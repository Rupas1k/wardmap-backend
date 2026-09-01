FROM rust:1-bookworm AS rust-toolchain


FROM python:3.13-slim-trixie AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    CARGO_HOME=/usr/local/cargo \
    RUSTUP_HOME=/usr/local/rustup \
    PATH="/usr/local/cargo/bin:$PATH"

COPY --from=rust-toolchain /usr/local/cargo /usr/local/cargo
COPY --from=rust-toolchain /usr/local/rustup /usr/local/rustup

RUN apt-get update \
    && apt-get install --yes --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY replay_parser ./replay_parser
RUN python -m pip wheel --wheel-dir /wheels ./replay_parser

COPY requirements.txt .
RUN sed -e '/^-e \.\/replay_parser/d' -e '/^pytest/d' requirements.txt > requirements-container.txt \
    && python -m pip wheel --wheel-dir /wheels --requirement requirements-container.txt


FROM python:3.13-slim-trixie AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv /opt/venv \
    && addgroup --system app \
    && adduser --system --ingroup app --home /app app

COPY --from=builder /wheels /wheels
RUN python -m pip install /wheels/* \
    && rm -rf /wheels

WORKDIR /app
COPY --chown=app:app dota2wardmap ./dota2wardmap

USER app

EXPOSE 5000

CMD ["gunicorn", "--config", "python:dota2wardmap.gunicorn_config", "dota2wardmap:create_app()"]
