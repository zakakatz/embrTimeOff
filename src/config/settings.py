"""Application configuration settings."""

import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import List, Optional


@dataclass
class PaginationSettings:
    """Pagination configuration."""
    
    default_page_size: int = 20
    max_page_size: int = 100
    min_page_size: int = 1


@dataclass
class SearchSettings:
    """Search configuration."""
    
    # Default search limit
    default_limit: int = 50
    max_limit: int = 200
    
    # Fuzzy matching settings
    fuzzy_enabled: bool = True
    fuzzy_min_score: float = 0.6
    
    # Fields to search by default
    default_search_fields: List[str] = field(default_factory=lambda: [
        "first_name",
        "last_name",
        "preferred_name",
        "email",
        "employee_id",
        "job_title",
    ])
    
    # Suggestion settings
    suggestion_limit: int = 5
    suggestion_min_query_length: int = 2


@dataclass
class AccessControlSettings:
    """Access control configuration."""
    
    # Whether to enforce organizational hierarchy in searches
    enforce_hierarchy: bool = True
    
    # Maximum depth of organizational hierarchy to traverse
    max_hierarchy_depth: int = 10
    
    # Roles that can see all employees regardless of hierarchy
    admin_roles: List[str] = field(default_factory=lambda: ["admin", "hr_manager"])


@dataclass
class Settings:
    """Main application settings."""
    
    # Application info
    app_name: str = "Employee Management API"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # Database
    database_url: str = ""
    database_pool_size: int = 5
    database_max_overflow: int = 10
    
    # Pagination
    pagination: PaginationSettings = field(default_factory=PaginationSettings)
    
    # Search
    search: SearchSettings = field(default_factory=SearchSettings)
    
    # Access Control
    access_control: AccessControlSettings = field(default_factory=AccessControlSettings)
    
    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables."""
        return cls(
            app_name=os.getenv("APP_NAME", "Employee Management API"),
            app_version=os.getenv("APP_VERSION", "1.0.0"),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            database_url=os.getenv(
                "DATABASE_URL",
                f"postgresql://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', '')}@"
                f"{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/"
                f"{os.getenv('DB_NAME', 'embi')}"
            ),
            database_pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
            database_max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
            pagination=PaginationSettings(
                default_page_size=int(os.getenv("PAGINATION_DEFAULT_SIZE", "20")),
                max_page_size=int(os.getenv("PAGINATION_MAX_SIZE", "100")),
            ),
            search=SearchSettings(
                default_limit=int(os.getenv("SEARCH_DEFAULT_LIMIT", "50")),
                max_limit=int(os.getenv("SEARCH_MAX_LIMIT", "200")),
                fuzzy_enabled=os.getenv("SEARCH_FUZZY_ENABLED", "true").lower() == "true",
            ),
        )


# Singleton settings instance
_settings: Optional[Settings] = None


@lru_cache()
def get_settings() -> Settings:
    """Get application settings (cached)."""
    global _settings
    if _settings is None:
        _settings = Settings.from_env()
    return _settings


def reset_settings() -> None:
    """Reset settings (for testing)."""
    global _settings
    _settings = None
    get_settings.cache_clear()

