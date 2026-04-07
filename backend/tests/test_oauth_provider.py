"""Tests for OAuth provider system."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.oauth_provider import (
    OAuthError,
    OAuthProviderConfig,
    OAuthProviderManager,
    OAuthToken,
    PendingAuth,
    PROVIDER_TEMPLATES,
)


@pytest.fixture
def manager():
    """Fresh OAuth manager for each test."""
    return OAuthProviderManager()


@pytest.fixture
def github_config():
    """GitHub OAuth config."""
    return OAuthProviderConfig(
        name="github",
        client_id="test_client_id",
        client_secret="test_client_secret",
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        userinfo_url="https://api.github.com/user",
        scopes=["repo", "read:user"],
    )


@pytest.fixture
def google_config():
    """Google OAuth config with PKCE."""
    return OAuthProviderConfig(
        name="google",
        client_id="google_client_id",
        client_secret="google_client_secret",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=["openid", "email"],
        pkce=True,
        extra_params={"access_type": "offline"},
    )


# --- Registration ---


class TestProviderRegistration:
    def test_register_provider(self, manager, github_config):
        manager.register_provider(github_config)
        assert "github" in manager.list_providers()
        assert manager.get_provider("github") is github_config

    def test_register_from_settings(self, manager):
        manager.register_from_settings("github", "cid", "csecret")
        p = manager.get_provider("github")
        assert p is not None
        assert p.client_id == "cid"
        assert p.client_secret == "csecret"
        assert p.authorize_url == PROVIDER_TEMPLATES["github"]["authorize_url"]

    def test_register_unknown_provider_no_url(self, manager):
        with pytest.raises(OAuthError, match="Unknown provider"):
            manager.register_from_settings("unknown", "cid", "csecret")

    def test_register_custom_provider_with_url(self, manager):
        manager.register_from_settings(
            "custom",
            "cid",
            "csecret",
            authorize_url="https://custom.example.com/auth",
            token_url="https://custom.example.com/token",
        )
        p = manager.get_provider("custom")
        assert p is not None
        assert p.authorize_url == "https://custom.example.com/auth"

    def test_list_providers_empty(self, manager):
        assert manager.list_providers() == []

    def test_get_nonexistent_provider(self, manager):
        assert manager.get_provider("nope") is None


# --- Authorization URL ---


class TestAuthorizeURL:
    def test_build_authorize_url(self, manager, github_config):
        manager.register_provider(github_config)
        url = manager.build_authorize_url("github", "http://localhost/callback")
        assert url.startswith("https://github.com/login/oauth/authorize?")
        assert "client_id=test_client_id" in url
        assert "redirect_uri=" in url
        assert "response_type=code" in url
        assert "state=" in url
        assert "scope=repo" in url

    def test_build_authorize_url_custom_scopes(self, manager, github_config):
        manager.register_provider(github_config)
        url = manager.build_authorize_url("github", "http://localhost/cb", scopes=["user:email"])
        assert "scope=user%3Aemail" in url

    def test_build_authorize_url_pkce(self, manager, google_config):
        manager.register_provider(google_config)
        url = manager.build_authorize_url("google", "http://localhost/cb")
        assert "code_challenge=" in url
        assert "code_challenge_method=S256" in url
        assert "access_type=offline" in url

    def test_build_authorize_url_creates_pending(self, manager, github_config):
        manager.register_provider(github_config)
        url = manager.build_authorize_url("github", "http://localhost/cb", session_id="sess_123")
        assert len(manager._pending) == 1
        pending = list(manager._pending.values())[0]
        assert pending.provider == "github"
        assert pending.session_id == "sess_123"

    def test_build_authorize_url_unknown_provider(self, manager):
        with pytest.raises(OAuthError, match="not registered"):
            manager.build_authorize_url("unknown", "http://localhost/cb")


# --- Token Exchange ---


class TestTokenExchange:
    @pytest.mark.asyncio
    async def test_exchange_code_invalid_state(self, manager):
        with pytest.raises(OAuthError, match="Invalid or expired state"):
            await manager.exchange_code("bad_state", "some_code")

    @pytest.mark.asyncio
    async def test_exchange_code_expired_state(self, manager, github_config):
        manager.register_provider(github_config)
        state = "test_state"
        manager._pending[state] = PendingAuth(
            provider="github",
            state=state,
            code_verifier=None,
            scopes=["repo"],
            redirect_uri="http://localhost/cb",
            created_at=time.time() - 700,  # 700s ago — expired
        )
        with pytest.raises(OAuthError, match="expired"):
            await manager.exchange_code(state, "code")

    @pytest.mark.asyncio
    async def test_exchange_code_success(self, manager, github_config):
        manager.register_provider(github_config)
        manager.build_authorize_url("github", "http://localhost/cb")
        state = list(manager._pending.keys())[0]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "gho_abc123",
            "token_type": "bearer",
            "scope": "repo,read:user",
            "expires_in": 3600,
        }

        mock_userinfo = MagicMock()
        mock_userinfo.status_code = 200
        mock_userinfo.json.return_value = {"login": "testuser", "email": "test@example.com"}

        with patch("backend.services.oauth_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client.get.return_value = mock_userinfo
            mock_client_cls.return_value = mock_client

            with patch("backend.services.oauth_provider.auth_profile_manager") as mock_apm:
                token = await manager.exchange_code(state, "auth_code_xyz")

        assert token.access_token == "gho_abc123"
        assert token.provider == "github"
        assert token.user_email == "test@example.com"
        assert token.expires_at is not None
        assert state not in manager._pending  # consumed

    @pytest.mark.asyncio
    async def test_exchange_code_provider_error(self, manager, github_config):
        manager.register_provider(github_config)
        manager.build_authorize_url("github", "http://localhost/cb")
        state = list(manager._pending.keys())[0]

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        with patch("backend.services.oauth_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            with pytest.raises(OAuthError, match="exchange failed"):
                await manager.exchange_code(state, "bad_code")


# --- Token Refresh ---


class TestTokenRefresh:
    @pytest.mark.asyncio
    async def test_refresh_unknown_provider(self, manager):
        with pytest.raises(OAuthError, match="not registered"):
            await manager.refresh_token("unknown")

    @pytest.mark.asyncio
    async def test_refresh_no_refresh_token(self, manager, github_config):
        manager.register_provider(github_config)
        with patch("backend.services.oauth_provider.auth_profile_manager") as mock_apm:
            mock_apm.get_profiles_for_provider.return_value = []
            with pytest.raises(OAuthError, match="No refreshable token"):
                await manager.refresh_token("github")

    @pytest.mark.asyncio
    async def test_refresh_success(self, manager, github_config):
        from backend.services.advanced_fallback.auth_profiles import (
            AuthProfile,
            AuthProfileCredential,
            ProfileUsageStats,
        )

        manager.register_provider(github_config)

        existing_profile = AuthProfile(
            credential=AuthProfileCredential(
                profile_id="oauth_github_1234",
                provider="github",
                type="oauth",
                token="old_token",
                refresh_token="refresh_abc",
                expires_at=time.time() - 100,  # expired
                email="user@test.com",
                display_name="Test User",
            ),
            stats=ProfileUsageStats(),
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_token_xyz",
            "token_type": "bearer",
            "expires_in": 7200,
            "refresh_token": "new_refresh_abc",
        }

        with patch("backend.services.oauth_provider.auth_profile_manager") as mock_apm:
            mock_apm.get_profiles_for_provider.return_value = [existing_profile]

            with patch("backend.services.oauth_provider.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.post.return_value = mock_response
                mock_client_cls.return_value = mock_client

                token = await manager.refresh_token("github")

        assert token.access_token == "new_token_xyz"
        assert token.refresh_token == "new_refresh_abc"
        assert token.user_email == "user@test.com"


# --- Revocation ---


class TestRevocation:
    @pytest.mark.asyncio
    async def test_revoke_unknown_provider(self, manager):
        with pytest.raises(OAuthError, match="not registered"):
            await manager.revoke("unknown")

    @pytest.mark.asyncio
    async def test_revoke_no_profiles(self, manager, github_config):
        manager.register_provider(github_config)
        with patch("backend.services.oauth_provider.auth_profile_manager") as mock_apm:
            mock_apm.get_profiles_for_provider.return_value = []
            with pytest.raises(OAuthError, match="No OAuth profiles"):
                await manager.revoke("github")

    @pytest.mark.asyncio
    async def test_revoke_success(self, manager, github_config):
        from backend.services.advanced_fallback.auth_profiles import (
            AuthProfile,
            AuthProfileCredential,
            ProfileUsageStats,
        )

        manager.register_provider(github_config)

        profile = AuthProfile(
            credential=AuthProfileCredential(
                profile_id="oauth_github_1234",
                provider="github",
                type="oauth",
                token="some_token",
            ),
            stats=ProfileUsageStats(),
        )

        with patch("backend.services.oauth_provider.auth_profile_manager") as mock_apm:
            mock_apm.get_profiles_for_provider.return_value = [profile]

            with patch("backend.services.oauth_provider.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.delete.return_value = AsyncMock(status_code=204)
                mock_client_cls.return_value = mock_client

                result = await manager.revoke("github")

        assert result is True
        mock_apm.remove_profile.assert_called_once_with("oauth_github_1234")


# --- Status ---


class TestStatus:
    def test_status_empty(self, manager):
        assert manager.get_status() == []

    def test_status_with_provider(self, manager, github_config):
        manager.register_provider(github_config)
        with patch("backend.services.oauth_provider.auth_profile_manager") as mock_apm:
            mock_apm.get_profiles_for_provider.return_value = []
            statuses = manager.get_status()
            assert len(statuses) == 1
            assert statuses[0]["provider"] == "github"
            assert statuses[0]["connected"] is False
            assert statuses[0]["profiles"] == 0


# --- OAuthToken ---


class TestOAuthToken:
    def test_token_not_expired(self):
        t = OAuthToken(access_token="abc", expires_at=time.time() + 3600)
        assert t.is_expired is False

    def test_token_expired(self):
        t = OAuthToken(access_token="abc", expires_at=time.time() - 100)
        assert t.is_expired is True

    def test_token_no_expiry(self):
        t = OAuthToken(access_token="abc")
        assert t.is_expired is False

    def test_token_grace_window(self):
        """Token should be considered expired within 60s grace window."""
        t = OAuthToken(access_token="abc", expires_at=time.time() + 30)
        assert t.is_expired is True  # within 60s grace


# --- Pending Cleanup ---


class TestPendingCleanup:
    def test_cleanup_expired_pending(self, manager, github_config):
        manager.register_provider(github_config)
        # Create pending with old timestamp
        manager._pending["old_state"] = PendingAuth(
            provider="github",
            state="old_state",
            code_verifier=None,
            scopes=["repo"],
            redirect_uri="http://localhost/cb",
            created_at=time.time() - 700,
        )
        manager._pending["new_state"] = PendingAuth(
            provider="github",
            state="new_state",
            code_verifier=None,
            scopes=["repo"],
            redirect_uri="http://localhost/cb",
            created_at=time.time(),
        )
        cleaned = manager.cleanup_expired_pending()
        assert cleaned == 1
        assert "old_state" not in manager._pending
        assert "new_state" in manager._pending


# --- Provider Templates ---


class TestProviderTemplates:
    def test_github_template_exists(self):
        assert "github" in PROVIDER_TEMPLATES
        t = PROVIDER_TEMPLATES["github"]
        assert "authorize_url" in t
        assert "token_url" in t

    def test_google_template_exists(self):
        assert "google" in PROVIDER_TEMPLATES
        t = PROVIDER_TEMPLATES["google"]
        assert t["pkce"] is True
        assert "access_type" in t.get("extra_params", {})
