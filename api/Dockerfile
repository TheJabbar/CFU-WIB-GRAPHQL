FROM playcourt/jenkins:python-3.11.0 AS builder

USER root

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    git \
    build-essential \
    python3-dev \
    libffi-dev \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=true \
    UV_SYSTEM_PYTHON=true \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --compile-bytecode --no-install-project

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --compile-bytecode && \
    uv pip uninstall setuptools wheel pip --system

FROM playcourt/jenkins:python-3.11.0

USER root

RUN apt-get update && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# Install a shell
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY lib ./lib
COPY *.py ./
COPY entrypoints.sh ./
COPY .env ./

RUN sed -i 's/\r$//' /app/entrypoints.sh

RUN chmod +x /app/entrypoints.sh
RUN mkdir -p /app/log /app/data \
    && groupadd -r user \
    && useradd -r -g user user \
    && chown -R user:user /app /app/log /app/data \
    && chmod -R 777 /app/log /app/data \
    && pip uninstall -y setuptools wheel pip

# Copy the environment, but not the source code
COPY --from=minio/mc --chown=user:user /usr/bin/mc /usr/bin/mc
COPY --from=builder --chown=user:user /app/.venv /app/.venv

USER user

ENTRYPOINT ["/bin/bash", "/app/entrypoints.sh"]