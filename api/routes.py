from typing import List, Dict, Any, Optional, Tuple
import json
import time
import re
from datetime import datetime
import pytz
from fastapi import HTTPException
from fastapi.security.api_key import APIKey
from loguru import logger

# Internal modules
from config import settings
from database import get_table_columns, execute_query

from llm_engine import (
    telkomllm_main_agent,
    telkomllm_select_table,
    telkomllm_generate_sql,
    telkomllm_infer_sql,
    telkomllm_fix_sql,
    telkomllm_generate_topic,
    telkomllm_generate_recommendation_question,
    telkomllm_greeting_and_general
)

from lib.prompt import (
    agent_prompt,
    generate_sql_prompt,
    generate_insight_prompt,
    sql_fix_prompt,
    select_table_and_prompt_prompt,
    generate_topic_prompt,
    recommendation_question_prompt,
    recognize_components_prompt
)

from chart_generator import ChartGenerator


# Runtime constants
SQL_FIX_RETRIES = 3
MAX_AGENT_STEPS = 3


# JSON utilities
def _extract_json_object(text: str) -> Optional[str]:
    """Extract the first valid JSON object from a string, considering nested braces."""
    if not text:
        return None

    s = text.strip()
    first_brace = s.find("{")
    if first_brace == -1:
        return None

    brace_count = 0
    for i in range(first_brace, len(s)):
        if s[i] == "{":
            brace_count += 1
        elif s[i] == "}":
            brace_count -= 1

        if brace_count == 0:
            candidate = s[first_brace : i + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue

    return None


def _safe_json_loads(text_or_obj, required_keys: Optional[List[str]] = None) -> Optional[dict]:
    """
    A safer json.loads wrapper that handles both strings and dicts,
    and extracts the first valid JSON block if the input is noisy.
    """
    if isinstance(text_or_obj, dict):
        data = text_or_obj
    elif isinstance(text_or_obj, str):
        s = text_or_obj.strip()
        first_brace = s.find("{")
        if first_brace == -1:
            return None

        brace_count = 1
        for i in range(first_brace + 1, len(s)):
            if s[i] == "{":
                brace_count += 1
            elif s[i] == "}":
                brace_count -= 1

            if brace_count == 0:
                json_block = s[first_brace : i + 1]
                try:
                    data = json.loads(json_block)
                    break
                except json.JSONDecodeError:
                    brace_count = 1
                    continue
        else:
            return None
    else:
        return None

    if required_keys and not all(k in data for k in required_keys):
        logger.warning(
            f"JSON missing required keys. Got: {list(data.keys())}, Expected: {required_keys}"
        )
        return None

    return data


# Chart helpers
def _should_generate_chart(prompt_name: str, user_query: str, rows: List[Dict[str, Any]]) -> bool:
    """Check if a chart should be generated based on prompt type and available data."""
    trend_prompts = {
        "CFU Trend Analysis",
        "CFU Comparison Trend Analysis",
        "CFU External Revenue Trend Analysis",
    }
    is_trend_request = prompt_name in trend_prompts

    has_multiple_periods = False
    if rows and "period" in rows[0]:
        unique_periods = len({row["period"] for row in rows})
        has_multiple_periods = unique_periods > 1

    return is_trend_request and has_multiple_periods


def _determine_chart_type(prompt_name: str, user_query: str) -> str:
    """Select chart type string based on prompt name."""
    if "Comparison Trend" in (prompt_name or ""):
        return "comparison_trend"
    if "External Revenue Trend" in (prompt_name or ""):
        return "external_revenue_trend"
    return "trend"


# Core agent functions
async def select_table_and_prompt(user_query: str) -> Tuple[str, str, str]:
    """
    Use LLM to select the most relevant table and prompt.
    Returns: (table_name, instruction_prompt, prompt_name_for_chart).
    """
    t0 = time.monotonic()
    tables_list = [
        f"{c['table_name']}: {c.get('table_description', '')}"
        for c in settings.tables_config
    ]
    prompt_list = [
        f"{p['prompt_name']}: {p.get('prompt_description', '')}"
        for p in settings.prompt_config
    ]

    raw = await telkomllm_select_table(
        prompt=select_table_and_prompt_prompt,
        tables_list=tables_list,
        prompt_list=prompt_list,
        user_query=user_query,
    )
    logger.debug(f"[Timing] select_table_and_prompt {(time.monotonic() - t0):.2f}s")

    parsed = _safe_json_loads(raw, required_keys=["table_name", "prompt"])
    if not parsed:
        logger.warning(f"[Agentic] select_table invalid JSON. Raw: {str(raw)[:300]}")
        default_table = settings.tables_config[0]["table_name"] if settings.tables_config else ""
        default_prompt = settings.prompt_config[0]["prompt_name"] if settings.prompt_config else ""
        if not default_table or not default_prompt:
            raise HTTPException(status_code=502, detail="No valid fallback for select_table.")
        parsed = {"table_name": default_table, "prompt": default_prompt}

    table_name = parsed["table_name"]
    prompt_name = parsed["prompt"]
    instruction_prompt = settings.get_prompt_by_name(prompt_name)

    # If the selected prompt is for greetings, we don't need a valid table.
    if prompt_name == "Greeting or General Question":
        return table_name, instruction_prompt, prompt_name

    # For all other data-related prompts, a valid table name is required.
    valid_names = [c["table_name"] for c in settings.tables_config]
    if table_name not in valid_names:
        raise HTTPException(status_code=400, detail=f"Invalid table selected by LLM: {table_name}")

    return table_name, instruction_prompt, prompt_name


def get_schema_and_sample(table_name: str) -> Tuple[List[str], Dict[str, Any]]:
    """Fetch table schema and a sample row for context."""
    t0 = time.monotonic()
    column_list = get_table_columns(settings.database_api_path, table_name)
    if not column_list:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found or empty.")

    first_row_list = execute_query(settings.database_api_path, f"SELECT * FROM {table_name} LIMIT 1")
    first_row = first_row_list[0] if first_row_list else {}
    logger.debug(f"[Timing] get_schema_and_sample {(time.monotonic() - t0):.2f}s")
    return column_list, first_row


async def execute_agent_step(agent_prompt_text: str, query: str, chat_history: Optional[str], tools_answer: str) -> Dict[str, Any]:
    """Run a single agent step. Returns dict with keys: action, action_input, final_answer."""
    t0 = time.monotonic()
    raw = await telkomllm_main_agent(
        agent_prompt=agent_prompt_text,
        user_query=query,
        chat_history=chat_history or "",
        tools_answer=tools_answer or "",
    )
    logger.debug(f"[Timing] execute_agent_step {(time.monotonic() - t0):.2f}s")

    state = _safe_json_loads(raw, required_keys=["action", "action_input", "final_answer"])
    if not state:
        logger.warning(f"[Agentic] main_agent invalid JSON. Raw: {str(raw)[:300]}")
        state = {"action": "Continue", "action_input": query, "final_answer": ""}
    return state


async def generate_and_validate_sql(table_name: str, columns_list: List[str], first_row: Dict[str, Any],
                                    user_query: str, instruction_prompt: str) -> str:
    """Ask LLM to generate SQL and validate the response."""
    t0 = time.monotonic()
    generated_sql = await telkomllm_generate_sql(
        prompt=generate_sql_prompt,
        table_name=table_name,
        columns_list=columns_list,
        first_row=first_row,
        user_query=user_query,
        instruction_prompt=instruction_prompt,
    )
    logger.debug(f"[Timing] generate_and_validate_sql {(time.monotonic() - t0):.2f}s")
    logger.info(f"[Agentic] Generated SQL: {generated_sql}")

    if isinstance(generated_sql, dict) and "error" in generated_sql:
        logger.error(f"LLM SQL generation failed: {generated_sql['error']}")
        raise HTTPException(status_code=500, detail=f"LLM SQL generation failed: {generated_sql['error']}")
    return generated_sql


async def execute_sql_query(generated_sql: str, columns_list: List[str]) -> List[Dict[str, Any]]:
    """Run SQL query with error handling and retry using LLM-based fix if needed."""
    t0 = time.monotonic()
    try:
        rows = execute_query(settings.database_api_path, generated_sql)
        logger.debug(f"[Timing] execute_sql_query {(time.monotonic() - t0):.2f}s (success). Rows={len(rows)}")

        if not rows:
            logger.warning("[Agentic] Query returned no rows. Trying LLM fix...")
            fixed_sql = await telkomllm_fix_sql(
                prompt=sql_fix_prompt,
                columns_list=columns_list,
                error_sql=generated_sql,
                error_message="No data found for the given query."
            )
            rows = execute_query(settings.database_api_path, fixed_sql)
            logger.debug(f"[Agentic] Fixed empty result. Rows={len(rows)}")

        return rows

    except Exception as exec_error:
        logger.warning(f"[Agentic] SQL error: {exec_error}. Trying to fix...")
        fixed_sql = await telkomllm_fix_sql(
            prompt=sql_fix_prompt,
            columns_list=columns_list,
            error_sql=generated_sql,
            error_message=str(exec_error)
        )
        last_exc = exec_error

        for attempt in range(SQL_FIX_RETRIES):
            try:
                rows = execute_query(settings.database_api_path, fixed_sql)
                logger.debug(
                    f"[Timing] execute_sql_query FIX {(time.monotonic() - t0):.2f}s "
                    f"(attempt {attempt+1}). Rows={len(rows)}"
                )
                return rows
            except Exception as e2:
                last_exc = e2

        logger.error(f"[Agentic] SQL execution failed after retries: {last_exc}")
        raise HTTPException(status_code=500, detail=f"SQL execution failed: {last_exc}")


async def generate_insight(table_name: str, columns_list: List[str], table_data: List[Dict[str, Any]],
                           user_query: str, instruction_prompt: str, intent: Dict[str, bool], 
                           stream: bool = False, stream_callback = None) -> str:
    """Use LLM to generate textual insight from query results."""
    t0 = time.monotonic()

    if intent.get("wants_simplified_numbers", True):
        number_format_instruction = "Gunakan format sederhana (contoh: Rp5.025,1 Miliar, bukan Rp5,03 Triliun)."
    else:
        number_format_instruction = "Gunakan angka lengkap tanpa singkatan (contoh: 5.025.100.000.000)."
    
    final_prompt = generate_insight_prompt.replace('{number_format_instruction}', number_format_instruction)

    insight = await telkomllm_infer_sql(
        prompt=final_prompt, 
        user_query=user_query,
        table_name=table_name,
        instruction_prompt=instruction_prompt,
        column_list=columns_list,
        table_data=table_data,
        stream=stream,
        stream_callback=stream_callback
    )
    logger.debug(f"[Timing] generate_insight {(time.monotonic() - t0):.2f}s")
    return str(insight)


async def get_insight_logic(
    query: str,
    chat_history: Optional[str],
    requested_fields: List[str],
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main agent logic combining a robust agentic loop with the corrected flow:
    1. Plan first (Contextualize Query).
    2. Then, enter an execution loop that handles the rest.
    """
    
    def emit(step: str, status: str, message: str, details: Optional[str] = None):
        if request_id:
            try:
                from graphql_schema import emit_progress
                emit_progress(request_id, step, status, message, details)
            except ImportError:
                pass

    # Contextualization (adjust the follow-up question based on chat history)
    emit("context_completion", "in_progress", "Memahami konteks pertanyaan...")
    planning_state = await execute_agent_step(
        agent_prompt_text=agent_prompt,
        query=query,
        chat_history=chat_history,
        tools_answer=""
    )
    completed_query = planning_state.get("action_input") or query
    logger.info(f"Query contextualized from '{query}' to '{completed_query}'")
    emit("context_completion", "completed", f"Pertanyaan diproses: {completed_query}")

    # Intent Recognition
    emit("intent", "in_progress", "Mengenali intent...")
    intent_dict = await get_intent_logic(completed_query)
    logger.info(f"Intent recognized for completed query: {intent_dict}")
    emit("intent", "completed", "Intent berhasil dikenali")

    # Table & Prompt Selection
    emit("table_selection", "in_progress", "Memilih tabel dan prompt...")
    table_name, instruction_prompt, prompt_name_for_chart = await select_table_and_prompt(completed_query)
    emit("table_selection", "completed", f"Tabel terpilih: {table_name}")

    if prompt_name_for_chart == "Greeting or General Question":
        logger.info("Handling a greeting or general question, bypassing data pipeline.")
        emit("greeting", "in_progress", "Memproses sapaan...")
        jakarta_tz = pytz.timezone("Asia/Jakarta")
        current_time_str = datetime.now(jakarta_tz).strftime('%A, %d %B %Y, %H:%M %Z')
        time_aware_prompt = instruction_prompt.replace('{current_time}', current_time_str)
        greeting_response = await telkomllm_greeting_and_general(
            prompt=time_aware_prompt, user_query=completed_query
        )
        emit("greeting", "completed", "Respon sapaan berhasil dibuat")
        return { 
            "output": str(greeting_response), 
            "chart": None, 
            "chart_type": None, 
            "chart_library": None, 
            "data_columns": [], 
            "data_rows": [],
            "intent": intent_dict
        }

    # Data Schema Preparation
    emit("schema", "in_progress", "Mengambil skema data...")
    column_list, first_row = get_schema_and_sample(table_name)
    emit("schema", "completed", "Skema data berhasil diambil")


    insight_text = ""
    last_rows: List[Dict[str, Any]] = []
    step_count = 0

    agent_state = {"action": "Continue", "action_input": completed_query, "final_answer": ""}

    while agent_state["action"] != "Final Answer":
        if step_count >= MAX_AGENT_STEPS:
            logger.warning(f"[Agentic] Reached MAX_AGENT_STEPS. Forcing final answer.")
            agent_state["final_answer"] = insight_text or "Proses mencapai batas maksimal, tidak ada insight yang dapat dihasilkan."
            break

        # If the insight already exists, do not process or reason further
        if insight_text:
            logger.debug("[Agentic] Insight text is ready. Bypassing agent thought process.")
            agent_state = { "action": "Final Answer", "action_input": "", "final_answer": insight_text }
            continue

        action_input = agent_state.get("action_input") or completed_query

        emit("sql", "in_progress", "Membuat SQL query...")
        generated_sql = await generate_and_validate_sql(
            table_name=table_name, columns_list=column_list, first_row=first_row,
            user_query=action_input, instruction_prompt=instruction_prompt
        )
        emit("sql", "completed", "SQL query berhasil dibuat")

        emit("query", "in_progress", "Menjalankan query ke database...")
        rows = await execute_sql_query(generated_sql, column_list)
        emit("query", "completed", f"Query berhasil - {len(rows)} baris data ditemukan")
        last_rows = rows

        if "output" in requested_fields:
            emit("insight", "in_progress", "Menghasilkan insight dari data...")
            
            # Define streaming callback
            async def stream_callback(chunk: str):
                try:
                    from graphql_schema import emit_text_stream
                    emit_text_stream(request_id, chunk, is_final=False)
                except ImportError:
                    pass
            
            insight_text = await generate_insight(
                table_name=table_name, columns_list=column_list, table_data=rows,
                user_query=action_input, instruction_prompt=instruction_prompt,
                intent=intent_dict,
                stream=True if request_id else False,
                stream_callback=stream_callback if request_id else None
            )
            
            # Emit final chunk
            if request_id:
                try:
                    from graphql_schema import emit_text_stream
                    emit_text_stream(request_id, "", is_final=True)
                except ImportError:
                    pass
            
            emit("insight", "completed", "Insight teks berhasil dibuat")
        else:
            insight_text = "Data berhasil diambil."
        
        step_count += 1

    final_output = agent_state.get("final_answer") or insight_text


    chart_json, chart_library, chart_type = None, None, None
    if "chart" in requested_fields and intent_dict.get("wants_chart", False):
        emit("chart", "in_progress", "Memeriksa kelayakan chart...")
        if _should_generate_chart(prompt_name_for_chart, completed_query, last_rows):
            chart_type = _determine_chart_type(prompt_name_for_chart, completed_query)
            emit("chart", "in_progress", f"Membuat chart tipe: {chart_type}...")
            chart_json = ChartGenerator.create_trend_chart(last_rows, chart_type)
            if chart_json:
                chart_library = "plotly"
                emit("chart", "completed", f"Chart {chart_type} berhasil dibuat")
        else:
            emit("chart", "completed", "Chart tidak diperlukan untuk query ini")

    data_rows_to_send, data_columns_to_send = [], []
    if "dataRows" in requested_fields and intent_dict.get("wants_table", False) and last_rows:
        data_rows_to_send = last_rows
        if "dataColumns" in requested_fields:
            data_columns_to_send = list(last_rows[0].keys())

    return {
        "output": str(final_output),
        "chart": chart_json,
        "chart_type": chart_type,
        "chart_library": chart_library,
        "data_columns": data_columns_to_send,
        "data_rows": data_rows_to_send,
        "intent": intent_dict
    }

async def get_topic_logic(chat_history: str) -> str:
    """Generate discussion topic based on the chat history."""
    topic = await telkomllm_generate_topic(
        prompt=generate_topic_prompt,
        user_query=chat_history or ""
    )
    return str(topic)


async def get_recommendation_logic(chat_history: str) -> str:
    """Generate a recommendation-related question from the chat history."""
    rec_q = await telkomllm_generate_recommendation_question(
        prompt=recommendation_question_prompt,
        chat_history=chat_history or ""
    )
    return str(rec_q)


async def get_intent_logic(query: str) -> Dict[str, bool]:
    """
    Identify the intended output components from a user query.
    Returns a dictionary with four keys: wants_text, wants_chart,
    wants_table, and wants_simplified_numbers.
    """
    logger.info(f"Recognizing intent for query: '{query}'")

    raw_response = await telkomllm_main_agent(
        agent_prompt=recognize_components_prompt.format(user_query=query),
        user_query=query
    )
    parsed_intent = _safe_json_loads(raw_response)

    required_keys = ["wants_text", "wants_chart", "wants_table"]

    if parsed_intent and all(k in parsed_intent for k in required_keys):
        logger.info(f"Intent recognized: {parsed_intent}")
        return parsed_intent

    logger.warning("Failed to parse intent from LLM, using fallback defaults.")
    return {
        "wants_text": True,
        "wants_chart": False,
        "wants_table": True,
        "wants_simplified_numbers": True 
    }


async def health_check() -> Dict[str, str]:
    """Return a simple status indicator for health checks."""
    return {"status": "ok"}