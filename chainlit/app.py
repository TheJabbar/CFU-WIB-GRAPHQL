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

load_dotenv()

# Application settings
API_URL = os.getenv("API_URL")
API_KEY = os.getenv("X_API_KEY")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "120.0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", None)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", None)

# Basic authentication for Chainlit
@cl.password_auth_callback
def auth_callback(username: str, password: str) -> Optional[cl.User]:
    """Authenticate user with a simple check (temporary for demo use)."""
    if username == "admin" and password == "admin":
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
            # Apply the passed formatter unconditionally
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
            if formatter and isinstance(val, (int, float)) and col.lower() != "period":
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
    """Step 1: Call the lightweight intent recognizer agent."""
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
        # Normalize field names to snake_case for easier use in Python
        return {
            "wants_text": intent_data.get("wantsText", True),
            "wants_chart": intent_data.get("wantsChart", False),
            "wants_table": intent_data.get("wantsTable", True),
            "wants_simplified_numbers": intent_data.get("wantsSimplifiedNumbers", True)
        }
    except Exception:
        # Fallback when recognizer fails
        return {
            "wants_text": True,
            "wants_chart": False,
            "wants_table": True,
            "wants_simplified_numbers": True
        }

async def make_insight_request(user_query: str, chat_history: str, intent: Dict[str, bool]):
    """Step 2: Build and execute the main insight query based on the recognized intent."""
    
    fields_to_request = []
    if intent["wants_text"]:
        fields_to_request.append("output")
    if intent["wants_chart"]:
        fields_to_request.append("chart { chart, chartType, chartLibrary }")
    if intent["wants_table"]:
        fields_to_request.extend(["dataColumns", "dataRows"])

    # Default to output if nothing is explicitly requested
    if not fields_to_request:
        fields_to_request.append("output")
        
    fields_string = "\n".join(fields_to_request)

    graphql_query = f"""
        query GetInsight($query: String!, $chatHistory: String!) {{
            getInsight(query: $query, chatHistory: $chatHistory) {{
                {fields_string}
            }}
        }}
    """
    payload = {"query": graphql_query, "variables": {"query": user_query, "chatHistory": chat_history}}
    return await _post_json_with_retry(f"{API_URL}/cfu-insight", payload)


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
    """Main message handler (insight + optional post-analysis)."""
    user_query = message.content.strip()
    if not user_query:
        await cl.Message(content="Mohon masukkan pertanyaan yang valid.").send()
        return

    chat_session: ChatSession = cl.user_session.get("chat_session")

    # Initial loading message
    loading_msg = cl.Message(content="Sedang memproses permintaan Anda...")
    await loading_msg.send()

    try:
        # Step 1: Recognize intent (including format requests)
        intent = await recognize_user_intent(user_query)
        
        # Step 2: Call main agent with optimized query
        chat_history = chat_session.get_history_string(last_n=3)
        insight_result = await make_insight_request(user_query, chat_history, intent)

        insight_data = insight_result.get("data", {}).get("getInsight", {})
        if not insight_data:
            await cl.Message(content="Maaf, saya tidak dapat menghasilkan output untuk permintaan tersebut.").send()
            return

        answer = insight_data.get("output")
        data_rows = insight_data.get("dataRows", [])
        data_columns = insight_data.get("dataColumns", [])
        
        # Choose formatter depending on intent
        formatter = format_number_simplified if intent.get("wants_simplified_numbers", True) else format_number_full
        
        # Format table and text if available
        table_md = rows_to_markdown_table(data_rows, data_columns, formatter=formatter) if data_rows else ""
        formatted_answer = format_insight_text(answer, formatter) if answer else answer
        
        # Store raw data for potential reformatting
        cacheable_data = {
            "output": answer,
            "data_rows": data_rows,
            "data_columns": data_columns,
            "chart": insight_data.get("chart", {}).get("chart"),
            "chart_type": insight_data.get("chart", {}).get("chartType"),
            "chart_library": insight_data.get("chart", {}).get("chartLibrary"),
        }
        chat_session.last_response_data = cacheable_data

        # Assemble final content
        content_parts = []
        if table_md:
            content_parts.append(table_md)
        if formatted_answer:
            content_parts.append(formatted_answer)
        
        final_content = "\n\n".join(content_parts) or "Berhasil mengambil data, namun tidak ada output teks atau tabel untuk ditampilkan."

        # Add chart if available
        elements = []
        chart_info = insight_data.get("chart")
        if chart_info and chart_info.get("chart"):
            try:
                fig = go.Figure(json.loads(chart_info["chart"]))
                elements.append(cl.Plotly(figure=fig, display="inline"))
            except Exception as chart_e:
                final_content += f"\n\n*❌ Gagal menampilkan grafik: {str(chart_e)}*"

        # If only a chart is present, keep content empty
        if elements and not content_parts:
            final_content = ""

        loading_msg.content = final_content
        loading_msg.elements = elements
        await loading_msg.update()

        # Update history with the plain text answer
        chat_session.add_to_history(user_query, answer)

        # Step 3: Background post-analysis (topic & recommendations)
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
        loading_msg.content = error_msg
        await loading_msg.update()


@cl.on_chat_end
async def end_chat():
    """Clean up when the user ends the chat."""
    sess: ChatSession = cl.user_session.get("chat_session")
    _debug(f"Chat session ended. conversation_id={getattr(sess, 'conversation_id', 'N/A')}")    