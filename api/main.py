import os
import sys
import warnings
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv
from loguru import logger
from security import SecurityHeadersMiddleware
from utils import load_initial_data
from strawberry.fastapi import GraphQLRouter
from graphql_schema import schema

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
    title="CFU WIB INSIGHT BOT API (GraphQL)",  
    description="CFU WIB Insight Bot services using a FastAPI backend with a GraphQL layer.", 
    version="2.0.0",
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

# GraphQL router setup
graphql_app = GraphQLRouter(
    schema,
    graphiql=True  # Enable GraphiQL interface for debugging
)

app.include_router(
    graphql_app,
    prefix="/cfu-insight",
    tags=["GraphQL"]
)

# Health check endpoint
@app.get("/ht", tags=["Health"])
async def health_check_endpoint():
    from routes import health_check
    return await health_check()

# Entrypoint
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8123")), workers=int(os.getenv("WORKERS", "1")))