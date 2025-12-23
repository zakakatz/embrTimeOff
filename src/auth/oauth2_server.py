"""
OAuth2 Server with Client Credentials Flow

Implements OAuth2 client credentials flow for service-to-service authentication
with scope-based permissions for granular access control.
"""

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4

try:
    import jwt
    from jwt.exceptions import InvalidTokenError
except ImportError:
    jwt = None

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Scopes Definition
# =============================================================================

class APIScope(str, Enum):
    """Available API scopes for access control."""
    
    # Employee scopes
    EMPLOYEES_READ = "employees:read"
    EMPLOYEES_WRITE = "employees:write"
    EMPLOYEES_DELETE = "employees:delete"
    
    # Time-off scopes
    TIMEOFF_READ = "timeoff:read"
    TIMEOFF_WRITE = "timeoff:write"
    TIMEOFF_APPROVE = "timeoff:approve"
    
    # Organization scopes
    ORG_READ = "org:read"
    ORG_WRITE = "org:write"
    
    # Reports scopes
    REPORTS_READ = "reports:read"
    REPORTS_EXPORT = "reports:export"
    
    # Admin scopes
    ADMIN_CLIENTS = "admin:clients"
    ADMIN_AUDIT = "admin:audit"
    
    # Integration scopes
    WEBHOOKS_MANAGE = "webhooks:manage"
    INTEGRATIONS_READ = "integrations:read"


# Scope descriptions for documentation
SCOPE_DESCRIPTIONS = {
    APIScope.EMPLOYEES_READ: "Read employee data",
    APIScope.EMPLOYEES_WRITE: "Create and update employees",
    APIScope.EMPLOYEES_DELETE: "Delete employees",
    APIScope.TIMEOFF_READ: "Read time-off requests",
    APIScope.TIMEOFF_WRITE: "Create and update time-off requests",
    APIScope.TIMEOFF_APPROVE: "Approve or deny time-off requests",
    APIScope.ORG_READ: "Read organizational structure",
    APIScope.ORG_WRITE: "Modify organizational structure",
    APIScope.REPORTS_READ: "Read reports",
    APIScope.REPORTS_EXPORT: "Export reports",
    APIScope.ADMIN_CLIENTS: "Manage API clients",
    APIScope.ADMIN_AUDIT: "Access audit logs",
    APIScope.WEBHOOKS_MANAGE: "Manage webhooks",
    APIScope.INTEGRATIONS_READ: "Read integration data",
}


# =============================================================================
# Configuration
# =============================================================================

class OAuth2Config(BaseModel):
    """OAuth2 server configuration."""
    
    # Token settings
    access_token_expire_minutes: int = Field(default=60)
    token_issuer: str = Field(
        default_factory=lambda: os.environ.get("OAUTH2_ISSUER", "embi-oauth2"),
    )
    token_audience: str = Field(
        default_factory=lambda: os.environ.get("OAUTH2_AUDIENCE", "embi-api"),
    )
    
    # Signing
    secret_key: str = Field(
        default_factory=lambda: os.environ.get(
            "OAUTH2_SECRET_KEY",
            secrets.token_urlsafe(32),
        ),
    )
    algorithm: str = "HS256"
    
    # Client credentials
    client_secret_bytes: int = 32
    client_id_prefix: str = "embi_"


# =============================================================================
# Models
# =============================================================================

class APIClient(BaseModel):
    """Registered API client."""
    
    client_id: str
    client_name: str
    client_secret_hash: str
    scopes: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    
    # Status
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    
    # Rate limiting
    rate_limit_per_minute: int = 1000
    
    # Metadata
    contact_email: Optional[str] = None
    allowed_ips: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ClientCredentials(BaseModel):
    """Client credentials for registration response."""
    
    client_id: str
    client_secret: str  # Only returned on creation
    client_name: str
    scopes: List[str]
    created_at: datetime


class TokenRequest(BaseModel):
    """OAuth2 token request."""
    
    grant_type: str = Field(..., description="Must be 'client_credentials'")
    client_id: str
    client_secret: str
    scope: Optional[str] = Field(None, description="Space-separated scopes")


class TokenResponse(BaseModel):
    """OAuth2 token response."""
    
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    scope: str


class TokenIntrospectionResponse(BaseModel):
    """Token introspection response (RFC 7662)."""
    
    active: bool
    scope: Optional[str] = None
    client_id: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None
    iss: Optional[str] = None
    aud: Optional[str] = None
    token_type: Optional[str] = None


class ClientRegistrationRequest(BaseModel):
    """Request to register a new API client."""
    
    client_name: str = Field(..., min_length=3, max_length=100)
    scopes: List[str] = Field(..., min_items=1)
    description: Optional[str] = Field(None, max_length=500)
    contact_email: Optional[str] = None
    allowed_ips: List[str] = Field(default_factory=list)
    rate_limit_per_minute: int = Field(default=1000, ge=10, le=10000)


# =============================================================================
# Client Storage
# =============================================================================

class ClientStore:
    """
    In-memory client storage.
    
    In production, replace with database-backed storage.
    """
    
    def __init__(self):
        self._clients: Dict[str, APIClient] = {}
    
    def create(self, client: APIClient) -> None:
        """Store a new client."""
        self._clients[client.client_id] = client
    
    def get(self, client_id: str) -> Optional[APIClient]:
        """Get a client by ID."""
        return self._clients.get(client_id)
    
    def update(self, client: APIClient) -> None:
        """Update a client."""
        client.updated_at = datetime.now(timezone.utc)
        self._clients[client.client_id] = client
    
    def delete(self, client_id: str) -> bool:
        """Delete a client."""
        if client_id in self._clients:
            del self._clients[client_id]
            return True
        return False
    
    def list_all(self) -> List[APIClient]:
        """List all clients."""
        return list(self._clients.values())
    
    def get_by_name(self, name: str) -> Optional[APIClient]:
        """Get a client by name."""
        for client in self._clients.values():
            if client.client_name == name:
                return client
        return None


# =============================================================================
# OAuth2 Server
# =============================================================================

class OAuth2Server:
    """
    OAuth2 Authorization Server implementing client credentials flow.
    
    Features:
    - Client registration and management
    - Token generation with configurable expiration
    - Scope-based access control
    - Token introspection
    - Secure credential hashing
    """
    
    def __init__(
        self,
        config: Optional[OAuth2Config] = None,
        client_store: Optional[ClientStore] = None,
    ):
        if jwt is None:
            raise ImportError("PyJWT package is required for OAuth2 server")
        
        self.config = config or OAuth2Config()
        self.client_store = client_store or ClientStore()
        self._revoked_tokens: Set[str] = set()
    
    # =========================================================================
    # Client Management
    # =========================================================================
    
    def register_client(
        self,
        request: ClientRegistrationRequest,
    ) -> ClientCredentials:
        """
        Register a new API client.
        
        Returns client credentials including the secret (only shown once).
        """
        # Validate scopes
        invalid_scopes = self._validate_scopes(request.scopes)
        if invalid_scopes:
            raise ValueError(f"Invalid scopes: {', '.join(invalid_scopes)}")
        
        # Check for duplicate name
        existing = self.client_store.get_by_name(request.client_name)
        if existing:
            raise ValueError(f"Client with name '{request.client_name}' already exists")
        
        # Generate credentials
        client_id = self._generate_client_id()
        client_secret = self._generate_client_secret()
        secret_hash = self._hash_secret(client_secret)
        
        # Create client
        client = APIClient(
            client_id=client_id,
            client_name=request.client_name,
            client_secret_hash=secret_hash,
            scopes=request.scopes,
            description=request.description,
            contact_email=request.contact_email,
            allowed_ips=request.allowed_ips,
            rate_limit_per_minute=request.rate_limit_per_minute,
        )
        
        self.client_store.create(client)
        
        logger.info(f"Registered new API client: {client_id}")
        
        return ClientCredentials(
            client_id=client_id,
            client_secret=client_secret,
            client_name=request.client_name,
            scopes=request.scopes,
            created_at=client.created_at,
        )
    
    def regenerate_secret(self, client_id: str) -> Optional[str]:
        """
        Regenerate client secret.
        
        Returns the new secret (only shown once).
        """
        client = self.client_store.get(client_id)
        if not client:
            return None
        
        new_secret = self._generate_client_secret()
        client.client_secret_hash = self._hash_secret(new_secret)
        client.updated_at = datetime.now(timezone.utc)
        
        self.client_store.update(client)
        
        logger.info(f"Regenerated secret for client: {client_id}")
        
        return new_secret
    
    def update_client_scopes(
        self,
        client_id: str,
        scopes: List[str],
    ) -> Optional[APIClient]:
        """Update client scopes."""
        client = self.client_store.get(client_id)
        if not client:
            return None
        
        invalid_scopes = self._validate_scopes(scopes)
        if invalid_scopes:
            raise ValueError(f"Invalid scopes: {', '.join(invalid_scopes)}")
        
        client.scopes = scopes
        self.client_store.update(client)
        
        return client
    
    def deactivate_client(self, client_id: str) -> bool:
        """Deactivate a client (soft delete)."""
        client = self.client_store.get(client_id)
        if not client:
            return False
        
        client.is_active = False
        self.client_store.update(client)
        
        logger.info(f"Deactivated client: {client_id}")
        return True
    
    def delete_client(self, client_id: str) -> bool:
        """Permanently delete a client."""
        result = self.client_store.delete(client_id)
        if result:
            logger.info(f"Deleted client: {client_id}")
        return result
    
    def get_client(self, client_id: str) -> Optional[APIClient]:
        """Get client by ID."""
        return self.client_store.get(client_id)
    
    def list_clients(self) -> List[APIClient]:
        """List all clients."""
        return self.client_store.list_all()
    
    # =========================================================================
    # Token Operations
    # =========================================================================
    
    def issue_token(self, request: TokenRequest) -> TokenResponse:
        """
        Issue an access token using client credentials.
        
        Implements RFC 6749 Section 4.4 Client Credentials Grant.
        """
        # Validate grant type
        if request.grant_type != "client_credentials":
            raise ValueError("Invalid grant_type. Must be 'client_credentials'")
        
        # Authenticate client
        client = self._authenticate_client(request.client_id, request.client_secret)
        if not client:
            raise ValueError("Invalid client credentials")
        
        if not client.is_active:
            raise ValueError("Client is deactivated")
        
        # Parse and validate requested scopes
        requested_scopes = self._parse_scopes(request.scope)
        granted_scopes = self._validate_requested_scopes(requested_scopes, client.scopes)
        
        if not granted_scopes:
            raise ValueError("No valid scopes requested")
        
        # Generate token
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=self.config.access_token_expire_minutes)
        
        token_id = str(uuid4())
        
        payload = {
            "jti": token_id,
            "iss": self.config.token_issuer,
            "aud": self.config.token_audience,
            "sub": client.client_id,
            "client_id": client.client_id,
            "scope": " ".join(granted_scopes),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "token_type": "access_token",
        }
        
        access_token = jwt.encode(
            payload,
            self.config.secret_key,
            algorithm=self.config.algorithm,
        )
        
        # Update last used
        client.last_used_at = now
        self.client_store.update(client)
        
        logger.debug(f"Issued token for client: {client.client_id}")
        
        return TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=self.config.access_token_expire_minutes * 60,
            scope=" ".join(granted_scopes),
        )
    
    def introspect_token(self, token: str) -> TokenIntrospectionResponse:
        """
        Introspect a token (RFC 7662).
        
        Returns token metadata including validity and scopes.
        """
        try:
            payload = jwt.decode(
                token,
                self.config.secret_key,
                algorithms=[self.config.algorithm],
                audience=self.config.token_audience,
                issuer=self.config.token_issuer,
            )
            
            # Check if token is revoked
            if payload.get("jti") in self._revoked_tokens:
                return TokenIntrospectionResponse(active=False)
            
            return TokenIntrospectionResponse(
                active=True,
                scope=payload.get("scope"),
                client_id=payload.get("client_id"),
                exp=payload.get("exp"),
                iat=payload.get("iat"),
                iss=payload.get("iss"),
                aud=payload.get("aud"),
                token_type="Bearer",
            )
            
        except InvalidTokenError:
            return TokenIntrospectionResponse(active=False)
    
    def revoke_token(self, token: str) -> bool:
        """Revoke a token."""
        try:
            payload = jwt.decode(
                token,
                self.config.secret_key,
                algorithms=[self.config.algorithm],
                options={"verify_exp": False},
            )
            
            token_id = payload.get("jti")
            if token_id:
                self._revoked_tokens.add(token_id)
                return True
            return False
            
        except InvalidTokenError:
            return False
    
    def validate_token_scopes(
        self,
        token: str,
        required_scopes: List[str],
    ) -> bool:
        """
        Validate that token has required scopes.
        
        Returns True if token has all required scopes.
        """
        introspection = self.introspect_token(token)
        
        if not introspection.active:
            return False
        
        token_scopes = set(introspection.scope.split() if introspection.scope else [])
        required = set(required_scopes)
        
        return required.issubset(token_scopes)
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _generate_client_id(self) -> str:
        """Generate a unique client ID."""
        return f"{self.config.client_id_prefix}{secrets.token_hex(16)}"
    
    def _generate_client_secret(self) -> str:
        """Generate a secure client secret."""
        return secrets.token_urlsafe(self.config.client_secret_bytes)
    
    def _hash_secret(self, secret: str) -> str:
        """Hash a client secret for storage."""
        return hashlib.sha256(secret.encode()).hexdigest()
    
    def _verify_secret(self, secret: str, hash_value: str) -> bool:
        """Verify a client secret against stored hash."""
        return self._hash_secret(secret) == hash_value
    
    def _authenticate_client(
        self,
        client_id: str,
        client_secret: str,
    ) -> Optional[APIClient]:
        """Authenticate client with credentials."""
        client = self.client_store.get(client_id)
        
        if not client:
            return None
        
        if not self._verify_secret(client_secret, client.client_secret_hash):
            return None
        
        return client
    
    def _validate_scopes(self, scopes: List[str]) -> List[str]:
        """Validate scopes and return invalid ones."""
        valid_scopes = {s.value for s in APIScope}
        invalid = [s for s in scopes if s not in valid_scopes]
        return invalid
    
    def _parse_scopes(self, scope_string: Optional[str]) -> List[str]:
        """Parse space-separated scope string."""
        if not scope_string:
            return []
        return [s.strip() for s in scope_string.split() if s.strip()]
    
    def _validate_requested_scopes(
        self,
        requested: List[str],
        allowed: List[str],
    ) -> List[str]:
        """
        Validate requested scopes against allowed scopes.
        
        Returns intersection of requested and allowed scopes.
        If no scopes requested, returns all allowed scopes.
        """
        allowed_set = set(allowed)
        
        if not requested:
            return list(allowed_set)
        
        return list(set(requested) & allowed_set)


# =============================================================================
# Scope Enforcement
# =============================================================================

class ScopeEnforcer:
    """
    Utility class for enforcing scope-based access control.
    
    Use in route handlers to check required scopes.
    """
    
    def __init__(self, oauth2_server: OAuth2Server):
        self.oauth2_server = oauth2_server
    
    def check_scopes(
        self,
        token: str,
        required_scopes: List[str],
    ) -> tuple[bool, Optional[str]]:
        """
        Check if token has required scopes.
        
        Returns:
            Tuple of (has_access, error_message)
        """
        introspection = self.oauth2_server.introspect_token(token)
        
        if not introspection.active:
            return False, "Token is invalid or expired"
        
        token_scopes = set(introspection.scope.split() if introspection.scope else [])
        required = set(required_scopes)
        missing = required - token_scopes
        
        if missing:
            return False, f"Missing required scopes: {', '.join(missing)}"
        
        return True, None
    
    def get_token_scopes(self, token: str) -> List[str]:
        """Get list of scopes from token."""
        introspection = self.oauth2_server.introspect_token(token)
        
        if not introspection.active or not introspection.scope:
            return []
        
        return introspection.scope.split()


# =============================================================================
# Singleton
# =============================================================================

_oauth2_server: Optional[OAuth2Server] = None
_scope_enforcer: Optional[ScopeEnforcer] = None


def get_oauth2_server() -> OAuth2Server:
    """Get the OAuth2 server singleton."""
    global _oauth2_server
    if _oauth2_server is None:
        _oauth2_server = OAuth2Server()
    return _oauth2_server


def get_scope_enforcer() -> ScopeEnforcer:
    """Get the scope enforcer singleton."""
    global _scope_enforcer
    if _scope_enforcer is None:
        _scope_enforcer = ScopeEnforcer(get_oauth2_server())
    return _scope_enforcer
