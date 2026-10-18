# Reproducible runtime: same Python, same locked dependencies on any machine.
FROM ghcr.io/astral-sh/uv:0.6.17-python3.12-bookworm-slim

# git: used by scripts/download_data.sh
RUN apt-get update \
    && apt-get install -y --no-install-recommends git make \
    && rm -rf /var/lib/apt/lists/*

# The venv lives outside /app so bind-mounting the project does not hide it.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install dependencies first (cached layer; only rebuilt when the lock file changes).
COPY pyproject.toml uv.lock .python-version README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Then install the project itself.
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

CMD ["pytest", "-q"]
