"""OAuth2 Provider — authorization code flow with PKCE.

Supports GitHub, Google, and custom OAuth2 providers.
Integrates with auth_profiles for credential storage and rotation.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import httpx

from backend.services.advanced_fallback.auth_profiles import (
    AuthProfile,
    AuthProfileCredential,
    ProfileUsageStats,
    auth_profile_manager,
)

logger = logging.getLogger("tenderclaw.services.oauth")


class OAuthError(Exception):
    """OAuth flow error."""

    def __init__(self, message: str, code: str = "oauth_error"):
        self.code = code
        super().__init__(message)


class OAuthScope(str, Enum):
    """Standard scopes across providers."""

    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    REPO = "repo"
    USER = "user"


@dataclass
class OAuthProviderConfig:
    """Configuration for a single OAuth2 provider."""

    name: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    revoke_url: str = ""
    userinfo_url: str = ""
    scopes: list[str] = field(default_factory=list)
    scope_separator: str = " "
    pkce: bool = False
    extra_params: dict[str, str] = field(default_factory=dict)


# Built-in provider templates (client_id/secret filled from config)
PROVIDER_TEMPLATES: dict[str, dict[str, Any]] = {
    "github": {
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "revoke_url": "https://api.github.com/applications/{client_id}/token",
        "userinfo_url": "https://api.github.com/user",
        "scopes": ["repo", "read:user", "user:email"],
        "scope_separator": " ",
        "pkce": False,
    },
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "revoke_url": "https://oauth2.googleapis.com/revoke",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "scopes": ["openid", "email", "profile"],
        "scope_separator": " ",
        "pkce": True,
        "extra_params": {"access_type": "offline", "prompt": "consent"},
    },
}


@dataclass
class PendingAuth:
    """Tracks an in-flight OAuth authorization."""

    provider: str
    state: str
    code_verifier: str | None  # PKCE
    scopes: list[str]
    redirect_uri: str
    created_at: float = field(default_factory=time.time)
    session_id: str | None = None


@dataclass
class OAuthToken:
    """Resolved OAuth token."""

    access_token: str
    token_type: str = "bearer"
    expires_at: float | None = None
    refresh_token: str | None = None
    scope: str = ""
    provider: str = ""
    user_email: str | None = None
    user_name: str | None = None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at - 60  # 60s grace window


class OAuthProviderManager:
    """Manages OAuth2 flows for multiple providers.

    Handles:
    - Provider registration and configuration
    - Authorization URL generation with state and PKCE
    - Authorization code → token exchange
    - Token refresh
    - Credential storage via auth_profiles
    """

    def __init__(self) -> None:
        self._providers: dict[str, OAuthProviderConfig] = {}
        self._pending: dict[str, PendingAuth] = {}  # keyed by state
        self._state_secret = secrets.token_hex(32)

    def register_provider(self, config: OAuthProviderConfig) -> None:
        """Register an OAuth provider."""
        self._providers[config.name] = config
        logger.info("Registered OAuth provider: %s", config.name)

    def register_from_settings(
        self,
        provider: str,
        client_id: str,
        client_secret: str,
        **overrides: Any,
    ) -> None:
        """Register a provider using built-in templates + credentials."""
        template = PROVIDER_TEMPLATES.get(provider, {})
        if not template and not overrides.get("authorize_url"):
            raise OAuthError(f"Unknown provider '{provider}' and no authorize_url given", "unknown_provider")

        merged = {**template, **overrides}
        config = OAuthProviderConfig(
            name=provider,
            client_id=client_id,
            client_secret=client_secret,
            **merged,
        )
        self.register_provider(config)

    def get_provider(self, name: str) -> OAuthProviderConfig | None:
        return self._providers.get(name)

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())

    # --- Authorization ---

    def build_authorize_url(
        self,
        provider: str,
        redirect_uri: str,
        scopes: list[str] | None = None,
        session_id: str | None = None,
    ) -> str:
        """Build the authorization URL for the user to visit.

        Returns the full URL with state, scope, and optional PKCE challenge.
        """
        config = self._providers.get(provider)
        if not config:
            raise OAuthError(f"Provider '{provider}' not registered", "provider_not_found")

        state = self._generate_state(provider)
        effective_scopes = scopes or config.scopes

        code_verifier = None
        params: dict[str, str] = {
            "client_id": config.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
            "scope": config.scope_separator.join(effective_scopes),
        }

        if config.pkce:
            code_verifier = secrets.token_urlsafe(64)
            challenge = hashlib.sha256(code_verifier.encode()).digest()
            import base64
            code_challenge = base64.urlsafe_b64encode(challenge).rstrip(b"=").decode()
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        params.update(config.extra_params)

        self._pending[state] = PendingAuth(
            provider=provider,
            state=state,
            code_verifier=code_verifier,
            scopes=effective_scopes,
            redirect_uri=redirect_uri,
            session_id=session_id,
        )

        query = "&".join(f"{k}={_url_encode(v)}" for k, v in params.items())
        return f"{config.authorize_url}?{query}"

    # --- Token Exchange ---

    async def exchange_code(self, state: str, code: str) -> OAuthToken:
        """Exchange authorization code for tokens.

        Args:
            state: The state parameter from the callback.
            code: The authorization code from the callback.

        Returns:
            OAuthToken with access and refresh tokens.
        """
        pending = self._pending.pop(state, None)
        if not pending:
            raise OAuthError("Invalid or expired state parameter", "invalid_state")

        if time.time() - pending.created_at > 600:
            raise OAuthError("Authorization request expired (>10 min)", "state_expired")

        config = self._providers.get(pending.provider)
        if not config:
            raise OAuthError(f"Provider '{pending.provider}' no longer registered", "provider_not_found")

        payload: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": pending.redirect_uri,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        }

        if pending.code_verifier:
            payload["code_verifier"] = pending.code_verifier

        headers = {"Accept": "application/json"}
        async with httpx.AsyncClient() as client:
            resp = await client.post(config.token_url, data=payload, headers=headers, timeout=15.0)

        if resp.status_code != 200:
            body = resp.text
            logger.error("Token exchange failed for %s: %d %s", pending.provider, resp.status_code, body)
            raise OAuthError(f"Token exchange failed: {resp.status_code}", "exchange_failed")

        data = resp.json()
        if "error" in data:
            raise OAuthError(f"Provider error: {data['error']}: {data.get('error_description', '')}", "provider_error")

        expires_at = None
        if "expires_in" in data:
            expires_at = time.time() + int(data["expires_in"])

        token = OAuthToken(
            access_token=data["access_token"],
            token_type=data.get("token_type", "bearer"),
            expires_at=expires_at,
            refresh_token=data.get("refresh_token"),
            scope=data.get("scope", config.scope_separator.join(pending.scopes)),
            provider=pending.provider,
        )

        # Fetch user info if available
        if config.userinfo_url:
            try:
                token.user_email, token.user_name = await self._fetch_userinfo(config, token.access_token)
            except Exception as exc:
                logger.debug("Failed to fetch user info for %s: %s", pending.provider, exc)

        # Persist to auth profiles
        self._store_token(token, session_id=pending.session_id)

        logger.info("OAuth token acquired for provider=%s user=%s", pending.provider, token.user_email or "unknown")
        return token

    # --- Token Refresh ---

    async def refresh_token(self, provider: str, profile_id: str | None = None) -> OAuthToken:
        """Refresh an expired OAuth token.

        Args:
            provider: The OAuth provider name.
            profile_id: Specific profile to refresh. If None, finds first refreshable.

        Returns:
            New OAuthToken with updated access token.
        """
        config = self._providers.get(provider)
        if not config:
            raise OAuthError(f"Provider '{provider}' not registered", "provider_not_found")

        # Find the profile with a refresh token
        profiles = auth_profile_manager.get_profiles_for_provider(provider)
        target = None
        for p in profiles:
            if p.credential.type == "oauth" and p.credential.refresh_token:
                if profile_id is None or p.profile_id == profile_id:
                    target = p
                    break

        if not target or not target.credential.refresh_token:
            raise OAuthError(f"No refreshable token found for '{provider}'", "no_refresh_token")

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": target.credential.refresh_token,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        }

        headers = {"Accept": "application/json"}
        async with httpx.AsyncClient() as client:
            resp = await client.post(config.token_url, data=payload, headers=headers, timeout=15.0)

        if resp.status_code != 200:
            logger.error("Token refresh failed for %s: %d", provider, resp.status_code)
            auth_profile_manager.mark_profile_failure(
                target.profile_id,
                reason=_auth_failure_reason(),
            )
            raise OAuthError(f"Token refresh failed: {resp.status_code}", "refresh_failed")

        data = resp.json()
        if "error" in data:
            raise OAuthError(f"Refresh error: {data['error']}", "provider_error")

        expires_at = None
        if "expires_in" in data:
            expires_at = time.time() + int(data["expires_in"])

        new_token = OAuthToken(
            access_token=data["access_token"],
            token_type=data.get("token_type", "bearer"),
            expires_at=expires_at,
            refresh_token=data.get("refresh_token", target.credential.refresh_token),
            scope=data.get("scope", ""),
            provider=provider,
            user_email=target.credential.email,
            user_name=target.credential.display_name,
        )

        self._store_token(new_token, profile_id=target.profile_id)
        logger.info("OAuth token refreshed for provider=%s profile=%s", provider, target.profile_id)
        return new_token

    # --- Revocation ---

    async def revoke(self, provider: str, profile_id: str | None = None) -> bool:
        """Revoke an OAuth token and remove the profile.

        Args:
            provider: The OAuth provider name.
            profile_id: Specific profile to revoke. If None, revokes all for provider.

        Returns:
            True if revocation succeeded.
        """
        config = self._providers.get(provider)
        if not config:
            raise OAuthError(f"Provider '{provider}' not registered", "provider_not_found")

        profiles = auth_profile_manager.get_profiles_for_provider(provider)
        targets = [p for p in profiles if p.credential.type == "oauth"]
        if profile_id:
            targets = [p for p in targets if p.profile_id == profile_id]

        if not targets:
            raise OAuthError(f"No OAuth profiles found for '{provider}'", "not_found")

        for target in targets:
            if config.revoke_url and target.credential.token:
                try:
                    await self._revoke_remote(config, target.credential.token)
                except Exception as exc:
                    logger.warning("Remote revocation failed for %s: %s", provider, exc)

            auth_profile_manager.remove_profile(target.profile_id)
            logger.info("Revoked OAuth profile %s for %s", target.profile_id, provider)

        return True

    # --- Status ---

    def get_status(self) -> list[dict[str, Any]]:
        """Get OAuth status for all registered providers."""
        result = []
        for name in self._providers:
            profiles = auth_profile_manager.get_profiles_for_provider(name)
            oauth_profiles = [p for p in profiles if p.credential.type == "oauth"]

            connected = any(
                not p.credential.is_expired and p.is_usable
                for p in oauth_profiles
            )

            result.append({
                "provider": name,
                "connected": connected,
                "profiles": len(oauth_profiles),
                "scopes": self._providers[name].scopes,
                "users": [
                    {
                        "profile_id": p.profile_id,
                        "email": p.credential.email,
                        "display_name": p.credential.display_name,
                        "expired": p.credential.is_expired,
                        "usable": p.is_usable,
                    }
                    for p in oauth_profiles
                ],
            })
        return result

    def get_valid_token(self, provider: str) -> str | None:
        """Get a valid (non-expired) access token for a provider, if available."""
        profiles = auth_profile_manager.get_profiles_for_provider(provider)
        for p in profiles:
            if p.credential.type == "oauth" and not p.credential.is_expired and p.is_usable:
                return p.credential.token
        return None

    # --- Internal ---

    def _generate_state(self, provider: str) -> str:
        """Generate a CSRF-safe state parameter."""
        nonce = secrets.token_urlsafe(32)
        sig = hmac.new(
            self._state_secret.encode(),
            f"{provider}:{nonce}".encode(),
            hashlib.sha256,
        ).hexdigest()[:16]
        return f"{nonce}.{sig}"

    def _store_token(
        self,
        token: OAuthToken,
        profile_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Store OAuth token in auth profiles."""
        pid = profile_id or f"oauth_{token.provider}_{secrets.token_hex(4)}"
        credential = AuthProfileCredential(
            profile_id=pid,
            provider=token.provider,
            type="oauth",
            token=token.access_token,
            refresh_token=token.refresh_token,
            expires_at=token.expires_at,
            email=token.user_email,
            display_name=token.user_name,
        )
        profile = AuthProfile(credential=credential, stats=ProfileUsageStats())
        auth_profile_manager.add_profile(profile)

    async def _fetch_userinfo(self, config: OAuthProviderConfig, access_token: str) -> tuple[str | None, str | None]:
        """Fetch user info from the provider."""
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(config.userinfo_url, headers=headers, timeout=10.0)

        if resp.status_code != 200:
            return None, None

        data = resp.json()
        email = data.get("email") or data.get("mail")
        name = data.get("name") or data.get("login") or data.get("displayName")
        return email, name

    async def _revoke_remote(self, config: OAuthProviderConfig, token: str) -> None:
        """Call the provider's revocation endpoint."""
        if not config.revoke_url:
            return

        url = config.revoke_url.replace("{client_id}", config.client_id)

        async with httpx.AsyncClient() as client:
            if "github" in config.name:
                # GitHub uses Basic auth for revocation
                await client.delete(
                    url,
                    auth=(config.client_id, config.client_secret),
                    json={"access_token": token},
                    timeout=10.0,
                )
            else:
                await client.post(
                    url,
                    data={"token": token},
                    timeout=10.0,
                )

    def cleanup_expired_pending(self, max_age: float = 600) -> int:
        """Remove expired pending auth requests."""
        now = time.time()
        expired = [s for s, p in self._pending.items() if now - p.created_at > max_age]
        for s in expired:
            del self._pending[s]
        return len(expired)


def _url_encode(value: str) -> str:
    """URL-encode a value."""
    from urllib.parse import quote
    return quote(str(value), safe="")


def _auth_failure_reason():
    """Get the FailoverReason for auth failure."""
    from backend.services.advanced_fallback.errors import FailoverReason
    return FailoverReason.AUTH


# Singleton
oauth_manager = OAuthProviderManager()
