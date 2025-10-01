from typing import List, Dict, Any, Optional, Tuple
import json
import re
import os
import time
from fastapi import Depends, HTTPException
from fastapi.security.api_key import APIKey
from loguru import logger

# Project modules
from security import get_api_key
from model import QueryInput, ChatHistoryInput, ChatResponse
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
)

from lib.prompt import (
    agent_prompt,
    generate_sql_prompt,
    generate_insight_prompt,
    sql_fix_prompt,
    select_table_and_prompt_prompt,
    generate_topic_prompt,
    recommendation_question_prompt,
)

from chart_generator import ChartGenerator


# Constants
SQL_FIX_RETRIES = 3
MAX_AGENT_STEPS = 3


# JSON Helpers
def _extract_json_object(text: str) -> Optional[str]:
    """Extract the first complete JSON object from a string, handling nested structures."""
    if not text:
        return None
    
    s = text.strip()
    
    # Find the first opening brace
    first_brace = s.find('{')
    if first_brace == -1:
        return None
        
    # Find the matching closing brace
    brace_count = 0
    for i in range(first_brace, len(s)):
        if s[i] == '{':
            brace_count += 1
        elif s[i] == '}':
            brace_count -= 1
        
        # If brace_count is zero, we've found the end of the object
        if brace_count == 0:
            potential_json = s[first_brace : i + 1]
            try:
                # Try to load it to ensure it's valid
                json.loads(potential_json)
                return potential_json
            except json.JSONDecodeError:
                # If it fails, continue searching in case of malformed objects
                continue
    
    # If no complete object is found, return None
    return None

def _safe_json_loads(text_or_obj, required_keys: Optional[List[str]] = None) -> Optional[dict]:
    """Safe json.loads that handles str/dict noisy inputs, optional key validation."""
    if isinstance(text_or_obj, dict):
        data = text_or_obj
    elif isinstance(text_or_obj, str):
        s = text_or_obj.strip()
        try:
            data = json.loads(s)
        except Exception:
            extracted = _extract_json_object(s)
            if not extracted:
                return None
            try:
                data = json.loads(extracted)
            except Exception:
                return None
    else:
        return None
    if required_keys:
        for k in required_keys:
            if k not in data:
                return None
    return data


# Chart Helpers
def _should_generate_chart(prompt_name: str, user_query: str) -> bool:
    """Determine if chart is relevant based on prompt or keywords."""
    trend_keywords = ['trend', 'grafik', 'chart', 'perbandingan', 'tampilkan']
    trend_prompts = [
        'CFU Trend Analysis',
        'CFU Comparison Trend Analysis',
        'CFU External Revenue Trend Analysis'
    ]
    return (prompt_name in trend_prompts or any(k in (user_query or "").lower() for k in trend_keywords))

def _determine_chart_type(prompt_name: str, user_query: str) -> str:
    """Return chart type based on prompt name."""
    if 'Comparison Trend' in (prompt_name or ''):
        return "comparison_trend"
    elif 'External Revenue Trend' in (prompt_name or ''):
        return "external_revenue_trend"
    return "trend"


# Modular Functions
async def select_table_and_prompt(user_query: str) -> Tuple[str, str, str]:
    """
    Select table & prompt using LLM.
    Returns: (table_name, instruction_prompt, prompt_name_for_chart).
    """
    t0 = time.monotonic()
    tables_list = [f"{c['table_name']}: {c.get('table_description', '')}" for c in settings.tables_config]
    prompt_list = [f"{p['prompt_name']}: {p.get('prompt_description', '')}" for p in settings.prompt_config]

    raw = await telkomllm_select_table(
        prompt=select_table_and_prompt_prompt,
        tables_list=tables_list,
        prompt_list=prompt_list,
        user_query=user_query
    )
    logger.debug(f"[Timing] select_table_and_prompt {(time.monotonic()-t0):.2f}s")

    parsed = _safe_json_loads(raw, required_keys=["table_name", "prompt"])
    if not parsed:
        logger.warning(f"[Agentic] select_table invalid JSON. Raw: {str(raw)[:300]}")
        default_table = settings.tables_config[0]["table_name"] if settings.tables_config else ""
        default_prompt = settings.prompt_config[0]["prompt_name"] if settings.prompt_config else ""
        if not default_table or not default_prompt:
            raise HTTPException(status_code=502, detail="LLM select_table invalid and no fallback available.")
        parsed = {"table_name": default_table, "prompt": default_prompt}

    table_name = parsed["table_name"]
    valid_names = [c['table_name'] for c in settings.tables_config]
    if table_name not in valid_names:
        raise HTTPException(status_code=400, detail=f"Invalid table selected by LLM: {table_name}")

    instruction_prompt = settings.get_prompt_by_name(parsed["prompt"])
    prompt_name_for_chart = parsed["prompt"]
    return table_name, instruction_prompt, prompt_name_for_chart

def get_schema_and_sample(table_name: str) -> Tuple[List[str], Dict[str, Any]]:
    """Retrieve column list and first sample row for LLM context."""
    t0 = time.monotonic()
    column_list = get_table_columns(settings.database_api_path, table_name)
    if not column_list:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found or has no columns.")
    first_row_list = execute_query(settings.database_api_path, f"SELECT * FROM {table_name} LIMIT 1")
    first_row = first_row_list[0] if isinstance(first_row_list, list) and first_row_list else {}
    logger.debug(f"[Timing] get_schema_and_sample {(time.monotonic()-t0):.2f}s")
    return column_list, first_row

async def execute_agent_step(agent_prompt_text: str, query: str, chat_history: Optional[str], tools_answer: str) -> Dict[str, Any]:
    """Run one agent step. Returns dict(action, action_input, final_answer) safely."""
    t0 = time.monotonic()
    raw = await telkomllm_main_agent(
        agent_prompt=agent_prompt_text,
        user_query=query,
        chat_history=chat_history or "",
        tools_answer=tools_answer or ""
    )
    logger.debug(f"[Timing] execute_agent_step {(time.monotonic()-t0):.2f}s")
    state = _safe_json_loads(raw, required_keys=["action", "action_input", "final_answer"])
    if not state:
        logger.warning(f"[Agentic] main_agent invalid JSON. Raw: {str(raw)[:300]}")
        state = {"action": "Continue", "action_input": query, "final_answer": ""}
    return state

async def generate_and_validate_sql(table_name: str, columns_list: List[str], first_row: Dict[str, Any],
                                    user_query: str, instruction_prompt: str) -> str:
    """Request LLM to generate SQL. Raise 500 if LLM returns error object."""
    t0 = time.monotonic()
    generated_sql = await telkomllm_generate_sql(
        prompt=generate_sql_prompt,
        table_name=table_name,
        columns_list=columns_list,
        first_row=first_row,
        user_query=user_query,
        instruction_prompt=instruction_prompt
    )
    logger.debug(f"[Timing] generate_and_validate_sql {(time.monotonic()-t0):.2f}s")
    logger.info(f"[Agentic] Generated SQL: {generated_sql}")

    if isinstance(generated_sql, dict) and "error" in generated_sql:
        logger.error(f"LLM SQL generation failed: {generated_sql['error']}")
        raise HTTPException(status_code=500, detail=f"LLM SQL generation failed: {generated_sql['error']}")
    return generated_sql

async def execute_sql_query(generated_sql: str, columns_list: List[str]) -> List[Dict[str, Any]]:
    """Execute SQL with error handling and LLM-assisted fix with retries."""
    t0 = time.monotonic()
    try:
        rows = execute_query(settings.database_api_path, generated_sql)
        logger.debug(f"[Timing] execute_sql_query {(time.monotonic()-t0):.2f}s (success). Rows={len(rows)}")
        if not rows:
            # Try fix when empty
            logger.warning("[Agentic] Query returned no rows. Attempting fix...")
            fixed_sql = await telkomllm_fix_sql(
                prompt=sql_fix_prompt,
                columns_list=columns_list,
                error_sql=generated_sql,
                error_message="No data found for the given query. Fix the SQL query."
            )
            rows = execute_query(settings.database_api_path, fixed_sql)
            logger.debug(f"[Agentic] Fixed empty result. Rows={len(rows)}")
        return rows
    except Exception as exec_error:
        logger.warning(f"[Agentic] SQL error: {exec_error}. Attempting to fix...")
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
                logger.debug(f"[Timing] execute_sql_query FIX {(time.monotonic()-t0):.2f}s (attempt {attempt+1}). Rows={len(rows)}")
                return rows
            except Exception as e2:
                last_exc = e2
        logger.error(f"[Agentic] SQL execution failed after retries: {last_exc}")
        raise HTTPException(status_code=500, detail=f"SQL execution failed after retries: {last_exc}")

async def generate_insight(table_name: str, columns_list: List[str], table_data: List[Dict[str, Any]],
                           user_query: str, instruction_prompt: str) -> str:
    """Generate insight from SQL query results."""
    t0 = time.monotonic()
    insight = await telkomllm_infer_sql(
        prompt=generate_insight_prompt,
        user_query=user_query,
        table_name=table_name,
        instruction_prompt=instruction_prompt,
        column_list=columns_list,
        table_data=table_data
    )
    logger.debug(f"[Timing] generate_insight {(time.monotonic()-t0):.2f}s")
    return str(insight)

def maybe_build_chart(prompt_name: str, user_query: str, rows: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Generate Plotly chart JSON if relevant."""
    if not rows:
        return None, None, None
    if _should_generate_chart(prompt_name, user_query):
        chart_type = _determine_chart_type(prompt_name, user_query)
        chart_json = ChartGenerator.create_trend_chart(rows, chart_type)
        if chart_json:
            logger.info("[Agentic] Plotly chart generated")
            return chart_json, "plotly", chart_type
    return None, None, None

# API functions (called by main.py)

async def get_insight_api(
    input_data: QueryInput,
    x_api_key: APIKey = Depends(get_api_key)
) -> ChatResponse:
    """
    Main insight generation entry:
    - Select table & prompt
    - Loop agent until Final Answer (max MAX_AGENT_STEPS)
    - If continue: Generate SQL -> Execute -> Generate Insight
    - Return narrative + raw rows + optional chart
    """
    try:
        # Step 0: Select table & prompt
        table_name, instruction_prompt, prompt_name_for_chart = await select_table_and_prompt(input_data.query)

        # Step 1: Get schema + sample row
        column_list, first_row = get_schema_and_sample(table_name)

        # Step 2: Loop agent until Final Answer or max steps reached = 3
        insight_text = ""
        last_rows: List[Dict[str, Any]] = []
        step_count = 0
        final_output: Optional[str] = None

        agent_state = {
            "action": "Start",
            "action_input": input_data.query,
            "final_answer": "",
        }

        while agent_state["action"] != "Final Answer":
            if step_count >= MAX_AGENT_STEPS:
                logger.warning(f"[Agentic] Reached MAX_AGENT_STEPS={MAX_AGENT_STEPS}. Forcing final answer.")
                agent_state["action"] = "Final Answer"
                agent_state["final_answer"] = insight_text or "No insights available."
                break

            logger.debug(f"[Debug] Chat history input: {input_data.chat_history}")

            # Run one agent step
            agent_state = await execute_agent_step(
                agent_prompt_text=agent_prompt,
                query=agent_state["action_input"],
                chat_history=input_data.chat_history,
                tools_answer=insight_text
            )
            logger.debug(f"[Agentic] Step {step_count+1} state: {agent_state}")

            # Final?
            if agent_state["action"] == "Final Answer":
                final_output = agent_state.get("final_answer") or insight_text or "No insights available."
                break

            # Continue => SQL -> Exec -> Insight
            action_input = agent_state.get("action_input") or input_data.query
            generated_sql = await generate_and_validate_sql(
                table_name=table_name,
                columns_list=column_list,
                first_row=first_row,
                user_query=action_input,
                instruction_prompt=instruction_prompt
            )
            rows = await execute_sql_query(generated_sql, column_list)
            last_rows = rows
            insight_text = await generate_insight(
                table_name=table_name,
                columns_list=column_list,
                table_data=rows,
                user_query=input_data.query,
                instruction_prompt=instruction_prompt
            )
            logger.info(f"[Agentic] Partial insight: {str(insight_text)[:300]}...")
            step_count += 1

        # Fallback final output if none
        if final_output is None:
            final_output = agent_state.get("final_answer") or insight_text or "No insights available."

        # Step 3: Optional chart
        data_rows: List[Dict[str, Any]] = last_rows if isinstance(last_rows, list) else []
        data_columns: List[str] = list(data_rows[0].keys()) if data_rows else []
        chart_json, chart_library, chart_type = maybe_build_chart(prompt_name_for_chart, input_data.query, data_rows)

        return ChatResponse(
            output=str(final_output),
            chart=chart_json,
            chart_type=chart_type,
            chart_library=chart_library,
            data_columns=data_columns,
            data_rows=data_rows
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_insight_api error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

async def get_topic_api(
    input_data: ChatHistoryInput,
    x_api_key: APIKey = Depends(get_api_key)
) -> ChatResponse:
    """Get topic from chat history."""
    try:
        topic = await telkomllm_generate_topic(
            prompt=generate_topic_prompt,
            user_query=input_data.chat_history or ""
        )
        logger.debug(f"[Debug] Topic generated from chat history: {topic}")
        return ChatResponse(output=str(topic))
        logger.debug(f"[Debug] Topic generated from chat history: {topic}")
    except Exception as e:
        logger.error(f"get_topic_api error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_recommendation_question(
    input_data: ChatHistoryInput,
    x_api_key: APIKey = Depends(get_api_key)
) -> ChatResponse:
    """Get one recommended follow-up question from chat history."""
    try:
        rec_q = await telkomllm_generate_recommendation_question(
            prompt=recommendation_question_prompt,
            chat_history=input_data.chat_history or ""
        )
        logger.info(f"[Agentic] Generated Recommendation Question: {rec_q}")
        return ChatResponse(output=str(rec_q))
    except Exception as e:
        logger.error(f"get_recommendation_question error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def health_check() -> Dict[str, str]:
    """Health check endpoint body."""
    return {"status": "ok"}