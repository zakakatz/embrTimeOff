"""
Google OAuth 2.0 Authentication

Implements Google OAuth 2.0 flow for user authentication with
profile information retrieval.
"""

import os
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

class GoogleOAuthConfig(BaseModel):
    """Google OAuth configuration."""
    
    client_id: str = Field(
        default_factory=lambda: os.environ.get("GOOGLE_CLIENT_ID", ""),
    )
    client_secret: str = Field(
        default_factory=lambda: os.environ.get("GOOGLE_CLIENT_SECRET", ""),
    )
    redirect_uri: str = Field(
        default_factory=lambda: os.environ.get(
            "GOOGLE_REDIRECT_URI",
            "http://localhost:8000/api/v1/auth/google/callback"
        ),
    )
    
    # OAuth endpoints
    authorization_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url: str = "https://oauth2.googleapis.com/token"
    userinfo_url: str = "https://www.googleapis.com/oauth2/v3/userinfo"
    revoke_url: str = "https://oauth2.googleapis.com/revoke"
    
    # Scopes
    scopes: list = Field(default_factory=lambda: [
        "openid",
        "email",
        "profile",
    ])


# =============================================================================
# Models
# =============================================================================

class GoogleUserInfo(BaseModel):
    """User information from Google."""
    
    sub: str  # Google user ID
    email: str
    email_verified: bool = False
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None
    locale: Optional[str] = None


class GoogleTokenResponse(BaseModel):
    """Token response from Google OAuth."""
    
    access_token: str
    expires_in: int
    token_type: str = "Bearer"
    scope: Optional[str] = None
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None


# =============================================================================
# OAuth Client
# =============================================================================

class GoogleOAuthClient:
    """
    Google OAuth 2.0 client for authentication.
    
    Handles:
    - Authorization URL generation
    - Token exchange
    - User profile retrieval
    - Token refresh
    - Token revocation
    """
    
    def __init__(self, config: Optional[GoogleOAuthConfig] = None):
        self.config = config or GoogleOAuthConfig()
        self._http_client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close HTTP client."""
        await self._http_client.aclose()
    
    def get_authorization_url(
        self,
        state: str,
        nonce: Optional[str] = None,
        prompt: str = "select_account",
        access_type: str = "offline",
    ) -> str:
        """
        Generate Google OAuth authorization URL.
        
        Args:
            state: CSRF protection state token
            nonce: Optional nonce for ID token validation
            prompt: Consent prompt behavior
            access_type: Access type (offline for refresh token)
        
        Returns:
            Authorization URL to redirect user to
        """
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.config.scopes),
            "state": state,
            "access_type": access_type,
            "prompt": prompt,
        }
        
        if nonce:
            params["nonce"] = nonce
        
        return f"{self.config.authorization_url}?{urlencode(params)}"
    
    async def exchange_code(self, code: str) -> GoogleTokenResponse:
        """
        Exchange authorization code for tokens.
        
        Args:
            code: Authorization code from callback
        
        Returns:
            Token response with access token and optionally refresh token
        
        Raises:
            OAuthError: If token exchange fails
        """
        data = {
            "code": code,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "redirect_uri": self.config.redirect_uri,
            "grant_type": "authorization_code",
        }
        
        try:
            response = await self._http_client.post(
                self.config.token_url,
                data=data,
            )
            response.raise_for_status()
            
            token_data = response.json()
            return GoogleTokenResponse(**token_data)
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Token exchange failed: {e.response.text}")
            raise OAuthError(f"Failed to exchange code: {e.response.text}")
        except Exception as e:
            logger.error(f"Token exchange error: {str(e)}")
            raise OAuthError(f"Token exchange error: {str(e)}")
    
    async def refresh_access_token(
        self,
        refresh_token: str,
    ) -> GoogleTokenResponse:
        """
        Refresh an access token using refresh token.
        
        Args:
            refresh_token: Refresh token from initial auth
        
        Returns:
            New token response
        """
        data = {
            "refresh_token": refresh_token,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "grant_type": "refresh_token",
        }
        
        try:
            response = await self._http_client.post(
                self.config.token_url,
                data=data,
            )
            response.raise_for_status()
            
            token_data = response.json()
            return GoogleTokenResponse(**token_data)
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Token refresh failed: {e.response.text}")
            raise OAuthError(f"Failed to refresh token: {e.response.text}")
    
    async def get_user_info(self, access_token: str) -> GoogleUserInfo:
        """
        Get user profile information from Google.
        
        Args:
            access_token: Valid Google access token
        
        Returns:
            User profile information
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            response = await self._http_client.get(
                self.config.userinfo_url,
                headers=headers,
            )
            response.raise_for_status()
            
            user_data = response.json()
            return GoogleUserInfo(**user_data)
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get user info: {e.response.text}")
            raise OAuthError(f"Failed to get user info: {e.response.text}")
    
    async def revoke_token(self, token: str) -> bool:
        """
        Revoke a Google OAuth token.
        
        Args:
            token: Access token or refresh token to revoke
        
        Returns:
            True if revocation succeeded
        """
        try:
            response = await self._http_client.post(
                self.config.revoke_url,
                params={"token": token},
            )
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Token revocation failed: {str(e)}")
            return False


# =============================================================================
# Exceptions
# =============================================================================

class OAuthError(Exception):
    """OAuth authentication error."""
    pass


# =============================================================================
# Singleton
# =============================================================================

_oauth_client: Optional[GoogleOAuthClient] = None


def get_google_oauth_client() -> GoogleOAuthClient:
    """Get the Google OAuth client singleton."""
    global _oauth_client
    if _oauth_client is None:
        _oauth_client = GoogleOAuthClient()
    return _oauth_client

