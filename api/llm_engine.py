# app/llm_engine.py
import os
import httpx
from dotenv import load_dotenv
from loguru import logger

load_dotenv('.env')

URL_CUSTOM_LLM = os.getenv('URL_CUSTOM_LLM')
TOKEN_CUSTOM_LLM = os.getenv('TOKEN_CUSTOM_LLM')

async def make_async_api_call(url, token, payload):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-api-key": token
    }
    async with httpx.AsyncClient(timeout=120.0, verify=False) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                error_message = response.text
                print(f"API Error {response.status_code}: {error_message}")
                return {"error": f"API call failed with status {response.status_code}"}
        except Exception as e:
            logger.error(f"Exception during API call: {e}")
            return {"error": str(e)}

async def telkomllm_select_table(prompt, tables_list, prompt_list, user_query):
    payload = {
        "model": "telkom-ai-instruct",
        "messages": [{"role": "system", "content": prompt.format(tables_list=tables_list, prompt_list=prompt_list, user_query=user_query)}],
        "max_tokens": 2000, "temperature": 0, "stream": False
    }
    return await make_async_api_call(URL_CUSTOM_LLM, TOKEN_CUSTOM_LLM, payload)

async def telkomllm_generate_sql(prompt, table_name, columns_list, first_row, user_query, instruction_prompt):
    payload = {
        "model": "telkom-ai-instruct",
        "messages": [{"role": "system", "content": prompt.format(table_name=table_name, columns_list=columns_list, first_row=first_row, user_query=user_query, instruction_prompt=instruction_prompt)}],
        "max_tokens": 10000, "temperature": 0, "stream": False
    }
    return await make_async_api_call(URL_CUSTOM_LLM, TOKEN_CUSTOM_LLM, payload)

async def telkomllm_infer_sql(prompt, user_query, table_name, instruction_prompt, column_list, table_data):
    payload = {
        "model": "telkom-ai-instruct",
        "messages": [{"role": "system", "content": prompt.format(table_name=table_name, column_list=column_list, table_data=table_data, instruction_prompt=instruction_prompt, user_query=user_query)}],
        "max_tokens": 28000, "temperature": 0, "stream": False
    }
    return await make_async_api_call(URL_CUSTOM_LLM, TOKEN_CUSTOM_LLM, payload)

async def telkomllm_fix_sql(prompt, columns_list, error_sql, error_message):
    payload = {
        "model": "telkom-ai-instruct",
        "messages": [{"role": "system", "content": prompt.format(columns_list=columns_list, error_sql=error_sql, error_message=error_message)}],
        "max_tokens": 5000, "temperature": 0, "stream": False
    }
    return await make_async_api_call(URL_CUSTOM_LLM, TOKEN_CUSTOM_LLM, payload)

async def telkomllm_main_agent(agent_prompt, user_query, chat_history="", tools_answer=""):
    payload = {
        "model": "telkom-ai-instruct",
        "messages": [{"role": "system","content": agent_prompt.format(user_query=user_query, chat_history=chat_history or "", tools_answer=tools_answer or "")}],
        "max_tokens": 4000, "temperature": 0, "stream": False
    }
    return await make_async_api_call(URL_CUSTOM_LLM, TOKEN_CUSTOM_LLM, payload)

async def telkomllm_generate_topic(prompt, user_query: str):
    payload = {
        "model": "telkom-ai-instruct",
        "messages": [{"role": "system", "content": prompt.format(user_query=user_query)}],
        "max_tokens": 128, "temperature": 0, "stream": False
    }
    return await make_async_api_call(URL_CUSTOM_LLM, TOKEN_CUSTOM_LLM, payload)

async def telkomllm_generate_recommendation_question(prompt, chat_history: str):
    payload = {
        "model": "telkom-ai-instruct",
        "messages": [{"role": "system", "content": prompt.format(chat_history=chat_history or "")}],
        "max_tokens": 256, "temperature": 0, "stream": False
    }
    return await make_async_api_call(URL_CUSTOM_LLM, TOKEN_CUSTOM_LLM, payload)

async def telkomllm_greeting_and_general(prompt, user_query: str):
    payload = {
        "model": "telkom-ai-instruct",
        "messages": [{"role": "system", "content": prompt.format(user_query=user_query)}],
        "max_tokens": 2000, "temperature": 0, "stream": False
    }
    return await make_async_api_call(URL_CUSTOM_LLM, TOKEN_CUSTOM_LLM, payload)