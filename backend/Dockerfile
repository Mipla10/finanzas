# Imagen del backend (plan 001 §6.4). Se construye desde docker compose (servicio api).
FROM python:3.12-slim

# uv, el mismo gestor de dependencias que en local (versión fija).
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Primero solo las dependencias: si no cambian, Docker reutiliza esta capa.
COPY pyproject.toml uv.lock README.md .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
RUN uv sync --frozen --no-dev

# Sin privilegios de administrador dentro del contenedor.
RUN useradd --create-home --uid 10001 finanzas
USER finanzas

EXPOSE 8000

# Migrar y luego servir. `exec` deja al servidor recibir las señales de parada.
CMD ["sh", "-c", "alembic upgrade head && exec fastapi run src/finanzas/main.py --host 0.0.0.0 --port 8000"]
