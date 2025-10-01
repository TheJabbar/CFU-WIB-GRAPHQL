# app.py

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

# API endpoint configurations
API_URL = os.getenv("API_URL")
TOPIC_API_URL = os.getenv("TOPIC_API_URL")
REC_API_URL = os.getenv("REC_API_URL")
API_KEY = os.getenv("X_API_KEY")

# Request settings for robustness
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "120.0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Authentication
@cl.password_auth_callback
def auth_callback(username: str, password: str) -> Optional[cl.User]:
    """Authenticates users based on a username and password."""
    if username == "admin" and password == "admin":
        return cl.User(identifier="admin")
    return None

# 4 Question Starters (Landing Page)
@cl.set_starters
async def set_starters():
    """Defines the starter questions for the landing page."""
    return [
        cl.Starter(
            label="Bagaimana performansi unit CFU WIB?",
            message="Bagaimana performansi unit CFU WIB pada periode Juli 2025?",
        ),
        cl.Starter(
            label="Tunjukkan tren Revenue unit DWS.",
            message="Bagaimana trend Revenue unit DWS untuk periode Januari 2025 sampai Juli 2025?",
        ),
        cl.Starter(
            label="Produk apa saja yang tidak tercapai?",
            message="Produk apa yang tidak tercapai pada unit WINS?",
        ),
        cl.Starter(
            label="Mengapa EBITDA tercapai?",
            message="Mengapa performansi EBITDA unit TELIN tercapai?",
        ),
    ]

# Helper Functions & Classes
def _debug(msg: str):
    """A simple print wrapper for debugging messages."""
    print(f"[Chainlit Debug] {msg}")

class ChatSession:
    """
    Manages the state for a single chat session, including conversation history
    and the last API response for re-formatting purposes.
    """
    def __init__(self, conversation_id: Optional[str] = None):
        self.chat_history: List[Dict[str, str]] = []
        self.conversation_id = conversation_id or str(uuid.uuid4())
        self.topic: Optional[str] = None
        # Store the last full API response to allow re-formatting
        self.last_response_data: Optional[Dict[str, Any]] = None

    def add_to_history(self, user_query: str, response: str):
        """Adds a user query and assistant response to the history."""
        self.chat_history.append({"user": user_query, "assistant": response})

    def get_history_string(self, last_n: int = 5) -> str:
        """Formats the last N chat turns into a single string for context."""
        history_str = ""
        for exchange in self.chat_history[-last_n:]:
            history_str += f"User: {exchange['user']}\nAssistant: {exchange['assistant']}\n\n"
        return history_str.strip()

# Number Formatting Helpers
def format_number_simplified(num: Any) -> str:
    """
    Formats a number into a simplified string with Indonesian units (M for Miliar, Jt for Juta).
    """
    if not isinstance(num, (int, float)):
        return str(num)

    # Handle 'Miliar'
    if abs(num) >= 1_000_000_000:
        return f'{num / 1_000_000_000:,.1f} M'
    # Handle 'Juta' 
    if abs(num) >= 1_000_000:
        return f'{num / 1_000_000:,.1f} Jt'
    return f'{num:,.0f}'

def format_insight_text(text: str, formatter: Callable[[Any], str]) -> str:
    """
    Finds and replaces large numbers within a block of text using a given formatter function.
    """
    if not text:
        return ""
        
    def replace_number(match):
        # Clean the matched string to handle different thousand separators
        num_str = match.group(0).replace('.', '').replace(',', '')
        try:
            number = int(num_str)
            if abs(number) >= 1_000_000:
                 return formatter(number)
            else:
                 return match.group(0)
        except (ValueError, TypeError):
            return match.group(0)

    # Regex to find numbers, including those with separators (e.g., 1.000.000 or 1,000,000)
    # It also finds unformatted large numbers (7 digits or more).
    pattern = r'\b\d{1,3}(?:[.,]\d{3})+(?:\.\d+)?\b|\b\d{7,}\b'
    return re.sub(pattern, replace_number, text)

# Markdown Table Helper
def rows_to_markdown_table(
    rows: List[Dict[str, Any]], 
    columns: Optional[List[str]] = None,
    formatter: Optional[Callable[[Any], str]] = None
) -> str:
    """
    Converts a list of dictionary rows into a Markdown formatted table,
    with an optional formatter for numeric values.
    """
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
            if formatter and isinstance(val, (int, float)) and col.lower() != 'period':
                values.append(formatter(val))
            else:
                values.append(str(val))
        body_lines.append("| " + " | ".join(values) + " |")

    return "\n".join([header, alignment, *body_lines])

async def _post_json_with_retry(url: str, payload: dict) -> dict:
    """
    Sends a POST request with JSON data, including retries with exponential backoff.
    """
    headers = {"Content-Type": "application/json", "x-api-key": API_KEY}
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()  
                return response.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(1.5 ** attempt) # Exponential backoff
            else:
                _debug(f"API request failed after {MAX_RETRIES} attempts: {e}")
                raise e

# API Call Wrappers
async def make_insight_request(user_query: str, chat_history: str) -> dict:
    """Calls the main insight generation API."""
    payload = {"query": user_query, "chat_history": chat_history}
    return await _post_json_with_retry(API_URL, payload)

async def make_topic_request(text_source: str) -> Optional[str]:
    """Calls the topic generation API to summarize the conversation."""
    try:
        payload = {"chat_history": text_source}
        res = await _post_json_with_retry(TOPIC_API_URL, payload)
        return res.get("output")
    except Exception as e:
        _debug(f"Topic API error: {e}")
        return None

async def make_recommendation_request(chat_history: str) -> Optional[str]:
    """Calls the recommendation API to get follow-up question suggestions."""
    try:
        payload = {"chat_history": chat_history}
        res = await _post_json_with_retry(REC_API_URL, payload)
        return res.get("output")
    except Exception as e:
        _debug(f"Recommendation API error: {e}")
        return None

# Chainlit Event Handlers
@cl.on_chat_start
async def start_chat():
    """
    Initializes the user session when a new chat starts.
    """
    session = ChatSession()
    cl.user_session.set("chat_session", session)

@cl.on_message
async def main(message: cl.Message):
    """
    The main message handling function, triggered every time the user sends a message.
    """
    user_query = message.content.strip()
    if not user_query:
        await cl.Message(content="Mohon masukkan pertanyaan yang valid.").send()
        return

    chat_session: ChatSession = cl.user_session.get("chat_session")

    # Logic to handle on-the-fly formatting requests
    format_keywords = ["sederhanakan", "persingkat", "ringkas", "ubah satuan", "dalam miliar", "dalam juta", "simpelkan"]
    is_format_request = any(keyword in user_query.lower() for keyword in format_keywords)
    last_data = chat_session.last_response_data

    if is_format_request and last_data:
        loading_msg = cl.Message(content="Memformat ulang data...")
        await loading_msg.send()

        # 1. Format the insight text using the simplified number formatter
        formatted_answer = format_insight_text(last_data['output'], format_number_simplified)

        # 2. Format the table data
        table_md = ""
        if last_data.get("data_rows"):
            table_md = rows_to_markdown_table(
                last_data["data_rows"],
                last_data.get("data_columns"),
                formatter=format_number_simplified 
            )
        
        final_content = (table_md + "\n\n" if table_md else "") + formatted_answer

        # 3. Re-use the chart from the last response (no changes needed)
        elements = []
        if last_data.get("chart_library") == "plotly" and last_data.get("chart"):
            try:
                chart_json = last_data["chart"]
                fig = go.Figure(json.loads(chart_json))
                elements.append(cl.Plotly(figure=fig, display="inline"))
            except Exception as chart_e:
                final_content += f"\n\n---\n*❌ Gagal menampilkan grafik: {str(chart_e)}*"

        # 4. Update the message with the newly formatted content and stop processing.
        loading_msg.content = final_content
        loading_msg.elements = elements
        await loading_msg.update()
        return


    # Original logic for new queries
    loading_msg = cl.Message(content="Sedang memproses permintaan Anda...")
    await loading_msg.send()

    try:
        # 1. Call the backend API to get new insights.
        chat_history = chat_session.get_history_string()
        result = await make_insight_request(user_query, chat_history)

        # Store the raw, unformatted result in the session
        chat_session.last_response_data = result

        if isinstance(result, dict) and "error" in result:
            raise RuntimeError(result["error"])

        # 2. Parse the raw API response for initial display.
        answer = result.get("output", "Maaf, terjadi kesalahan pada format respons.")
        data_rows = result.get("data_rows", [])
        data_columns = result.get("data_columns")
        # Display raw data by default (no formatter is passed)
        table_md = rows_to_markdown_table(data_rows, data_columns) if data_rows else ""
        
        # 3. Combine text and table for the final message content.
        final_content = (table_md + "\n\n" if table_md else "") + answer
        
        # 4. Process and add Plotly charts if available.
        elements = []
        if result.get("chart_library") == "plotly" and result.get("chart"):
            try:
                chart_json = result["chart"]
                fig = go.Figure(json.loads(chart_json))
                elements.append(cl.Plotly(figure=fig, display="inline"))
            except Exception as chart_e:
                final_content += f"\n\n---\n*❌ Gagal menampilkan grafik: {str(chart_e)}*"

        # 5. Update the loading message with the final result.
        loading_msg.content = final_content
        loading_msg.elements = elements
        await loading_msg.update()

        # 6. Update the chat history.
        chat_session.add_to_history(user_query, answer)

        # 7. Asynchronously fetch topic and recommendations for the next turn.
        hist_text = chat_session.get_history_string(last_n=10)
        topic_task = asyncio.create_task(make_topic_request(hist_text))
        rec_task = asyncio.create_task(make_recommendation_request(hist_text))
        topic, rec_q = await asyncio.gather(topic_task, rec_task)
        
        # 8. Update chat title if a new topic is identified.
        if topic:
            topic_clean = topic.strip()
            if topic_clean and topic_clean != chat_session.topic:
                chat_session.topic = topic_clean
                await cl.Message(content=f"*Topik saat ini: {topic_clean}*").send()

    except Exception as e:
        # Handle any errors during processing and inform the user.
        error_msg = f"❌ Terjadi error saat memproses permintaan.\n\n**Error:** {str(e)}"
        loading_msg.content = error_msg
        await loading_msg.update()

@cl.on_chat_end
async def end_chat():
    """A hook that runs when the user closes the chat session."""
    sess: ChatSession = cl.user_session.get("chat_session")
    _debug(f"Chat session ended. conversation_id={getattr(sess, 'conversation_id', 'N/A')}")