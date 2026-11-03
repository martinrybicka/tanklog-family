FROM python:3.14.10-slim-bookworm@sha256:516b51cb9db2ef061e465c803e50f64361b82cefd91e525b889b967b83e83527 AS ocr-build
RUN rm -f /etc/apt/sources.list.d/debian.sources \
    && printf 'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20261103T000000Z bookworm main\n' > /etc/apt/sources.list \
    && apt-get update && apt-get install --no-install-recommends -y cmake build-essential pkg-config libleptonica-dev \
    && rm -rf /var/lib/apt/lists/*
COPY infra/ocr/build_inputs.py infra/ocr/dependencies.lock.json /build-inputs/
RUN python /build-inputs/build_inputs.py \
    && cmake -S /tmp/ocr-source/tesseract-5.5.4 -B /tmp/ocr-build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/ocr -DBUILD_TRAINING_TOOLS=OFF -DGRAPHICS_DISABLED=ON -DOPENMP_BUILD=OFF -DDISABLE_ARCHIVE=ON -DDISABLE_CURL=ON \
    && cmake --build /tmp/ocr-build --parallel 2 \
    && cmake --install /tmp/ocr-build

FROM python:3.14.10-slim-bookworm@sha256:516b51cb9db2ef061e465c803e50f64361b82cefd91e525b889b967b83e83527 AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv UV_NO_MANAGED_PYTHON=1 PATH="/opt/venv/bin:$PATH"
RUN rm -f /etc/apt/sources.list.d/debian.sources \
    && printf 'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20261103T000000Z bookworm main\n' > /etc/apt/sources.list \
    && apt-get update && apt-get install --no-install-recommends -y liblept5 libstdc++6 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ocr-build /opt/ocr /opt/ocr
RUN printf '/opt/ocr/lib\n' > /etc/ld.so.conf.d/tanklog-ocr.conf && ldconfig
COPY infra/ocr/dependencies.lock.json /opt/ocr/dependencies.lock.json
ENV OCR_BINARY=/opt/ocr/bin/tesseract OCR_DATA=/opt/ocr/tessdata OCR_LOCK_FILE=/opt/ocr/dependencies.lock.json
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
