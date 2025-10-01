import os
import sys
import warnings
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.security.api_key import APIKey
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv
from loguru import logger

# Project modules
from security import get_api_key, SecurityHeadersMiddleware
from utils import load_initial_data
from model import QueryInput, ChatHistoryInput, ChatResponse

# Route handlers
from routes import (
    get_insight_api,
    get_topic_api,
    get_recommendation_question,
    health_check,
)


# Init
load_dotenv(override=True)
warnings.filterwarnings("ignore", category=UserWarning)


# Logging
logger.remove()
logger.add(sys.stderr, level="DEBUG")
os.makedirs("log", exist_ok=True)
logger.add("log/CFU_Insight_Bot.log", rotation="100 MB", level="INFO")


# Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    load_initial_data()
    logger.info("Application startup complete.")
    yield
    logger.info("Application shutting down.")


# FastAPI app
app = FastAPI(
    title="CFU WIB INSIGHT BOT",
    description="CFU WIB Insight Bot services using FastAPI",
    version="1.0.0",
    lifespan=lifespan,
)


# Middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["DELETE", "GET", "POST", "PUT"],
    allow_headers=["*"],
)


# API endpoints
@app.post("/CFU_Insight/get_insight_api", response_model=ChatResponse, tags=["Insights"])
async def insight_api(input_data: QueryInput, x_api_key: APIKey = Depends(get_api_key)):
    return await get_insight_api(input_data, x_api_key)

@app.post("/CFU_Insight/get_topic", response_model=ChatResponse, tags=["Topic & Recommendation"])
async def topic_api(input_data: ChatHistoryInput, x_api_key: APIKey = Depends(get_api_key)):
    return await get_topic_api(input_data, x_api_key)

@app.post("/CFU_Insight/get_recommendation_question", response_model=ChatResponse, tags=["Topic & Recommendation"])
async def recommendation_question(input_data: ChatHistoryInput, x_api_key: APIKey = Depends(get_api_key)):
    return await get_recommendation_question(input_data, x_api_key)

@app.get("/ht", tags=["Health"])
async def ht():
    return await health_check()


# Entrypoint
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8123")), workers=int(os.getenv("WORKERS", "1")))