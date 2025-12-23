"""Authentication module."""

from src.auth.oauth_google import (
    GoogleOAuthClient,
    GoogleOAuthConfig,
    GoogleUserInfo,
    OAuthError,
    get_google_oauth_client,
)

from src.auth.jwt_manager import (
    JWTConfig,
    JWTManager,
    TokenBlacklist,
    TokenPair,
    TokenPayload,
    TokenType,
    TokenValidationResult,
    UserSession,
    get_jwt_manager,
    get_token_blacklist,
)

from src.auth.middleware import (
    AuthenticationMiddleware,
    bearer_scheme,
    get_current_user,
    get_current_user_optional,
    require_permissions,
    require_roles,
)

from src.auth.oauth2_server import (
    OAuth2Config,
    OAuth2Server,
    OAuth2Client,
    OAuth2Token,
    OAuth2Scope,
    OAuth2Error,
    OAuth2ClientStore,
    get_oauth2_server,
    get_client_store,
)

from src.auth.oauth2_middleware import (
    OAuth2ClientContext,
    OAuth2ScopeMiddleware,
    get_oauth2_client,
    get_oauth2_client_optional,
    require_scopes,
    require_any_scope,
)

__all__ = [
    # Google OAuth
    "GoogleOAuthClient",
    "GoogleOAuthConfig",
    "GoogleUserInfo",
    "OAuthError",
    "get_google_oauth_client",
    # JWT
    "JWTConfig",
    "JWTManager",
    "TokenBlacklist",
    "TokenPair",
    "TokenPayload",
    "TokenType",
    "TokenValidationResult",
    "UserSession",
    "get_jwt_manager",
    "get_token_blacklist",
    # User Auth Middleware
    "AuthenticationMiddleware",
    "bearer_scheme",
    "get_current_user",
    "get_current_user_optional",
    "require_permissions",
    "require_roles",
    # OAuth2 Server
    "OAuth2Config",
    "OAuth2Server",
    "OAuth2Client",
    "OAuth2Token",
    "OAuth2Scope",
    "OAuth2Error",
    "OAuth2ClientStore",
    "get_oauth2_server",
    "get_client_store",
    # OAuth2 Middleware
    "OAuth2ClientContext",
    "OAuth2ScopeMiddleware",
    "get_oauth2_client",
    "get_oauth2_client_optional",
    "require_scopes",
    "require_any_scope",
]

