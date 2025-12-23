"""
OAuth2 API Endpoints

Provides OAuth2 token endpoint, introspection, and client management.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Form, Header, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

from src.auth.oauth2_server import (
    OAuth2Server,
    OAuth2Config,
    APIClient,
    APIScope,
    SCOPE_DESCRIPTIONS,
    ClientRegistrationRequest,
    ClientCredentials,
    TokenRequest,
    TokenResponse,
    TokenIntrospectionResponse,
    ScopeEnforcer,
    get_oauth2_server,
    get_scope_enforcer,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/oauth2", tags=["OAuth2"])

# HTTP Basic auth for client credentials
basic_auth = HTTPBasic(auto_error=False)


# =============================================================================
# Response Models
# =============================================================================

class ClientResponse(BaseModel):
    """Client information response (without secret)."""
    
    client_id: str
    client_name: str
    scopes: List[str]
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    rate_limit_per_minute: int
    contact_email: Optional[str] = None


class ClientListResponse(BaseModel):
    """List of clients response."""
    
    clients: List[ClientResponse]
    total: int


class ScopeInfo(BaseModel):
    """Scope information."""
    
    scope: str
    description: str


class ScopesResponse(BaseModel):
    """Available scopes response."""
    
    scopes: List[ScopeInfo]


class ErrorResponse(BaseModel):
    """OAuth2 error response."""
    
    error: str
    error_description: Optional[str] = None


class TokenErrorResponse(BaseModel):
    """Token endpoint error response (RFC 6749)."""
    
    error: str = Field(..., description="Error code")
    error_description: Optional[str] = Field(None, description="Human-readable error")


# =============================================================================
# Dependencies
# =============================================================================

async def get_client_from_basic_auth(
    credentials: Optional[HTTPBasicCredentials] = Depends(basic_auth),
) -> tuple[str, str]:
    """Extract client credentials from HTTP Basic auth."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Client authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username, credentials.password


async def require_admin_scope(
    authorization: Optional[str] = Header(None),
    enforcer: ScopeEnforcer = Depends(get_scope_enforcer),
) -> None:
    """Require admin:clients scope for client management."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = authorization[7:]
    has_access, error = enforcer.check_scopes(token, ["admin:clients"])
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error or "Insufficient permissions",
        )


def require_scopes(*scopes: str):
    """
    Dependency factory for scope-based access control.
    
    Usage:
        @router.get("/protected", dependencies=[Depends(require_scopes("employees:read"))])
        async def protected_route():
            ...
    """
    async def dependency(
        authorization: Optional[str] = Header(None),
        enforcer: ScopeEnforcer = Depends(get_scope_enforcer),
    ) -> None:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer token required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        token = authorization[7:]
        has_access, error = enforcer.check_scopes(token, list(scopes))
        
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error or "Insufficient permissions",
            )
    
    return dependency


# =============================================================================
# Token Endpoints
# =============================================================================

@router.post(
    "/token",
    response_model=TokenResponse,
    responses={
        400: {"model": TokenErrorResponse},
        401: {"model": TokenErrorResponse},
    },
    summary="Token Endpoint",
    description="Exchange client credentials for an access token (RFC 6749 Section 4.4)",
)
async def token_endpoint(
    grant_type: str = Form(..., description="Must be 'client_credentials'"),
    scope: Optional[str] = Form(None, description="Space-separated scopes"),
    client_id: Optional[str] = Form(None),
    client_secret: Optional[str] = Form(None),
    credentials: Optional[HTTPBasicCredentials] = Depends(basic_auth),
    oauth2_server: OAuth2Server = Depends(get_oauth2_server),
) -> TokenResponse:
    """
    OAuth2 Token Endpoint.
    
    Accepts client credentials via:
    - HTTP Basic Authentication (preferred)
    - Form parameters (client_id, client_secret)
    
    Returns an access token with the granted scopes.
    """
    # Get client credentials (prefer Basic auth)
    if credentials:
        actual_client_id = credentials.username
        actual_client_secret = credentials.password
    elif client_id and client_secret:
        actual_client_id = client_id
        actual_client_secret = client_secret
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_client", "error_description": "Client authentication required"},
            headers={"WWW-Authenticate": "Basic"},
        )
    
    try:
        request = TokenRequest(
            grant_type=grant_type,
            client_id=actual_client_id,
            client_secret=actual_client_secret,
            scope=scope,
        )
        
        return oauth2_server.issue_token(request)
        
    except ValueError as e:
        error_msg = str(e)
        
        if "Invalid grant_type" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "unsupported_grant_type", "error_description": error_msg},
            )
        elif "Invalid client" in error_msg or "deactivated" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "invalid_client", "error_description": error_msg},
                headers={"WWW-Authenticate": "Basic"},
            )
        elif "scope" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "invalid_scope", "error_description": error_msg},
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "invalid_request", "error_description": error_msg},
            )


@router.post(
    "/introspect",
    response_model=TokenIntrospectionResponse,
    summary="Token Introspection Endpoint",
    description="Verify token validity and retrieve metadata (RFC 7662)",
)
async def introspect_token(
    token: str = Form(..., description="Token to introspect"),
    oauth2_server: OAuth2Server = Depends(get_oauth2_server),
) -> TokenIntrospectionResponse:
    """
    Token Introspection Endpoint (RFC 7662).
    
    Returns token metadata including validity and scopes.
    """
    return oauth2_server.introspect_token(token)


@router.post(
    "/revoke",
    status_code=status.HTTP_200_OK,
    summary="Token Revocation Endpoint",
    description="Revoke an access token (RFC 7009)",
)
async def revoke_token(
    token: str = Form(..., description="Token to revoke"),
    oauth2_server: OAuth2Server = Depends(get_oauth2_server),
) -> Dict[str, Any]:
    """
    Token Revocation Endpoint (RFC 7009).
    
    Revokes the specified token.
    """
    success = oauth2_server.revoke_token(token)
    
    # RFC 7009: Always return 200, even if token was invalid
    return {"revoked": success}


# =============================================================================
# Client Management Endpoints
# =============================================================================

@router.post(
    "/clients",
    response_model=ClientCredentials,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_scope)],
    summary="Register API Client",
    description="Register a new API client and receive credentials",
)
async def register_client(
    request: ClientRegistrationRequest,
    oauth2_server: OAuth2Server = Depends(get_oauth2_server),
) -> ClientCredentials:
    """
    Register a new API client.
    
    Returns client credentials including the secret (shown only once).
    Requires admin:clients scope.
    """
    try:
        return oauth2_server.register_client(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/clients",
    response_model=ClientListResponse,
    dependencies=[Depends(require_admin_scope)],
    summary="List API Clients",
    description="List all registered API clients",
)
async def list_clients(
    oauth2_server: OAuth2Server = Depends(get_oauth2_server),
) -> ClientListResponse:
    """
    List all registered API clients.
    
    Requires admin:clients scope.
    """
    clients = oauth2_server.list_clients()
    
    return ClientListResponse(
        clients=[
            ClientResponse(
                client_id=c.client_id,
                client_name=c.client_name,
                scopes=c.scopes,
                description=c.description,
                is_active=c.is_active,
                created_at=c.created_at,
                updated_at=c.updated_at,
                last_used_at=c.last_used_at,
                rate_limit_per_minute=c.rate_limit_per_minute,
                contact_email=c.contact_email,
            )
            for c in clients
        ],
        total=len(clients),
    )


@router.get(
    "/clients/{client_id}",
    response_model=ClientResponse,
    dependencies=[Depends(require_admin_scope)],
    summary="Get API Client",
    description="Get details of a specific API client",
)
async def get_client(
    client_id: str,
    oauth2_server: OAuth2Server = Depends(get_oauth2_server),
) -> ClientResponse:
    """
    Get details of a specific API client.
    
    Requires admin:clients scope.
    """
    client = oauth2_server.get_client(client_id)
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    
    return ClientResponse(
        client_id=client.client_id,
        client_name=client.client_name,
        scopes=client.scopes,
        description=client.description,
        is_active=client.is_active,
        created_at=client.created_at,
        updated_at=client.updated_at,
        last_used_at=client.last_used_at,
        rate_limit_per_minute=client.rate_limit_per_minute,
        contact_email=client.contact_email,
    )


@router.post(
    "/clients/{client_id}/regenerate-secret",
    dependencies=[Depends(require_admin_scope)],
    summary="Regenerate Client Secret",
    description="Regenerate the secret for an API client",
)
async def regenerate_client_secret(
    client_id: str,
    oauth2_server: OAuth2Server = Depends(get_oauth2_server),
) -> Dict[str, Any]:
    """
    Regenerate client secret.
    
    Returns new secret (shown only once).
    Requires admin:clients scope.
    """
    new_secret = oauth2_server.regenerate_secret(client_id)
    
    if not new_secret:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    
    return {
        "client_id": client_id,
        "client_secret": new_secret,
        "message": "Store this secret securely. It will not be shown again.",
        "regenerated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.patch(
    "/clients/{client_id}/scopes",
    response_model=ClientResponse,
    dependencies=[Depends(require_admin_scope)],
    summary="Update Client Scopes",
    description="Update the scopes assigned to an API client",
)
async def update_client_scopes(
    client_id: str,
    scopes: List[str],
    oauth2_server: OAuth2Server = Depends(get_oauth2_server),
) -> ClientResponse:
    """
    Update client scopes.
    
    Requires admin:clients scope.
    """
    try:
        client = oauth2_server.update_client_scopes(client_id, scopes)
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found",
            )
        
        return ClientResponse(
            client_id=client.client_id,
            client_name=client.client_name,
            scopes=client.scopes,
            description=client.description,
            is_active=client.is_active,
            created_at=client.created_at,
            updated_at=client.updated_at,
            last_used_at=client.last_used_at,
            rate_limit_per_minute=client.rate_limit_per_minute,
            contact_email=client.contact_email,
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/clients/{client_id}/deactivate",
    dependencies=[Depends(require_admin_scope)],
    summary="Deactivate API Client",
    description="Deactivate an API client (soft delete)",
)
async def deactivate_client(
    client_id: str,
    oauth2_server: OAuth2Server = Depends(get_oauth2_server),
) -> Dict[str, Any]:
    """
    Deactivate an API client.
    
    Requires admin:clients scope.
    """
    success = oauth2_server.deactivate_client(client_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    
    return {
        "client_id": client_id,
        "deactivated": True,
        "deactivated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.delete(
    "/clients/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin_scope)],
    summary="Delete API Client",
    description="Permanently delete an API client",
)
async def delete_client(
    client_id: str,
    oauth2_server: OAuth2Server = Depends(get_oauth2_server),
) -> None:
    """
    Permanently delete an API client.
    
    Requires admin:clients scope.
    """
    success = oauth2_server.delete_client(client_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )


# =============================================================================
# Discovery Endpoints
# =============================================================================

@router.get(
    "/scopes",
    response_model=ScopesResponse,
    summary="List Available Scopes",
    description="Get list of all available OAuth2 scopes",
)
async def list_scopes() -> ScopesResponse:
    """List all available OAuth2 scopes with descriptions."""
    scopes = [
        ScopeInfo(scope=s.value, description=SCOPE_DESCRIPTIONS.get(s, s.value))
        for s in APIScope
    ]
    
    return ScopesResponse(scopes=scopes)


@router.get(
    "/.well-known/oauth-authorization-server",
    summary="OAuth2 Server Metadata",
    description="OAuth2 Authorization Server Metadata (RFC 8414)",
)
async def oauth_metadata() -> Dict[str, Any]:
    """
    OAuth2 Authorization Server Metadata (RFC 8414).
    
    Returns server capabilities and endpoint URLs.
    """
    base_url = "/api/v1/oauth2"
    
    return {
        "issuer": get_oauth2_server().config.token_issuer,
        "token_endpoint": f"{base_url}/token",
        "introspection_endpoint": f"{base_url}/introspect",
        "revocation_endpoint": f"{base_url}/revoke",
        "scopes_supported": [s.value for s in APIScope],
        "response_types_supported": ["token"],
        "grant_types_supported": ["client_credentials"],
        "token_endpoint_auth_methods_supported": [
            "client_secret_basic",
            "client_secret_post",
        ],
        "introspection_endpoint_auth_methods_supported": ["none"],
        "revocation_endpoint_auth_methods_supported": ["none"],
    }
