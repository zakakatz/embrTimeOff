"""Main application entry point for the Employee Management API."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from src.api.employees import employee_import_export_router, import_export_error_handler
from src.api.employee_org import employee_org_router
from src.api.employee_audit import employee_audit_router
from src.api.employee_import_upload import employee_import_upload_router
from src.api.employee_import_validate import employee_import_validate_router
from src.api.employee_profile import employee_profile_router
from src.api.employee_import_execute import employee_import_execute_router
from src.api.employee_profile_update import employee_profile_update_router
from src.api.employee_import_errors import employee_import_errors_router
from src.api.employee_profile_history import employee_profile_history_router
from src.api.employee_dashboard import employee_dashboard_router
from src.api.employee_import_config import employee_import_config_router
from src.api.employee_directory import employee_directory_router
from src.api.admin_org_structure import admin_org_structure_router
from src.api.org_chart import org_chart_router
from src.api.directory_analytics import directory_analytics_router
from src.api.admin_locations import admin_locations_router
from src.api.time_off_requests import time_off_router
from src.api.privacy_controls import privacy_controls_router
from src.api.department_assignments import department_assignments_router
from src.api.time_off_approval import time_off_approval_router
from src.api.employment_types import employment_types_router
from src.api.search import router as search_router
from src.api.tasks import router as tasks_router
from src.api.documents import documents_router
from src.api.email import email_router
from src.api.approval_management import approval_management_router
from src.api.approval_context import approval_context_router
from src.api.policy_management import policy_management_router
from src.api.balance_inquiry import balance_inquiry_router
from src.api.delegate_management import delegate_management_router
from src.api.team_balance import team_balance_router
from src.api.approval_analytics import approval_analytics_router
from src.api.sick_leave_schedule import sick_leave_schedule_router
from src.api.time_off_submission import time_off_submission_router
from src.api.balance_projections import balance_projections_router
from src.api.holiday_calendar import holiday_calendar_router
from src.api.time_off_balances import time_off_balances_router
from src.api.workflow_analytics import workflow_analytics_router
from src.api.organizational_analytics import organizational_analytics_router
from src.api.employee_policy_info import employee_policy_info_router
from src.api.envelope_management import envelope_router
from src.api.balance_analytics import balance_analytics_router
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
    app.include_router(employee_import_export_router)
    app.include_router(employee_org_router)
    app.include_router(employee_audit_router)
    app.include_router(employee_import_upload_router)
    app.include_router(employee_import_validate_router)
    app.include_router(employee_profile_router)
    app.include_router(employee_import_execute_router)
    app.include_router(employee_profile_update_router)
    app.include_router(employee_import_errors_router)
    app.include_router(employee_profile_history_router)
    app.include_router(employee_dashboard_router)
    app.include_router(employee_import_config_router)
    app.include_router(employee_directory_router)
    app.include_router(admin_org_structure_router)
    app.include_router(org_chart_router)
    app.include_router(directory_analytics_router)
    app.include_router(admin_locations_router)
    app.include_router(time_off_router)
    app.include_router(privacy_controls_router)
    app.include_router(department_assignments_router)
    app.include_router(time_off_approval_router)
    app.include_router(employment_types_router)
    app.include_router(search_router)
    app.include_router(tasks_router)
    app.include_router(documents_router)
    app.include_router(email_router)
    app.include_router(approval_management_router)
    app.include_router(approval_context_router)
    app.include_router(policy_management_router)
    app.include_router(balance_inquiry_router)
    app.include_router(delegate_management_router)
    app.include_router(team_balance_router)
    app.include_router(approval_analytics_router)
    app.include_router(sick_leave_schedule_router)
    app.include_router(time_off_submission_router)
    app.include_router(balance_projections_router)
    app.include_router(holiday_calendar_router)
    app.include_router(time_off_balances_router)
    app.include_router(workflow_analytics_router)
    app.include_router(organizational_analytics_router)
    app.include_router(employee_policy_info_router)
    app.include_router(envelope_router)
    app.include_router(balance_analytics_router)
    
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

