FROM python:3.14.10-slim-bookworm@sha256:516b51cb9db2ef061e465c803e50f64361b82cefd91e525b889b967b83e83527 AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv UV_NO_MANAGED_PYTHON=1 PATH="/opt/venv/bin:$PATH"
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.6 \
    && groupadd --gid 10001 tanklog \
    && useradd --uid 10001 --gid tanklog --create-home tanklog
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN chown -R tanklog:tanklog /app
USER tanklog

FROM base AS production
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "30", "--access-logfile", "-", "--access-logformat", "%(m)s %(U)s %(s)s %(D)s"]

FROM base AS development
USER root
RUN uv sync --frozen --no-install-project && chown -R tanklog:tanklog /opt/venv
USER tanklog
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
