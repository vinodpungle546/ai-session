# payee-demo container.
#
# This image runs on Azure Container Apps with scale-to-zero, so COLD START is
# the thing to optimise: every megabyte and every deferred initialisation is
# paid by the first user after the app scales back up. Two consequences drive
# the layout below:
#
#   1. The Chroma index -- and the ~79 MB ONNX embedding model it downloads on
#      first use -- is built at BUILD time. If it were built lazily, the first
#      request after a cold start would wait for a model download.
#   2. Dependencies are installed before application code is copied, so edits
#      to app/ or ui/ reuse the (large, slow) dependency layer.
#
# Image size note: requirements.txt includes arize-phoenix, which is the
# Phoenix *server*. Nothing in this container imports it -- tracing exports via
# opentelemetry-exporter-otlp, and Container Apps deployments send traces to
# Langfuse. Dropping it removes 82 transitive packages (~223 MB, including
# scipy and botocore). Build with the slim set when you do not need parity with
# the local dev environment:
#
#     docker build --build-arg REQUIREMENTS=requirements-container.txt -t payee-demo .

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# --- dependencies (cached independently of application code) ---
ARG REQUIREMENTS=requirements.txt
COPY requirements.txt requirements-container.txt ./
RUN pip install --no-cache-dir -r "${REQUIREMENTS}"

# --- non-root user -------------------------------------------------------
# Created before the index is built so that the Chroma store and the ONNX
# model cache under $HOME are written by, and owned by, the runtime user.
RUN useradd --create-home --uid 10001 appuser

COPY app/ ./app/
COPY ui/ ./ui/
# Pins the Streamlit theme. Without it the theme follows the viewer's OS
# setting, and a dark theme repaints the text inside the custom light panels.
COPY .streamlit/ ./.streamlit/
COPY data/ ./data/
COPY evals/ ./evals/

RUN chown -R appuser:appuser /app
USER appuser
ENV HOME=/home/appuser

# --- build the retrieval index at BUILD time, not at container start -----
# Writes /app/chroma_store and caches the embedding model in $HOME/.cache.
# app/config.py resolves paths from its own location, so this matches what
# app/rag.py looks for at runtime regardless of working directory.
RUN python -c "from app.rag import build_index; c = build_index(); print(f'chroma index built: {c.count()} chunks')"

# No secrets are baked in: MODEL_API_KEY, LANGFUSE_* and every feature flag
# come from the environment at run time. app/config.py tolerates all of them
# being absent.
EXPOSE 8000

# Uses the stdlib rather than installing curl, to keep the image smaller.
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/_stcore/health', timeout=4).status == 200 else 1)"

CMD ["streamlit", "run", "ui/streamlit_app.py", \
     "--server.port=8000", "--server.address=0.0.0.0", "--server.headless=true"]
