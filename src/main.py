"""Main application entry point for the Employee Management API."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from src.database.database import DatabaseConfig, dispose_engine, get_engine
from src.routes.api import api_error_handler, api_router
from src.utils.errors import APIError, ValidationError


# =============================================================================
# Logging Configuration
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Application Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup/shutdown events."""
    # Startup
    logger.info("Starting Employee Management API...")
    
    # Initialize database connection
    config = DatabaseConfig.from_env()
    logger.info(f"Connecting to database at {config.host}:{config.port}/{config.database}")
    get_engine(config)
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Employee Management API...")
    dispose_engine()
    logger.info("Application shutdown complete")


# =============================================================================
# Application Factory
# =============================================================================

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="Employee Management API",
        description=(
            "API for managing employee profiles with comprehensive "
            "CRUD operations, validation, and audit logging."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register routes
    app.include_router(api_router)
    
    # Register exception handlers
    app.add_exception_handler(APIError, api_error_handler)
    
    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_handler(
        request: Request,
        exc: PydanticValidationError,
    ) -> JSONResponse:
        """Convert Pydantic validation errors to structured response."""
        field_errors = []
        for error in exc.errors():
            loc = ".".join(str(x) for x in error["loc"])
            field_errors.append({
                "field": loc,
                "message": error["msg"],
                "code": error["type"],
            })
        
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "message": "Request validation failed",
                    "code": "validation_error",
                    "field_errors": field_errors,
                }
            },
        )
    
    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Handle unexpected exceptions."""
        logger.exception("Unexpected error occurred")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": "An unexpected error occurred",
                    "code": "internal_error",
                }
            },
        )
    
    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """Check application health."""
        return {"status": "healthy", "version": "1.0.0"}
    
    return app


# =============================================================================
# Application Instance
# =============================================================================

app = create_app()


# =============================================================================
# Development Server
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )

