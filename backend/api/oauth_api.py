"""OAuth API — endpoints for OAuth2 authorization flows.

Provides:
- GET  /oauth/{provider}/authorize  — build auth URL
- GET  /oauth/{provider}/callback   — handle code callback
- POST /oauth/{provider}/refresh    — refresh token
- GET  /oauth/status                — connection status
- DELETE /oauth/{provider}          — revoke/disconnect
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from backend.services.oauth_provider import OAuthError, oauth_manager

logger = logging.getLogger("tenderclaw.api.oauth")

router = APIRouter()


class AuthorizeResponse(BaseModel):
    """Response with the authorization URL to redirect to."""

    url: str
    provider: str


class TokenResponse(BaseModel):
    """Response after successful token exchange or refresh."""

    provider: str
    token_type: str = "bearer"
    scope: str = ""
    expires_at: float | None = None
    user_email: str | None = None
    user_name: str | None = None


class OAuthStatusResponse(BaseModel):
    """Status of all OAuth providers."""

    providers: list[dict[str, Any]]


class RevokeResponse(BaseModel):
    """Response after revocation."""

    provider: str
    revoked: bool


@router.get("/oauth/{provider}/authorize")
async def authorize(
    provider: str,
    request: Request,
    redirect_uri: str | None = Query(default=None),
    scopes: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
) -> AuthorizeResponse:
    """Build the OAuth authorization URL for the user to visit.

    Args:
        provider: OAuth provider name (github, google, etc.)
        redirect_uri: Where the provider should redirect after auth.
                      Defaults to /api/oauth/{provider}/callback.
        scopes: Comma-separated list of scopes (optional, uses provider defaults).
        session_id: Optional session to bind the token to.
    """
    if not redirect_uri:
        base = str(request.base_url).rstrip("/")
        redirect_uri = f"{base}/api/oauth/{provider}/callback"

    scope_list = scopes.split(",") if scopes else None

    try:
        url = oauth_manager.build_authorize_url(
            provider=provider,
            redirect_uri=redirect_uri,
            scopes=scope_list,
            session_id=session_id,
        )
    except OAuthError as exc:
        raise HTTPException(status_code=400, detail=exc.args[0]) from exc

    return AuthorizeResponse(url=url, provider=provider)


@router.get("/oauth/{provider}/callback")
async def callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> TokenResponse:
    """Handle OAuth callback from the provider.

    The provider redirects here with ?code=...&state=...
    """
    if error:
        detail = error_description or error
        raise HTTPException(status_code=400, detail=f"Provider denied: {detail}")

    try:
        token = await oauth_manager.exchange_code(state=state, code=code)
    except OAuthError as exc:
        raise HTTPException(status_code=400, detail=exc.args[0]) from exc

    return TokenResponse(
        provider=token.provider,
        token_type=token.token_type,
        scope=token.scope,
        expires_at=token.expires_at,
        user_email=token.user_email,
        user_name=token.user_name,
    )


@router.post("/oauth/{provider}/refresh")
async def refresh(
    provider: str,
    profile_id: str | None = Query(default=None),
) -> TokenResponse:
    """Refresh an expired OAuth token.

    Args:
        provider: OAuth provider name.
        profile_id: Specific auth profile to refresh (optional).
    """
    try:
        token = await oauth_manager.refresh_token(provider=provider, profile_id=profile_id)
    except OAuthError as exc:
        raise HTTPException(status_code=400, detail=exc.args[0]) from exc

    return TokenResponse(
        provider=token.provider,
        token_type=token.token_type,
        scope=token.scope,
        expires_at=token.expires_at,
        user_email=token.user_email,
        user_name=token.user_name,
    )


@router.get("/oauth/status")
async def status() -> OAuthStatusResponse:
    """Get OAuth connection status for all registered providers."""
    return OAuthStatusResponse(providers=oauth_manager.get_status())


@router.delete("/oauth/{provider}")
async def revoke(
    provider: str,
    profile_id: str | None = Query(default=None),
) -> RevokeResponse:
    """Revoke OAuth tokens and disconnect a provider.

    Args:
        provider: OAuth provider name.
        profile_id: Specific profile to revoke (optional, revokes all if omitted).
    """
    try:
        result = await oauth_manager.revoke(provider=provider, profile_id=profile_id)
    except OAuthError as exc:
        raise HTTPException(status_code=400, detail=exc.args[0]) from exc

    return RevokeResponse(provider=provider, revoked=result)
