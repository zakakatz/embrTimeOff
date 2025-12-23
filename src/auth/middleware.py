"""
Authentication Middleware

Provides JWT token validation middleware for FastAPI to protect routes
and inject user session information into requests.
"""

import logging
from typing import Callable, List, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.jwt_manager import (
    JWTManager,
    TokenType,
    TokenValidationResult,
    UserSession,
    get_jwt_manager,
)

logger = logging.getLogger(__name__)

# HTTP Bearer security scheme
bearer_scheme = HTTPBearer(auto_error=False)


# =============================================================================
# Dependencies
# =============================================================================

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    jwt_manager: JWTManager = Depends(get_jwt_manager),
) -> UserSession:
    """
    Dependency to get the current authenticated user.
    
    Validates JWT token and returns user session.
    Raises 401 if token is missing or invalid.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    result = jwt_manager.validate_token(token, expected_type=TokenType.ACCESS)
    
    if not result.is_valid:
        error_detail = _get_error_detail(result)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    session = jwt_manager.get_user_session(token)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Store session in request state for access in route handlers
    request.state.user = session
    
    return session


async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    jwt_manager: JWTManager = Depends(get_jwt_manager),
) -> Optional[UserSession]:
    """
    Dependency to optionally get the current user.
    
    Returns None if no valid token provided, instead of raising 401.
    Useful for routes that work differently for authenticated vs anonymous users.
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(request, credentials, jwt_manager)
    except HTTPException:
        return None


def require_roles(*required_roles: str) -> Callable:
    """
    Dependency factory for role-based access control.
    
    Usage:
        @router.get("/admin")
        async def admin_route(user: UserSession = Depends(require_roles("admin"))):
            ...
    """
    async def dependency(
        user: UserSession = Depends(get_current_user),
    ) -> UserSession:
        if not any(role in user.roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role(s): {', '.join(required_roles)}",
            )
        return user
    
    return dependency


def require_permissions(*required_permissions: str) -> Callable:
    """
    Dependency factory for permission-based access control.
    
    Usage:
        @router.post("/users")
        async def create_user(user: UserSession = Depends(require_permissions("users:create"))):
            ...
    """
    async def dependency(
        user: UserSession = Depends(get_current_user),
    ) -> UserSession:
        if not all(perm in user.permissions for perm in required_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required permission(s): {', '.join(required_permissions)}",
            )
        return user
    
    return dependency


# =============================================================================
# Middleware
# =============================================================================

class AuthenticationMiddleware:
    """
    Authentication middleware for request processing.
    
    Validates JWT tokens in Authorization header and adds
    user session to request state.
    """
    
    def __init__(
        self,
        app,
        exclude_paths: Optional[List[str]] = None,
        jwt_manager: Optional[JWTManager] = None,
    ):
        self.app = app
        self.exclude_paths = exclude_paths or [
            "/",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/auth/google",
            "/api/v1/auth/google/callback",
            "/api/v1/auth/refresh",
        ]
        self.jwt_manager = jwt_manager or get_jwt_manager()
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request = Request(scope, receive)
        path = request.url.path
        
        # Skip authentication for excluded paths
        if self._is_excluded(path):
            await self.app(scope, receive, send)
            return
        
        # Extract and validate token
        auth_header = request.headers.get("Authorization")
        
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            
            result = self.jwt_manager.validate_token(
                token,
                expected_type=TokenType.ACCESS,
            )
            
            if result.is_valid:
                session = self.jwt_manager.get_user_session(token)
                if session:
                    scope["state"] = scope.get("state", {})
                    scope["state"]["user"] = session
        
        await self.app(scope, receive, send)
    
    def _is_excluded(self, path: str) -> bool:
        """Check if path is excluded from authentication."""
        for excluded in self.exclude_paths:
            if path == excluded or path.startswith(excluded + "/"):
                return True
        return False


# =============================================================================
# Helper Functions
# =============================================================================

def _get_error_detail(result: TokenValidationResult) -> str:
    """Get user-friendly error detail from validation result."""
    error_messages = {
        "token_expired": "Token has expired. Please login again.",
        "invalid_signature": "Invalid authentication credentials.",
        "invalid_format": "Invalid token format.",
        "token_revoked": "Token has been revoked. Please login again.",
        "invalid_token_type": "Invalid token type.",
        "invalid_token": "Invalid authentication credentials.",
        "validation_error": "Authentication failed.",
    }
    
    return error_messages.get(
        result.error_code or "",
        result.error or "Authentication failed",
    )


def extract_token_from_header(authorization: Optional[str]) -> Optional[str]:
    """Extract JWT token from Authorization header."""
    if not authorization:
        return None
    
    parts = authorization.split()
    
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    
    return parts[1]

