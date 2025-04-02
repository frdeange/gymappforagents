import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from backend.configuration.config import Config

# Configure logger
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Resource to identify this service
resource = Resource(attributes={
    SERVICE_NAME: "gymappbackend"
})

def setup_azure_monitor():
    """Set up Azure Monitor using OpenTelemetry."""
    try:
        # Create a TracerProvider
        trace_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(trace_provider)
        
        # Create an Azure Monitor exporter
        azure_exporter = AzureMonitorTraceExporter(
            connection_string=Config.APPLICATIONINSIGHTS_CONNECTION_STRING
        )
        
        # Add the exporter to the TracerProvider
        trace_provider.add_span_processor(
            BatchSpanProcessor(azure_exporter)
        )
        
        # Fix: Update the instrumentation call with the correct class
        HTTPXClientInstrumentor().instrument()
        
        # Get a tracer from the global registry
        tracer = trace.get_tracer(__name__)
        
        logger.info("Azure Monitor setup completed successfully")
        return tracer
    except Exception as e:
        logger.error(f"Failed to set up Azure Monitor: {str(e)}")
        # Return a no-op tracer if setup fails
        return trace.get_tracer(__name__)

# Initialize tracer
tracer = setup_azure_monitor()

def instrument_fastapi(app):
    """Instrument a FastAPI application for monitoring."""
    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI app instrumented successfully")
    except Exception as e:
        logger.error(f"Failed to instrument FastAPI app: {str(e)}")

def start_span(name, context=None, kind=None, attributes=None):
    """Start a new trace span with the specified name and attributes."""
    return tracer.start_as_current_span(name, context=context, kind=kind, attributes=attributes)

def log_event(event_name, properties=None):
    """Log a custom event to Azure Monitor."""
    try:
        with tracer.start_as_current_span(event_name) as span:
            if properties:
                for key, value in properties.items():
                    span.set_attribute(key, str(value))
        logger.info(f"Event: {event_name}", extra={"custom_properties": properties})
    except Exception as e:
        logger.error(f"Failed to log event '{event_name}': {str(e)}")

def log_exception(exception, properties=None):
    """Log an exception to Azure Monitor."""
    try:
        with tracer.start_as_current_span("exception") as span:
            span.record_exception(exception)
            if properties:
                for key, value in properties.items():
                    span.set_attribute(key, str(value))
            span.set_status(trace.StatusCode.ERROR, str(exception))
        logger.exception(f"Exception: {str(exception)}", exc_info=exception, 
                        extra={"custom_properties": properties})
    except Exception as e:
        logger.error(f"Failed to log exception: {str(e)}")

def log_metric(metric_name, value, properties=None):
    """Log a custom metric to Azure Monitor."""
    try:
        with tracer.start_as_current_span(f"metric:{metric_name}") as span:
            span.set_attribute("metric.value", value)
            if properties:
                for key, val in properties.items():
                    span.set_attribute(key, str(val))
        logger.info(f"Metric: {metric_name}={value}", 
                   extra={"custom_properties": properties})
    except Exception as e:
        logger.error(f"Failed to log metric '{metric_name}': {str(e)}")