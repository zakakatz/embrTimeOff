"""
Celery Application Entry Point

Main Celery application configuration with task discovery,
retry logic, and monitoring integration.
"""

import os
import logging
from typing import Any, List, Optional

from src.infrastructure.redis.celery_config import (
    CeleryConfig,
    create_celery_app,
    celery_app as configured_app,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Celery Application
# =============================================================================

# Use the pre-configured app or create a new one
celery_app = configured_app or create_celery_app()

# Auto-discover tasks from these modules
TASK_MODULES: List[str] = [
    "src.tasks.accrual_tasks",
    "src.tasks.email_tasks",
    "src.tasks.report_tasks",
]

if celery_app:
    # Configure task autodiscovery
    celery_app.autodiscover_tasks(TASK_MODULES)
    
    # Additional configuration
    celery_app.conf.update(
        # Task result settings
        task_track_started=True,
        task_send_sent_event=True,
        
        # Worker settings
        worker_send_task_events=True,
        
        # Enable remote control
        worker_enable_remote_control=True,
    )
    
    logger.info(f"Celery app configured with task modules: {TASK_MODULES}")


def get_celery_app() -> Optional[Any]:
    """Get the configured Celery application."""
    return celery_app


# =============================================================================
# Application Information
# =============================================================================

def get_app_info() -> dict:
    """Get Celery application information."""
    if not celery_app:
        return {"status": "disabled", "reason": "Celery not installed"}
    
    return {
        "status": "enabled",
        "broker": celery_app.conf.broker_url,
        "backend": celery_app.conf.result_backend,
        "timezone": celery_app.conf.timezone,
        "task_modules": TASK_MODULES,
        "worker_concurrency": celery_app.conf.worker_concurrency,
    }

