"""
Authentication API Endpoints

Provides OAuth callback, token refresh, and logout endpoints
for authentication flow.
"""

import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from src.auth.oauth_google import (
    GoogleOAuthClient,
    GoogleUserInfo,
    OAuthError,
    get_google_oauth_client,
)
from src.auth.jwt_manager import (
    JWTManager,
    TokenPair,
    UserSession,
    get_jwt_manager,
)
from src.auth.middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# =============================================================================
# Request/Response Models
# =============================================================================

class AuthorizationUrlResponse(BaseModel):
    """Response with Google OAuth authorization URL."""
    
    authorization_url: str
    state: str


class TokenResponse(BaseModel):
    """Token response model."""
    
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    issued_at: datetime


class RefreshTokenRequest(BaseModel):
    """Request to refresh tokens."""
    
    refresh_token: str


class UserInfoResponse(BaseModel):
    """Current user information response."""
    
    user_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    roles: list = Field(default_factory=list)
    token_expires_at: datetime


class LogoutResponse(BaseModel):
    """Logout response."""
    
    success: bool
    message: str


# =============================================================================
# State Management (In production, use Redis)
# =============================================================================

_oauth_states: Dict[str, Dict[str, Any]] = {}


def _create_state() -> str:
    """Create a secure random state for OAuth."""
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = {
        "created_at": datetime.now(timezone.utc),
    }
    return state


def _verify_state(state: str) -> bool:
    """Verify OAuth state and remove it."""
    if state in _oauth_states:
        del _oauth_states[state]
        return True
    return False


# =============================================================================
# Endpoints
# =============================================================================

@router.get(
    "/google",
    response_model=AuthorizationUrlResponse,
    summary="Get Google OAuth URL",
    description="Get the Google OAuth authorization URL to redirect users for login",
)
async def get_google_auth_url(
    oauth_client: GoogleOAuthClient = Depends(get_google_oauth_client),
) -> AuthorizationUrlResponse:
    """
    Generate Google OAuth authorization URL.
    
    Returns URL that the client should redirect to for Google login.
    """
    state = _create_state()
    
    auth_url = oauth_client.get_authorization_url(
        state=state,
        prompt="select_account",
    )
    
    return AuthorizationUrlResponse(
        authorization_url=auth_url,
        state=state,
    )


@router.get(
    "/google/callback",
    response_model=TokenResponse,
    summary="Google OAuth Callback",
    description="Handle Google OAuth callback and exchange code for tokens",
)
async def google_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    error: Optional[str] = Query(None, description="Error from Google"),
    oauth_client: GoogleOAuthClient = Depends(get_google_oauth_client),
    jwt_manager: JWTManager = Depends(get_jwt_manager),
) -> TokenResponse:
    """
    Handle Google OAuth callback.
    
    - Verifies state parameter
    - Exchanges authorization code for tokens
    - Retrieves user profile from Google
    - Generates JWT token pair
    """
    # Check for errors from Google
    if error:
        logger.warning(f"Google OAuth error: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {error}",
        )
    
    # Verify state
    if not _verify_state(state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state parameter",
        )
    
    try:
        # Exchange code for tokens
        google_tokens = await oauth_client.exchange_code(code)
        
        # Get user info from Google
        user_info = await oauth_client.get_user_info(google_tokens.access_token)
        
        logger.info(f"Google auth successful for: {user_info.email}")
        
        # Generate JWT tokens
        token_pair = jwt_manager.generate_token_pair(
            user_id=user_info.sub,
            email=user_info.email,
            name=user_info.name,
            picture=user_info.picture,
            roles=["user"],  # Default role
            metadata={
                "auth_provider": "google",
                "email_verified": user_info.email_verified,
            },
        )
        
        return TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type=token_pair.token_type,
            expires_in=token_pair.expires_in,
            issued_at=token_pair.issued_at,
        )
        
    except OAuthError as e:
        logger.error(f"OAuth error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed",
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh Tokens",
    description="Exchange refresh token for new token pair",
)
async def refresh_tokens(
    request: RefreshTokenRequest,
    jwt_manager: JWTManager = Depends(get_jwt_manager),
) -> TokenResponse:
    """
    Refresh access token using refresh token.
    
    The old refresh token will be invalidated.
    """
    token_pair = jwt_manager.refresh_tokens(request.refresh_token)
    
    if not token_pair:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    
    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type=token_pair.token_type,
        expires_in=token_pair.expires_in,
        issued_at=token_pair.issued_at,
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Logout",
    description="Logout and invalidate current tokens",
)
async def logout(
    request: Request,
    user: UserSession = Depends(get_current_user),
    jwt_manager: JWTManager = Depends(get_jwt_manager),
) -> LogoutResponse:
    """
    Logout current user and invalidate tokens.
    """
    # Get token from header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        jwt_manager.revoke_token(token)
    
    logger.info(f"User logged out: {user.user_id}")
    
    return LogoutResponse(
        success=True,
        message="Successfully logged out",
    )


@router.post(
    "/logout/all",
    response_model=LogoutResponse,
    summary="Logout All Sessions",
    description="Logout and invalidate all tokens for current user",
)
async def logout_all_sessions(
    user: UserSession = Depends(get_current_user),
    jwt_manager: JWTManager = Depends(get_jwt_manager),
) -> LogoutResponse:
    """
    Logout all sessions for current user.
    
    Invalidates all access and refresh tokens.
    """
    jwt_manager.revoke_all_user_tokens(user.user_id)
    
    logger.info(f"All sessions revoked for user: {user.user_id}")
    
    return LogoutResponse(
        success=True,
        message="All sessions have been invalidated",
    )


@router.get(
    "/me",
    response_model=UserInfoResponse,
    summary="Get Current User",
    description="Get current authenticated user information from token",
)
async def get_current_user_info(
    user: UserSession = Depends(get_current_user),
) -> UserInfoResponse:
    """
    Get current user information.
    
    Extracts user info from JWT token without database lookup.
    """
    return UserInfoResponse(
        user_id=user.user_id,
        email=user.email,
        name=user.name,
        picture=user.picture,
        roles=user.roles,
        token_expires_at=user.expires_at,
    )


@router.get(
    "/verify",
    summary="Verify Token",
    description="Verify if current token is valid",
)
async def verify_token(
    user: UserSession = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Verify current token validity.
    
    Returns token information if valid.
    """
    return {
        "valid": True,
        "user_id": user.user_id,
        "email": user.email,
        "expires_at": user.expires_at.isoformat(),
        "issued_at": user.issued_at.isoformat(),
    }

