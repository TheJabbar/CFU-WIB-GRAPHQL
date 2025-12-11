import os
import uuid
import asyncio
import httpx
import chainlit as cl
from dotenv import load_dotenv
import json
import plotly.graph_objects as go
from typing import Dict, Any, List, Optional, Callable
import re
from gql import gql, Client
from gql.transport.websockets import WebsocketsTransport

load_dotenv()

# Application settings
API_URL = os.getenv("API_URL")
API_WS_URL = os.getenv("API_WS_URL", API_URL.replace("http://", "ws://").replace("https://", "wss://") if API_URL else None)
API_KEY = os.getenv("X_API_KEY")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "120.0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", None)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", None)

# Basic authentication for Chainlit
@cl.password_auth_callback
def auth_callback(username: str, password: str) -> Optional[cl.User]:
    """Authenticate user with a simple check (temporary for demo use)."""
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return cl.User(identifier="admin")
    return None

# Landing page starter questions
@cl.set_starters
async def set_starters():
    """Define starter questions shown on the landing page."""
    return [
        cl.Starter(
            label="Bagaimana performansi unit CFU WIB?",
            message="Bagaimana performansi unit CFU WIB pada periode Juli 2025?"
        ),
        cl.Starter(
            label="Tunjukkan tren Revenue unit DWS.",
            message="Bagaimana trend Revenue unit DWS untuk periode Januari 2025 sampai Juli 2025?"
        ),
        cl.Starter(
            label="Produk apa saja yang tidak tercapai?",
            message="Produk apa yang tidak tercapai pada unit WINS?"
        ),
        cl.Starter(
            label="Mengapa EBITDA tercapai?",
            message="Mengapa performansi EBITDA unit TELIN tercapai?"
        ),
    ]

# Utility for quick debug logging
def _debug(msg: str):
    """Wrapper for debug logs."""
    print(f"[Chainlit Debug] {msg}")


class ChatSession:
    """Manage per-session state such as history, last response, and topic."""

    def __init__(self, conversation_id: Optional[str] = None):
        self.chat_history: List[Dict[str, str]] = []
        self.conversation_id = conversation_id or str(uuid.uuid4())
        self.topic: Optional[str] = None
        self.last_response_data: Optional[Dict[str, Any]] = None

    def add_to_history(self, user_query: str, response: str):
        """Append user query and assistant response to history."""
        self.chat_history.append({"user": user_query, "assistant": response})

    def get_history_string(self, last_n: int = 3) -> str:
        """Return last N exchanges as a single formatted string."""
        history_str = ""
        for exchange in self.chat_history[-last_n:]:
            history_str += (
                f"User: {exchange['user']}\nAssistant: {exchange['assistant']}\n\n"
            )
        return history_str.strip()


# Helpers for text/number formatting
def format_number_simplified(num: Any) -> str:
    """Format numbers into Indonesian short units (T = Triliun, M = Miliar, Jt = Juta)."""
    if not isinstance(num, (int, float)):
        return str(num)

    if abs(num) >= 1_000_000_000:
        return f"{num / 1_000_000_000:,.1f} M"
    if abs(num) >= 1_000_000:
        return f"{num / 1_000_000:,.1f} Jt"
    return f"{num:,.0f}"


def format_number_full(num: Any) -> str:
    """Formats numbers with thousand separators, without simplification."""
    if not isinstance(num, (int, float)):
        return str(num)
    return f"{num:,.0f}"


def format_insight_text(text: str, formatter: Optional[Callable[[Any], str]]) -> str:
    """Find numbers in text and replace them using a custom formatter."""
    if not text or not formatter:
        return text

    def replace_number(match):
        num_str = match.group(0).replace(",", "")
        try:
            number = float(num_str)
            if number.is_integer():
                number = int(number)
            return formatter(number)
        except (ValueError, TypeError):
            return match.group(0)

    pattern = r"\b\d{1,3}(?:[.,]\d{3})+(?:\.\d+)?\b|\b\d{7,}\b"
    return re.sub(pattern, replace_number, text)

def rows_to_markdown_table(
    rows: List[Dict[str, Any]],
    columns: Optional[List[str]] = None,
    formatter: Optional[Callable[[Any], str]] = None,
) -> str:
    """Convert rows (list of dict) into a Markdown table."""
    if not rows:
        return ""

    if columns is None:
        columns = list(rows[0].keys())

    header = "| " + " | ".join(columns) + " |"
    alignment = "| " + " | ".join(["---"] * len(columns)) + " |"

    body_lines = []
    for row in rows:
        values = []
        for col in columns:
            val = row.get(col, "")
            # Skip formatting for period column
            if col.lower() == "period":
                values.append(str(val))
            # Check if column is percentage/achievement (has 'pct', 'ach', 'gmom', 'gyoy', etc.)
            elif isinstance(val, (int, float)) and any(keyword in col.lower() for keyword in ['pct', 'ach', 'gmom', 'gyoy', 'growth', 'achievement']):
                # Format percentages with 2 decimal places
                values.append(f"{val:.2f}%")
            # Apply number formatter for other numeric columns
            elif formatter and isinstance(val, (int, float)):
                values.append(formatter(val))
            else:
                values.append(str(val))
        body_lines.append("| " + " | ".join(values) + " |")

    return "\n".join([header, alignment, *body_lines])


# Networking utility with retry logic
async def _post_json_with_retry(url: str, payload: dict) -> dict:
    """Send POST request with retries and exponential backoff."""
    headers = {"Content-Type": "application/json", "x-api-key": API_KEY}
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(1.5**attempt)
            else:
                _debug(f"API request failed after {MAX_RETRIES} attempts: {e}")
                raise e


# API calls
async def recognize_user_intent(user_query: str) -> Dict[str, bool]:
    """Call the intent recognizer agent."""
    graphql_query = """
        query RecognizeIntent($query: String!) {
            recognizeIntent(query: $query) {
                wantsText
                wantsChart
                wantsTable
                wantsSimplifiedNumbers
            }
        }
    """
    payload = {"query": graphql_query, "variables": {"query": user_query}}
    try:
        result = await _post_json_with_retry(f"{API_URL}/cfu-insight", payload)
        intent_data = result.get("data", {}).get("recognizeIntent", {})
        return {
            "wantsText": intent_data.get("wantsText", True),
            "wantsChart": intent_data.get("wantsChart", False),
            "wantsTable": intent_data.get("wantsTable", True),
            "wantsSimplifiedNumbers": intent_data.get("wantsSimplifiedNumbers", True),
        }
    except Exception:
        return {
            "wantsText": True,
            "wantsChart": False,
            "wantsTable": True,
            "wantsSimplifiedNumbers": True,
        }

async def make_insight_request(user_query: str, chat_history: str, request_id: str):
    """
    Build and execute the main insight query.
    """

    fields_to_request = [
        "output",
        "chart { chart, chartType, chartLibrary }",
        "dataColumns",
        "dataRows",
        "intent { wantsText, wantsChart, wantsTable, wantsSimplifiedNumbers }"
    ]
    fields_string = "\n".join(fields_to_request)

    graphql_query = f"""
        query GetInsight($query: String!, $requestId: String!, $chatHistory: String) {{
            getInsight(query: $query, requestId: $requestId, chatHistory: $chatHistory) {{
                {fields_string}
            }}
        }}
    """
    payload = {
        "query": graphql_query,
        "variables": {
            "query": user_query,
            "requestId": request_id,
            "chatHistory": chat_history,
        }
    }
    return await _post_json_with_retry(f"{API_URL}/cfu-insight", payload)

async def subscribe_to_progress(request_id: str, progress_step: cl.Step, shared_data: Dict[str, Any]):
    """Subscribe to progress updates via GraphQL WebSocket and update step name dynamically."""
    subscription_query = gql("""
        subscription ProgressUpdates($requestId: String!) {
            progressUpdates(requestId: $requestId) {
                requestId
                step
                status
                message
                timestamp
                details
            }
        }
    """)

    try:
        transport = WebsocketsTransport(
            url=f"{API_WS_URL}/cfu-insight",
            init_payload={"headers": {"x-api-key": API_KEY}}  # Include API key in WebSocket connection init
        )
        async with Client(transport=transport, fetch_schema_from_transport=False) as session:

            async for result in session.subscribe(subscription_query, variable_values={"requestId": request_id}):
                update = result.get("progressUpdates", {})
                step_name = update.get("step", "")
                status = update.get("status", "")
                message = update.get("message", "")
                details = update.get("details")

                # Handle table_ready event - store table data in shared_data
                if step_name == "table_ready" and details:
                    try:
                        table_data = json.loads(details)
                        columns = table_data.get("columns", [])
                        rows = table_data.get("rows", [])

                        if rows and columns:
                            shared_data["table_columns"] = columns
                            shared_data["table_rows"] = rows
                            shared_data["wantsSimplifiedNumbers"] = table_data.get("wantsSimplifiedNumbers", True)
                            shared_data["table_ready"] = True
                    except Exception as table_err:
                        _debug(f"Error parsing table data: {table_err}")

                progress_step.name = f"| {message}"
                await progress_step.update()

                if status in ("completed", "error") and update.get("step") in ("complete", "error"):
                    break

    except Exception as e:
        _debug(f"Error in progress subscription: {e}")
        progress_step.name = f"⚠️ Error: {str(e)}"
        await progress_step.update()


async def subscribe_to_insight_stream(request_id: str, streaming_msg: cl.Message, shared_data: Dict[str, Any]):
    """Subscribe to streaming insight text via GraphQL WebSocket."""
    subscription_query = gql("""
        subscription InsightStream($requestId: String!) {
            insightStream(requestId: $requestId) {
                requestId
                chunk
                isFinal
            }
        }
    """)

    accumulated_text = ""
    table_displayed = False

    try:
        transport = WebsocketsTransport(
            url=f"{API_WS_URL}/cfu-insight",
            init_payload={"headers": {"x-api-key": API_KEY}}  # Include API key in WebSocket connection init
        )
        async with Client(transport=transport, fetch_schema_from_transport=False) as session:

            async for result in session.subscribe(subscription_query, variable_values={"requestId": request_id}):
                chunk_data = result.get("insightStream", {})

                chunk = chunk_data.get("chunk", "")
                is_final = chunk_data.get("isFinal", False)

                # Display table first if available and not yet displayed
                if not table_displayed and shared_data.get("table_ready"):
                    wants_simplified = shared_data.get("wantsSimplifiedNumbers", True)
                    formatter = format_number_simplified if wants_simplified else format_number_full
                    
                    table_md = rows_to_markdown_table(
                        shared_data.get("table_rows", []),
                        shared_data.get("table_columns", []),
                        formatter=formatter
                    )
                    if table_md:
                        streaming_msg.content = f"### Data Hasil Analisis\n\n{table_md}\n\n### Insight\n\n"
                        await streaming_msg.update()
                        table_displayed = True

                if chunk:
                    accumulated_text += chunk
                    # Update message content in real-time
                    if table_displayed:
                        wants_simplified = shared_data.get("wantsSimplifiedNumbers", True)
                        formatter = format_number_simplified if wants_simplified else format_number_full
                        
                        table_md = rows_to_markdown_table(
                            shared_data.get("table_rows", []),
                            shared_data.get("table_columns", []),
                            formatter=formatter
                        )
                        streaming_msg.content = f"### Data Hasil Analisis\n\n{table_md}\n\n### Insight\n\n{accumulated_text}"
                    else:
                        streaming_msg.content = accumulated_text
                    await streaming_msg.update()

                if is_final:
                    break

        return accumulated_text

    except Exception as e:
        _debug(f"Error in insight stream subscription: {e}")
        return accumulated_text


async def make_post_analysis_request(chat_history: str):
    """Request topic and recommendations after main insight."""
    graphql_query = """
        query GetPostAnalysis($chatHistory: String!) {
            getTopic(chatHistory: $chatHistory) { output }
            getRecommendation(chatHistory: $chatHistory) { output }
        }
    """
    payload = {"query": graphql_query, "variables": {"chatHistory": chat_history}}
    return await _post_json_with_retry(f"{API_URL}/cfu-insight", payload)


# Chainlit event handlers
@cl.on_chat_start
async def start_chat():
    """Initialize chat session when conversation starts."""
    session = ChatSession()
    cl.user_session.set("chat_session", session)


@cl.on_message
async def main(message: cl.Message):
    """Main message handler with a simplified, single-API-call flow."""
    user_query = message.content.strip()
    if not user_query:
        await cl.Message(content="Mohon masukkan pertanyaan yang valid.").send()
        return

    chat_session: ChatSession = cl.user_session.get("chat_session")
    request_id = str(uuid.uuid4())

    # Shared data between progress and streaming
    shared_data = {
        "table_ready": False,
        "table_columns": [],
        "table_rows": []
    }

    async with cl.Step(name=" | Menganalisis pertanyaan Anda...", type="run") as progress_step:

        try:
            progress_task = asyncio.create_task(subscribe_to_progress(request_id, progress_step, shared_data))

            # Create empty message for streaming text
            streaming_msg = cl.Message(content="")
            await streaming_msg.send()

            # Start insight stream subscription with table display
            stream_task = asyncio.create_task(subscribe_to_insight_stream(request_id, streaming_msg, shared_data))

            chat_history = chat_session.get_history_string(last_n=3)
            insight_result = await make_insight_request(user_query, chat_history, request_id)

            await progress_task
            streamed_text = await stream_task

        except Exception as e:
            progress_step.name = f"❌ Error: {str(e)}"
            await progress_step.update()
            await cl.Message(content=f"❌ Terjadi kesalahan: {str(e)}").send()
            return

    try:
        insight_data = insight_result.get("data", {}).get("getInsight") # Cukup .get() tanpa default di sini

        if not insight_data:
            await cl.Message(content="Maaf, saya tidak dapat menghasilkan output untuk permintaan tersebut. Respons dari server kosong.").send()
            return

        answer = insight_data.get("output")
        data_rows = insight_data.get("dataRows", [])
        data_columns = insight_data.get("dataColumns", [])
        chart_info = insight_data.get("chart")
        intent_from_backend = insight_data.get("intent") or {}  # PERBAIKAN: Default ke {} jika None

        if not intent_from_backend.get("wantsSimplifiedNumbers", True):
            formatter = format_number_full
        else:
            formatter = format_number_simplified

        table_md = rows_to_markdown_table(data_rows, data_columns, formatter=formatter) if data_rows else ""
        formatted_answer = format_insight_text(answer, formatter) if answer else answer

        cacheable_data = {
            "output": answer,
            "data_rows": data_rows,
            "data_columns": data_columns,
            "chart": chart_info.get("chart") if isinstance(chart_info, dict) else None,
            "chart_type": chart_info.get("chartType") if isinstance(chart_info, dict) else None,
            "chart_library": chart_info.get("chartLibrary") if isinstance(chart_info, dict) else None,
        }
        chat_session.last_response_data = cacheable_data

        # Check the intent from the backend to understand what the user wants.
        wants_text = intent_from_backend.get("wantsText", True)
        wants_table = intent_from_backend.get("wantsTable", True)

        # FIX: Ensure table is displayed if streaming missed it (e.g. race condition or fast response)
        if streamed_text and table_md and "### Data Hasil Analisis" not in streaming_msg.content:
             current_text = streaming_msg.content
             streaming_msg.content = f"### Data Hasil Analisis\n\n{table_md}\n\n### Insight\n\n{current_text}"
             await streaming_msg.update()

        # Add chart at the end (after table and streaming text)
        elements = []
        if isinstance(chart_info, dict) and chart_info.get("chart"):
            try:
                fig = go.Figure(json.loads(chart_info["chart"]))
                elements.append(cl.Plotly(figure=fig, display="inline"))

                # Add chart title to the message content
                current_content = streaming_msg.content
                if current_content and not current_content.endswith("\n\n"):
                    current_content += "\n\n"
                streaming_msg.content = current_content + "### Grafik Visualisasi\n"
                streaming_msg.elements = elements
                await streaming_msg.update()
            except Exception as chart_e:
                _debug(f"Error displaying chart: {chart_e}")

        # If no streaming happened (e.g., greeting), send as regular message
        if not streamed_text and formatted_answer:
            final_content = "\n\n".join([table_md, formatted_answer] if table_md else [formatted_answer])
            result_msg = cl.Message(content=final_content, elements=elements)
            await result_msg.send()

        chat_session.add_to_history(user_query, answer or "")

        # Background post-analysis (topic & recommendations)
        updated_chat_history = chat_session.get_history_string(last_n=3)

        async def post_analysis_task():
            try:
                post_analysis_result = await make_post_analysis_request(updated_chat_history)
                post_data = post_analysis_result.get("data", {})
                topic_data = post_data.get("getTopic", {})
                rec_data = post_data.get("getRecommendation", {})

                if topic_data and topic_data.get("output"):
                    await cl.Message(content=f"*Topik saat ini: {topic_data['output'].strip()}*").send()
                if rec_data and rec_data.get("output"):
                    await cl.Message(content=f"*Rekomendasi pertanyaan selanjutnya: {rec_data['output'].strip()}*").send()
            except Exception as e:
                _debug(f"Post-analysis task failed: {e}")

        asyncio.create_task(post_analysis_task())

    except Exception as e:
        error_msg = f"❌ Terjadi kesalahan saat memproses permintaan.\n\n**Error:** {str(e)}"
        await cl.Message(content=error_msg).send()


@cl.on_chat_end
async def end_chat():
    """Clean up when the user ends the chat."""
    sess: ChatSession = cl.user_session.get("chat_session")
    _debug(f"Chat session ended. conversation_id={getattr(sess, 'conversation_id', 'N/A')}")