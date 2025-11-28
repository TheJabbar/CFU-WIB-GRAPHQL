import os
import sys
import warnings
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv
from loguru import logger
from security import SecurityHeadersMiddleware, get_api_key
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

# GraphQL router setup with WebSocket support for subscriptions
graphql_app = GraphQLRouter(
    schema,
    graphiql=True,
    subscription_protocols=[
        "graphql-transport-ws",
        "graphql-ws"
    ]
)

app.include_router(
    graphql_app,
    prefix="/cfu-insight",
    tags=["GraphQL"]
)

# Add middleware for API key validation
@app.middleware("http")
async def validate_api_key(request: Request, call_next):
    if request.url.path.startswith("/cfu-insight"):
        # Skip validation for health check
        if request.url.path == "/ht":
            return await call_next(request)

        # For websocket connections, allow the connection to be established
        # but authentication will be handled by GraphQL subscription validation
        if "upgrade" in request.headers and request.headers["upgrade"].lower() == "websocket":
            # WebSocket upgrade request - allow it to pass through to GraphQL
            # The authentication will be handled in GraphQL subscription resolvers
            pass
        else:
            # Validate API key for regular HTTP requests
            api_key = request.headers.get("x-api-key")
            if not api_key:
                # If no API key provided, call get_api_key with None to trigger validation error
                await get_api_key(None)
            else:
                # Validate the provided API key
                await get_api_key(api_key)

    response = await call_next(request)
    return response

# Health check endpoint
@app.get("/ht", tags=["Health"])
async def health_check_endpoint():
    from routes import health_check
    return await health_check()

# Entrypoint
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "5123")), workers=int(os.getenv("WORKERS", "1")))