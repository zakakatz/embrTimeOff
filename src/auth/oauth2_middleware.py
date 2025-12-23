"""
OAuth2 Scope Enforcement Middleware

Provides middleware and dependencies for enforcing OAuth2 scope-based
access control on API endpoints.
"""

import logging
from typing import Callable, List, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.oauth2_server import (
    OAuth2Server,
    OAuth2Scope,
    TokenPayload,
    get_oauth2_server,
)

logger = logging.getLogger(__name__)

# HTTP Bearer security scheme for OAuth2 tokens
oauth2_bearer = HTTPBearer(auto_error=False)


# =============================================================================
# OAuth2 Client Context
# =============================================================================

class OAuth2ClientContext:
    """
    Context for authenticated OAuth2 client.
    
    Contains token information and granted scopes for authorization decisions.
    """
    
    def __init__(
        self,
        client_id: str,
        client_name: Optional[str],
        scopes: List[str],
        token_payload: TokenPayload,
    ):
        self.client_id = client_id
        self.client_name = client_name
        self.scopes = scopes
        self.token_payload = token_payload
    
    def has_scope(self, scope: str) -> bool:
        """Check if client has a specific scope."""
        return scope in self.scopes
    
    def has_any_scope(self, scopes: List[str]) -> bool:
        """Check if client has any of the specified scopes."""
        return any(s in self.scopes for s in scopes)
    
    def has_all_scopes(self, scopes: List[str]) -> bool:
        """Check if client has all specified scopes."""
        return all(s in self.scopes for s in scopes)


# =============================================================================
# Dependencies
# =============================================================================

async def get_oauth2_client(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_bearer),
    oauth2_server: OAuth2Server = Depends(get_oauth2_server),
) -> OAuth2ClientContext:
    """
    Dependency to get authenticated OAuth2 client.
    
    Validates the Bearer token and returns client context.
    Raises 401 if authentication fails.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    is_valid, payload, error = oauth2_server.validate_token(token)
    
    if not is_valid or not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error or "Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Parse scopes
    scopes = payload.scope.split() if payload.scope else []
    
    context = OAuth2ClientContext(
        client_id=payload.sub,
        client_name=payload.client_name,
        scopes=scopes,
        token_payload=payload,
    )
    
    # Store in request state
    request.state.oauth2_client = context
    
    return context


async def get_oauth2_client_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(oauth2_bearer),
    oauth2_server: OAuth2Server = Depends(get_oauth2_server),
) -> Optional[OAuth2ClientContext]:
    """
    Optional dependency for OAuth2 client.
    
    Returns None if no valid token provided, instead of raising 401.
    """
    if not credentials:
        return None
    
    try:
        return await get_oauth2_client(request, credentials, oauth2_server)
    except HTTPException:
        return None


def require_scopes(*required_scopes: str) -> Callable:
    """
    Dependency factory for scope-based access control.
    
    Returns 403 if client doesn't have required scopes.
    
    Usage:
        @router.get("/employees")
        async def list_employees(
            client: OAuth2ClientContext = Depends(require_scopes("employees:read"))
        ):
            ...
    """
    async def dependency(
        client: OAuth2ClientContext = Depends(get_oauth2_client),
    ) -> OAuth2ClientContext:
        # Check all required scopes
        missing_scopes = [s for s in required_scopes if s not in client.scopes]
        
        if missing_scopes:
            logger.warning(
                f"Client {client.client_id} denied access. "
                f"Missing scopes: {missing_scopes}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "insufficient_scope",
                    "error_description": f"Missing required scopes: {', '.join(missing_scopes)}",
                    "required_scopes": list(required_scopes),
                    "granted_scopes": client.scopes,
                },
            )
        
        return client
    
    return dependency


def require_any_scope(*scopes: str) -> Callable:
    """
    Dependency factory requiring at least one of the specified scopes.
    
    Usage:
        @router.get("/data")
        async def get_data(
            client: OAuth2ClientContext = Depends(require_any_scope("admin:read", "data:read"))
        ):
            ...
    """
    async def dependency(
        client: OAuth2ClientContext = Depends(get_oauth2_client),
    ) -> OAuth2ClientContext:
        if not client.has_any_scope(list(scopes)):
            logger.warning(
                f"Client {client.client_id} denied access. "
                f"Requires one of: {scopes}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "insufficient_scope",
                    "error_description": f"Requires at least one of: {', '.join(scopes)}",
                    "required_scopes": list(scopes),
                    "granted_scopes": client.scopes,
                },
            )
        
        return client
    
    return dependency


# =============================================================================
# Scope Verification Utilities
# =============================================================================

def verify_scope(
    client: OAuth2ClientContext,
    required_scope: str,
    raise_on_fail: bool = True,
) -> bool:
    """
    Verify that client has a required scope.
    
    Args:
        client: OAuth2 client context
        required_scope: Scope to check
        raise_on_fail: Whether to raise HTTPException on failure
    
    Returns:
        True if scope is present
    
    Raises:
        HTTPException: If scope missing and raise_on_fail is True
    """
    if client.has_scope(required_scope):
        return True
    
    if raise_on_fail:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "insufficient_scope",
                "error_description": f"Missing required scope: {required_scope}",
            },
        )
    
    return False


def get_allowed_scopes_for_resource(resource_type: str) -> List[str]:
    """
    Get scopes that allow access to a resource type.
    
    Useful for filtering results based on client scopes.
    """
    resource_scope_map = {
        "employee": [OAuth2Scope.EMPLOYEES_READ.value, OAuth2Scope.ADMIN_READ.value],
        "timeoff": [OAuth2Scope.TIMEOFF_READ.value, OAuth2Scope.ADMIN_READ.value],
        "organization": [OAuth2Scope.ORG_READ.value, OAuth2Scope.ADMIN_READ.value],
        "directory": [OAuth2Scope.DIRECTORY_READ.value, OAuth2Scope.DIRECTORY_SEARCH.value],
        "audit": [OAuth2Scope.AUDIT_READ.value, OAuth2Scope.ADMIN_READ.value],
        "storage": [OAuth2Scope.STORAGE_READ.value, OAuth2Scope.ADMIN_READ.value],
    }
    
    return resource_scope_map.get(resource_type, [])


# =============================================================================
# Middleware
# =============================================================================

class OAuth2ScopeMiddleware:
    """
    Middleware for automatic OAuth2 token validation.
    
    Validates Bearer tokens and stores client context in request state.
    Does not enforce scopes - use dependencies for that.
    """
    
    def __init__(
        self,
        app,
        exclude_paths: Optional[List[str]] = None,
    ):
        self.app = app
        self.exclude_paths = exclude_paths or [
            "/",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/oauth2/token",
            "/api/v1/oauth2/introspect",
        ]
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        from fastapi import Request
        request = Request(scope, receive)
        path = request.url.path
        
        # Skip excluded paths
        if self._is_excluded(path):
            await self.app(scope, receive, send)
            return
        
        # Extract and validate token if present
        auth_header = request.headers.get("Authorization", "")
        
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            oauth2_server = get_oauth2_server()
            
            is_valid, payload, _ = oauth2_server.validate_token(token)
            
            if is_valid and payload:
                scopes = payload.scope.split() if payload.scope else []
                context = OAuth2ClientContext(
                    client_id=payload.sub,
                    client_name=payload.client_name,
                    scopes=scopes,
                    token_payload=payload,
                )
                scope["state"] = scope.get("state", {})
                scope["state"]["oauth2_client"] = context
        
        await self.app(scope, receive, send)
    
    def _is_excluded(self, path: str) -> bool:
        """Check if path is excluded from processing."""
        for excluded in self.exclude_paths:
            if path == excluded or path.startswith(excluded + "/"):
                return True
        return False

