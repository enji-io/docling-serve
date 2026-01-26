"""
BentoML service definition for Docling Serve.

This service mounts the FastAPI application from docling_serve.app:create_app()
as an ASGI application, allowing it to run on BentoML/BentoCloud.
"""

import bentoml
from docling_serve.app import create_app

# Create the FastAPI application instance
# This is safe to do at module level as create_app() only sets up routes
# and doesn't initialize heavy resources (that happens in lifespan)
fastapi_app = create_app()

# Define the BentoML service
@bentoml.service(
    name="docling-serve",
    traffic={"timeout": 600},  # 10 minutes timeout for long-running document processing
)
@bentoml.asgi_app(fastapi_app, path="/")
class DoclingServeService:
    """
    BentoML service wrapper for Docling Serve FastAPI application.
    
    This service mounts the entire FastAPI application, preserving all existing
    routes, WebSocket endpoints, and functionality. The FastAPI app's lifespan
    context manager handles initialization and cleanup of the orchestrator and
    background tasks.
    """
    pass
