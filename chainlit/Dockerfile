FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy requirements first for better caching
COPY requirements.txt .

# Create virtual environment and install dependencies
RUN uv venv && \
    . .venv/bin/activate && \
    uv pip install -r requirements.txt

# Copy application code
COPY app.py ./
COPY .env ./

# Copy Chainlit configuration
COPY .chainlit/ ./.chainlit/
COPY chainlit.md ./

# Expose the port
EXPOSE 8899

# Run the Chainlit application
CMD ["/bin/bash", "-c", "source .venv/bin/activate && chainlit run app.py --port 8899 --host 0.0.0.0"]