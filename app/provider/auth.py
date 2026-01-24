"""
Authentication Context
======================

This module handles authentication mode selection (OAuth vs API key)
and provides request headers/body configuration for each mode.

Auth Selection Flow
-------------------

    ┌─────────────────────────────────────────────────────────────────┐
    │                  AuthContext.from_environment()                 │
    └─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                       ┌────────────────────┐
                       │  SMOLCODE_OAUTH=1? │
                       └─────────┬──────────┘
                ┌────────────────┴────────────────┐
                ▼                                 ▼
          ┌───────────┐                    ┌─────────────┐
          │    yes    │                    │     no      │
          └─────┬─────┘                    └──────┬──────┘
                ▼                                 ▼
       ┌─────────────────┐              ┌─────────────────┐
       │ TokenManager    │              │ OPENAI_API_KEY? │
       │ .get_tokens()   │              └────────┬────────┘
       └────────┬────────┘                       │
                │                        ┌───────┴────────┐
       ┌────────┴────────┐               ▼                ▼
       ▼                 ▼          ┌─────────┐     ┌───────────┐
  ┌─────────┐     ┌────────────┐    │   set   │     │  not set  │
  │  valid  │     │   none     │    └────┬────┘     └─────┬─────┘
  └────┬────┘     └──────┬─────┘         │                │
       │                 │               ▼                ▼
       ▼                 ▼         ┌────────────┐   ┌─────────────┐
  ┌───────────┐   ┌───────────────┐│ AuthContext│   │RuntimeError │
  │AuthContext│   │OAuthNotLogged ││ mode=      │   └─────────────┘
  │mode=oauth │   │InError        ││ api_key    │
  └───────────┘   └───────────────┘└────────────┘
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .login import LoginFlow
from .oauth_token import DEFAULT_ORIGINATOR, TokenManager, Tokens

OPENAI_API_URL = "https://api.openai.com/v1/responses"
CODEX_API_URL = "https://chatgpt.com/backend-api/codex/responses"
DEFAULT_HOME = Path("~/.config/smolcode").expanduser()


@dataclass(slots=True)
class AuthContext:
    mode: Literal["oauth", "api_key"]
    base_url: str
    api_key: str | None = None
    token_manager: TokenManager | None = None

    @classmethod
    def from_environment(cls, home: Path = DEFAULT_HOME) -> "AuthContext":
        use_oauth = _truthy(os.getenv("SMOLCODE_OAUTH"))
        api_key = os.getenv("OPENAI_API_KEY")

        if use_oauth:
            manager = TokenManager(home=home)
            tokens = manager.get_tokens()
            if tokens and tokens.access_token:
                return cls(
                    mode="oauth",
                    base_url=CODEX_API_URL,
                    token_manager=manager,
                )
            raise RuntimeError(
                "OAuth is enabled but no valid token was found. "
                "Run `smolcode login` to authenticate, then rerun the command."
            )

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set and SMOLCODE_OAUTH is disabled."
            )

        return cls(
            mode="api_key",
            base_url=OPENAI_API_URL,
            api_key=api_key,
        )

    def get_token(self) -> str:
        if self.mode == "api_key":
            if not self.api_key:
                raise RuntimeError("OPENAI_API_KEY is missing.")
            return self.api_key

        tokens = self.get_oauth_tokens()
        return tokens.access_token

    def get_base_url(self) -> str:
        return self.base_url

    def request_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        if self.mode == "api_key":
            headers["Authorization"] = f"Bearer {self.get_token()}"
            return headers

        tokens = self.get_oauth_tokens()
        headers["Authorization"] = f"Bearer {tokens.access_token}"
        if tokens.account_id:
            headers["ChatGPT-Account-Id"] = tokens.account_id
        headers["User-Agent"] = DEFAULT_ORIGINATOR
        return headers

    def get_oauth_tokens(self) -> Tokens:
        if self.mode != "oauth" or not self.token_manager:
            raise RuntimeError("OAuth authentication is not enabled.")
        tokens = self.token_manager.get_tokens()
        if not tokens or not tokens.access_token:
            raise RuntimeError("OAuth token missing. Re-run login.")
        return tokens

    @classmethod
    def login_oauth(cls, home: Path = DEFAULT_HOME) -> Tokens:
        manager = TokenManager(home=home)
        flow = LoginFlow(
            home=home,
            issuer=manager.issuer,
            client_id=manager.client_id,
            scope=manager.scope,
            redirect_uri=manager.redirect_uri,
            originator=manager.originator,
        )
        return flow.run()


def _truthy(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}
