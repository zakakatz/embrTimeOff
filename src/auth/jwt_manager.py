"""
JWT Token Manager

Provides secure JWT token generation, validation, and management
with configurable expiration and blacklisting capabilities.
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
    from jwt.exceptions import (
        DecodeError,
        ExpiredSignatureError,
        InvalidSignatureError,
        InvalidTokenError,
    )
except ImportError:
    jwt = None
    DecodeError = Exception
    ExpiredSignatureError = Exception
    InvalidSignatureError = Exception
    InvalidTokenError = Exception

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

class JWTConfig(BaseModel):
    """JWT configuration settings."""
    
    # Secret key for signing
    secret_key: str = Field(
        default_factory=lambda: os.environ.get(
            "JWT_SECRET_KEY",
            secrets.token_urlsafe(32),
        ),
    )
    
    # Algorithm
    algorithm: str = "HS256"
    
    # Token expiration
    access_token_expire_minutes: int = Field(
        default=30,
        description="Access token expiration in minutes",
    )
    refresh_token_expire_days: int = Field(
        default=7,
        description="Refresh token expiration in days",
    )
    
    # Token issuer and audience
    issuer: str = Field(
        default_factory=lambda: os.environ.get("JWT_ISSUER", "embi-auth"),
    )
    audience: str = Field(
        default_factory=lambda: os.environ.get("JWT_AUDIENCE", "embi-api"),
    )
    
    # Security options
    verify_exp: bool = True
    verify_iss: bool = True
    verify_aud: bool = True
    require_exp: bool = True
    require_iat: bool = True
    
    # Blacklist settings
    enable_blacklist: bool = True
    blacklist_check_on_refresh: bool = True


class TokenType(str, Enum):
    """Types of JWT tokens."""
    
    ACCESS = "access"
    REFRESH = "refresh"


# =============================================================================
# Models
# =============================================================================

class TokenPayload(BaseModel):
    """JWT token payload."""
    
    # Standard claims
    sub: str  # Subject (user ID)
    exp: datetime  # Expiration
    iat: datetime  # Issued at
    nbf: Optional[datetime] = None  # Not before
    iss: Optional[str] = None  # Issuer
    aud: Optional[str] = None  # Audience
    jti: str  # JWT ID (unique identifier)
    
    # Custom claims
    token_type: TokenType
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TokenPair(BaseModel):
    """Access and refresh token pair."""
    
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int  # Seconds until access token expires
    refresh_expires_in: int  # Seconds until refresh token expires
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TokenValidationResult(BaseModel):
    """Result of token validation."""
    
    is_valid: bool
    payload: Optional[TokenPayload] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


class UserSession(BaseModel):
    """User session information from token."""
    
    user_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    roles: List[str] = []
    permissions: List[str] = []
    token_id: str
    issued_at: datetime
    expires_at: datetime


# =============================================================================
# Token Blacklist
# =============================================================================

class TokenBlacklist:
    """
    In-memory token blacklist for invalidated tokens.
    
    In production, use Redis for distributed blacklisting.
    """
    
    def __init__(self):
        self._blacklisted_tokens: Set[str] = set()
        self._blacklisted_users: Set[str] = set()
    
    def blacklist_token(self, jti: str) -> None:
        """Add a token ID to the blacklist."""
        self._blacklisted_tokens.add(jti)
    
    def blacklist_user(self, user_id: str) -> None:
        """Blacklist all tokens for a user."""
        self._blacklisted_users.add(user_id)
    
    def unblacklist_user(self, user_id: str) -> None:
        """Remove user from blacklist."""
        self._blacklisted_users.discard(user_id)
    
    def is_blacklisted(self, jti: str, user_id: str) -> bool:
        """Check if token or user is blacklisted."""
        return jti in self._blacklisted_tokens or user_id in self._blacklisted_users
    
    def clear_expired(self) -> None:
        """Clear expired entries (for maintenance)."""
        # In production, implement TTL-based cleanup
        pass


# =============================================================================
# JWT Manager
# =============================================================================

class JWTManager:
    """
    Secure JWT token management.
    
    Features:
    - Access and refresh token generation
    - Token validation with configurable checks
    - Token blacklisting
    - Session extraction from tokens
    - Protection against common JWT vulnerabilities
    """
    
    def __init__(
        self,
        config: Optional[JWTConfig] = None,
        blacklist: Optional[TokenBlacklist] = None,
    ):
        if jwt is None:
            raise ImportError("PyJWT package is required for JWT management")
        
        self.config = config or JWTConfig()
        self.blacklist = blacklist or TokenBlacklist()
    
    def generate_token_pair(
        self,
        user_id: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        picture: Optional[str] = None,
        roles: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TokenPair:
        """
        Generate access and refresh token pair.
        
        Args:
            user_id: Unique user identifier
            email: User email
            name: User display name
            picture: Profile picture URL
            roles: User roles
            permissions: User permissions
            metadata: Additional custom claims
        
        Returns:
            TokenPair with access and refresh tokens
        """
        now = datetime.now(timezone.utc)
        
        # Generate unique token IDs
        access_jti = str(uuid4())
        refresh_jti = str(uuid4())
        
        # Calculate expiration times
        access_expires = now + timedelta(minutes=self.config.access_token_expire_minutes)
        refresh_expires = now + timedelta(days=self.config.refresh_token_expire_days)
        
        # Common claims
        common_claims = {
            "sub": user_id,
            "iat": now,
            "iss": self.config.issuer,
            "aud": self.config.audience,
            "email": email,
            "name": name,
            "picture": picture,
            "roles": roles or [],
            "permissions": permissions or [],
            "metadata": metadata or {},
        }
        
        # Access token
        access_payload = {
            **common_claims,
            "exp": access_expires,
            "jti": access_jti,
            "token_type": TokenType.ACCESS.value,
        }
        
        access_token = jwt.encode(
            access_payload,
            self.config.secret_key,
            algorithm=self.config.algorithm,
        )
        
        # Refresh token
        refresh_payload = {
            **common_claims,
            "exp": refresh_expires,
            "jti": refresh_jti,
            "token_type": TokenType.REFRESH.value,
            "access_jti": access_jti,  # Link to access token
        }
        
        refresh_token = jwt.encode(
            refresh_payload,
            self.config.secret_key,
            algorithm=self.config.algorithm,
        )
        
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int((access_expires - now).total_seconds()),
            refresh_expires_in=int((refresh_expires - now).total_seconds()),
            issued_at=now,
        )
    
    def validate_token(
        self,
        token: str,
        expected_type: Optional[TokenType] = None,
        check_blacklist: bool = True,
    ) -> TokenValidationResult:
        """
        Validate a JWT token.
        
        Args:
            token: JWT token string
            expected_type: Expected token type (access/refresh)
            check_blacklist: Whether to check token blacklist
        
        Returns:
            TokenValidationResult with validation status and payload
        """
        try:
            # Decode and verify token
            options = {
                "verify_exp": self.config.verify_exp,
                "verify_iss": self.config.verify_iss,
                "verify_aud": self.config.verify_aud,
                "require": ["exp", "iat", "sub", "jti"],
            }
            
            payload_dict = jwt.decode(
                token,
                self.config.secret_key,
                algorithms=[self.config.algorithm],
                options=options,
                audience=self.config.audience if self.config.verify_aud else None,
                issuer=self.config.issuer if self.config.verify_iss else None,
            )
            
            # Parse payload
            payload = TokenPayload(
                sub=payload_dict["sub"],
                exp=datetime.fromtimestamp(payload_dict["exp"], tz=timezone.utc),
                iat=datetime.fromtimestamp(payload_dict["iat"], tz=timezone.utc),
                iss=payload_dict.get("iss"),
                aud=payload_dict.get("aud"),
                jti=payload_dict["jti"],
                token_type=TokenType(payload_dict.get("token_type", "access")),
                email=payload_dict.get("email"),
                name=payload_dict.get("name"),
                picture=payload_dict.get("picture"),
                roles=payload_dict.get("roles", []),
                permissions=payload_dict.get("permissions", []),
                metadata=payload_dict.get("metadata", {}),
            )
            
            # Check token type
            if expected_type and payload.token_type != expected_type:
                return TokenValidationResult(
                    is_valid=False,
                    error=f"Invalid token type. Expected {expected_type.value}",
                    error_code="invalid_token_type",
                )
            
            # Check blacklist
            if check_blacklist and self.config.enable_blacklist:
                if self.blacklist.is_blacklisted(payload.jti, payload.sub):
                    return TokenValidationResult(
                        is_valid=False,
                        error="Token has been revoked",
                        error_code="token_revoked",
                    )
            
            return TokenValidationResult(is_valid=True, payload=payload)
            
        except ExpiredSignatureError:
            return TokenValidationResult(
                is_valid=False,
                error="Token has expired",
                error_code="token_expired",
            )
        except InvalidSignatureError:
            return TokenValidationResult(
                is_valid=False,
                error="Invalid token signature",
                error_code="invalid_signature",
            )
        except DecodeError:
            return TokenValidationResult(
                is_valid=False,
                error="Invalid token format",
                error_code="invalid_format",
            )
        except InvalidTokenError as e:
            return TokenValidationResult(
                is_valid=False,
                error=f"Invalid token: {str(e)}",
                error_code="invalid_token",
            )
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            return TokenValidationResult(
                is_valid=False,
                error="Token validation failed",
                error_code="validation_error",
            )
    
    def refresh_tokens(
        self,
        refresh_token: str,
    ) -> Optional[TokenPair]:
        """
        Generate new token pair using refresh token.
        
        Args:
            refresh_token: Valid refresh token
        
        Returns:
            New TokenPair or None if refresh token is invalid
        """
        # Validate refresh token
        result = self.validate_token(
            refresh_token,
            expected_type=TokenType.REFRESH,
            check_blacklist=self.config.blacklist_check_on_refresh,
        )
        
        if not result.is_valid or not result.payload:
            logger.warning(f"Refresh token validation failed: {result.error}")
            return None
        
        payload = result.payload
        
        # Blacklist the old refresh token
        if self.config.enable_blacklist:
            self.blacklist.blacklist_token(payload.jti)
        
        # Generate new token pair
        return self.generate_token_pair(
            user_id=payload.sub,
            email=payload.email,
            name=payload.name,
            picture=payload.picture,
            roles=payload.roles,
            permissions=payload.permissions,
            metadata=payload.metadata,
        )
    
    def revoke_token(self, token: str) -> bool:
        """
        Revoke a token by adding to blacklist.
        
        Args:
            token: Token to revoke
        
        Returns:
            True if successfully revoked
        """
        result = self.validate_token(token, check_blacklist=False)
        
        if result.payload:
            self.blacklist.blacklist_token(result.payload.jti)
            return True
        
        return False
    
    def revoke_all_user_tokens(self, user_id: str) -> None:
        """Revoke all tokens for a user."""
        self.blacklist.blacklist_user(user_id)
    
    def get_user_session(self, token: str) -> Optional[UserSession]:
        """
        Extract user session from token without database lookup.
        
        Args:
            token: Valid access token
        
        Returns:
            UserSession or None if token is invalid
        """
        result = self.validate_token(token, expected_type=TokenType.ACCESS)
        
        if not result.is_valid or not result.payload:
            return None
        
        payload = result.payload
        
        return UserSession(
            user_id=payload.sub,
            email=payload.email,
            name=payload.name,
            picture=payload.picture,
            roles=payload.roles,
            permissions=payload.permissions,
            token_id=payload.jti,
            issued_at=payload.iat,
            expires_at=payload.exp,
        )
    
    def decode_token_unsafe(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decode token without verification (for debugging only).
        
        WARNING: Do not use for authentication decisions.
        """
        try:
            return jwt.decode(
                token,
                options={"verify_signature": False},
            )
        except Exception:
            return None


# =============================================================================
# Singleton
# =============================================================================

_jwt_manager: Optional[JWTManager] = None
_token_blacklist: Optional[TokenBlacklist] = None


def get_jwt_manager() -> JWTManager:
    """Get the JWT manager singleton."""
    global _jwt_manager, _token_blacklist
    
    if _jwt_manager is None:
        _token_blacklist = TokenBlacklist()
        _jwt_manager = JWTManager(blacklist=_token_blacklist)
    
    return _jwt_manager


def get_token_blacklist() -> TokenBlacklist:
    """Get the token blacklist singleton."""
    global _token_blacklist
    
    if _token_blacklist is None:
        _token_blacklist = TokenBlacklist()
    
    return _token_blacklist

