"""OpenTelemetry tracing that exports to Arize Phoenix or Langfuse.

Versions this file was written against and verified on (read from the installed
packages, not from memory):

    openinference-instrumentation-langchain   0.1.74
    opentelemetry-sdk                         1.44.0
    opentelemetry-exporter-otlp               1.44.0
    arize-phoenix                             20.9.0
    langfuse                                  4.15.1

The instrumentation is identical for both backends. Only the OTLP destination
and its auth headers differ, so switching TELEMETRY_BACKEND changes where spans
go and nothing else. Both endpoints speak OTLP over HTTP, which is why this uses
the http exporter rather than the gRPC one -- PHOENIX_ENDPOINT already carries
the /v1/traces path.

API notes for the installed versions:
  * LangChainInstrumentor().instrument(tracer_provider=...) -- takes **kwargs,
    and exposes is_instrumented_by_opentelemetry for idempotency.
  * A trace id is only meaningful inside an active span, so run() in
    app/graph.py opens a root span and reads the id from within it.
"""

from __future__ import annotations

import base64
import logging
import os

logger = logging.getLogger(__name__)

SERVICE_NAME = "payee-demo"
DEFAULT_PHOENIX_ENDPOINT = "http://localhost:6006/v1/traces"

# Module state, so a second call is a no-op rather than a second exporter.
_initialised = False
_tracer_provider = None


def _phoenix_target() -> tuple[str, dict]:
    endpoint = os.getenv("PHOENIX_ENDPOINT", DEFAULT_PHOENIX_ENDPOINT)
    return endpoint, {}


def _langfuse_target() -> tuple[str, dict]:
    """Langfuse ingests OTLP at /api/public/otel/v1/traces with basic auth."""
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com").rstrip("/")
    public = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    secret = os.getenv("LANGFUSE_SECRET_KEY", "")
    token = base64.b64encode(f"{public}:{secret}".encode()).decode()
    return f"{host}/api/public/otel/v1/traces", {"Authorization": f"Basic {token}"}


def init_telemetry(force: bool = False):
    """Configure tracing and instrument LangChain/LangGraph.

    Idempotent and non-fatal by design: if the collector is unreachable or a
    library has moved, this logs a warning and returns None so the demo still
    runs with tracing broken.

    Returns the TracerProvider, or None if telemetry could not be set up.
    """
    global _initialised, _tracer_provider
    if _initialised and not force:
        return _tracer_provider

    backend = os.getenv("TELEMETRY_BACKEND", "phoenix").strip().lower()

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        if backend == "langfuse":
            endpoint, headers = _langfuse_target()
        else:
            if backend != "phoenix":
                logger.warning(
                    "Unknown TELEMETRY_BACKEND %r; falling back to phoenix.", backend
                )
                backend = "phoenix"
            endpoint, headers = _phoenix_target()

        provider = TracerProvider(
            resource=Resource.create(
                {"service.name": SERVICE_NAME, "telemetry.backend": backend}
            )
        )
        # Batch export: the exporter never blocks a graph run, so an unreachable
        # collector costs nothing at request time.
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, headers=headers))
        )
        trace.set_tracer_provider(provider)

        from openinference.instrumentation.langchain import LangChainInstrumentor

        instrumentor = LangChainInstrumentor()
        # Guard against double-registration across reloads (Streamlit re-runs
        # this module on every interaction).
        if getattr(instrumentor, "is_instrumented_by_opentelemetry", False):
            instrumentor.uninstrument()
        instrumentor.instrument(tracer_provider=provider)

        _tracer_provider = provider
        _initialised = True
        logger.info("Telemetry initialised: backend=%s endpoint=%s", backend, endpoint)
        return provider

    except Exception:
        # Never raise. A demo with broken tracing is still a demo.
        logger.warning(
            "Telemetry setup failed; continuing without tracing.", exc_info=True
        )
        _initialised = True  # do not retry on every run
        return None


def get_tracer(name: str = SERVICE_NAME):
    """Return a tracer; safe to call whether or not telemetry initialised."""
    from opentelemetry import trace

    return trace.get_tracer(name)


def current_trace_id() -> str | None:
    """The active trace id as a 32-char hex string, or None outside a span.

    The UI shows this so a run can be found in Phoenix or Langfuse.
    """
    try:
        from opentelemetry import trace

        ctx = trace.get_current_span().get_span_context()
        if getattr(ctx, "is_valid", False) and ctx.trace_id:
            return format(ctx.trace_id, "032x")
    except Exception:
        logger.debug("Could not read current trace id.", exc_info=True)
    return None


def shutdown_telemetry() -> None:
    """Flush pending spans. Worth calling before a short-lived process exits."""
    if _tracer_provider is not None:
        try:
            _tracer_provider.shutdown()
        except Exception:
            logger.debug("Telemetry shutdown failed.", exc_info=True)
