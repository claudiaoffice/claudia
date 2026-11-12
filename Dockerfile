# syntax=docker/dockerfile:1
#
# One image for all Claudia app servers (computes, composes, creates).
# Which app a container runs is chosen at start-up with CLAUDIA_APP; see docker/entrypoint.sh.
#
#   docker build -t claudia-server .
#   docker run -p 8765:8765 -v claudia-computes:/data claudia-server                          # computes
#   docker run -p 8766:8765 -v claudia-composes:/data -e CLAUDIA_APP=composes claudia-server
#   docker build --build-arg WITH_OPENVINO=true -t claudia-server:ai .                        # with --ai support

# ---- web: the Nuxt single-page app, built to static files --------------------------------------
# It links the layout library (../layout, D902), so both folders are copied; `npm run build` also copies the
# pinned HarfBuzz WebAssembly into the app (D903).
FROM node:22-bookworm-slim AS web
WORKDIR /build/web
COPY layout/ /build/layout/
COPY web/package.json web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY web/ ./
RUN npm run build

# ---- python: the workspace packages and their locked dependencies, in one virtual environment --
FROM python:3.14-slim-bookworm AS python
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages packages
# WITH_OPENVINO=true adds the language model runtime for the server's --ai option (large; off by default).
ARG WITH_OPENVINO=false
RUN --mount=type=cache,target=/root/.cache/uv \
    set -- --locked --no-dev --no-editable --package claudia-server; \
    if [ "$WITH_OPENVINO" = "true" ]; then set -- "$@" --extra openvino; fi; \
    uv sync "$@"
# The starter set of open fonts, pinned by SHA-256 (D905): what the clients lay out and print with.
RUN /app/.venv/bin/python -m claudia_fonts fetch /app/fonts

# ---- runtime ----------------------------------------------------------------------------------
FROM python:3.14-slim-bookworm
RUN groupadd --system --gid 10001 claudia \
    && useradd --system --uid 10001 --gid claudia --no-create-home claudia \
    && mkdir -p /data/documents /data/state \
    && chown -R claudia:claudia /data

COPY --from=python /app/.venv /app/.venv
COPY --from=web /build/web/.output/public /app/web
COPY --from=python /app/fonts /app/fonts
COPY --chmod=755 docker/entrypoint.sh /app/entrypoint.sh
COPY docker/healthcheck.py /app/healthcheck.py

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    CLAUDIA_STATE_DIR=/data/state

USER 10001:10001
WORKDIR /data
# /data/documents: the documents, each sealed (encrypted) by its people's passwords;
# /data/state: the server's own TLS certificate. Use one volume per running app.
VOLUME /data
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "/app/healthcheck.py"]

ENTRYPOINT ["/app/entrypoint.sh"]
