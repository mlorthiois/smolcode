"""
OAuth Token Management
======================

This module handles OAuth token storage, loading, refresh, and JWT parsing.

Token Lifecycle
---------------

    ┌─────────────────────────────────────────────────────────────────┐
    │                        TokenManager                             │
    └─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                         ┌───────────────┐
                         │  get_tokens() │
                         └───────┬───────┘
                                 │
                                 ▼
                        ┌────────────────┐
                        │  load_tokens() │
                        │  from disk     │
                        └───────┬────────┘
                                │
               ┌────────────────┼────────────────┐
               ▼                ▼                ▼
          ┌─────────┐    ┌────────────┐    ┌──────────┐
          │ (none)  │    │   valid    │    │ expired  │
          │         │    │   token    │    │  token   │
          └────┬────┘    └─────┬──────┘    └────┬─────┘
               │               │                │
               ▼               │                ▼
           ┌──────┐            │         ┌──────────┐
           │ None │            │         │ refresh  │
           └──────┘            │         └────┬─────┘
                               │              │
                               │              ▼
                               │       ┌─────────────┐
                               │       │ save_tokens │
                               │       │  (0o600)    │
                               │       └──────┬──────┘
                               │              │
                               └──────┬───────┘
                                      ▼
                                  ┌────────┐
                                  │ Tokens │
                                  └────────┘

Token Storage (~/.config/smolcode/auth.json)
--------------------------------------------

    {
      "access_token": "eyJ...",
      "refresh_token": "v1.xxx...",
      "id_token": "eyJ...",
      "account_id": "org-xxx",
      "expires_at": 1234567890
    }

"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

# ---- Config / constants ----

DEFAULT_ISSUER: Final[str] = "https://auth.openai.com"
DEFAULT_CLIENT_ID: Final[str] = "app_EMoamEEZ73f0CkXaXp7hrann"
DEFAULT_SCOPE: Final[str] = "openid profile email offline_access"
DEFAULT_REDIRECT_URI: Final[str] = "http://localhost:1455/auth/callback"
DEFAULT_ORIGINATOR: Final[str] = "mlorthiois/smolcode"
AUTH_FILE_NAME: Final[str] = "auth.json"

AUTH_INFO_URL: Final[str] = "https://api.openai.com/auth"
AUTH_INFO_ACCOUNT_ID: Final[str] = "chatgpt_account_id"


def _b64url_decode(segment: str) -> bytes:
    padded = segment + "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(padded)


def parse_jwt_claims(token: str) -> dict[str, Any] | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        return json.loads(_b64url_decode(parts[1]))
    except Exception:
        return None


def extract_account_id_from_claims(claims: dict[str, Any] | None) -> str:
    if not isinstance(claims, dict):
        return ""

    direct = claims.get("chatgpt_account_id")
    if direct:
        return str(direct)

    auth_info = claims.get(AUTH_INFO_URL)
    if isinstance(auth_info, dict):
        account_id = auth_info.get(AUTH_INFO_ACCOUNT_ID)
        if account_id:
            return str(account_id)

    organizations = claims.get("organizations")
    if isinstance(organizations, list) and organizations:
        org = organizations[0]
        if isinstance(org, dict) and org.get("id"):
            return str(org["id"])

    return ""


def extract_account_id(tokens: dict[str, Any]) -> str:
    for key in ("id_token", "access_token"):
        raw = tokens.get(key)
        if isinstance(raw, str) and raw:
            claims = parse_jwt_claims(raw)
            account_id = extract_account_id_from_claims(claims)
            if account_id:
                return account_id
    return ""


def http_post_form(
    url: str, payload: dict[str, str], timeout: float = 20.0
) -> tuple[int, dict[str, Any] | str]:
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": DEFAULT_ORIGINATOR,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return status, json.loads(raw)
            except json.JSONDecodeError:
                return status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw
    except urllib.error.URLError as exc:
        return 0, str(exc)


def refresh_access_token(
    *,
    issuer: str,
    client_id: str,
    refresh_token: str,
) -> dict[str, Any]:
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    status, body = http_post_form(f"{issuer.rstrip('/')}/oauth/token", payload)
    if status != 200 or not isinstance(body, dict):
        raise RuntimeError(f"Token refresh failed (status={status}): {body}")
    return body


@dataclass(slots=True)
class Tokens:
    access_token: str
    refresh_token: str
    id_token: str
    account_id: str = ""
    expires_at: int | None = None

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> "Tokens":
        expires_at = _expires_at_from_payload(data)
        return cls(
            access_token=str(data.get("access_token", "")),
            refresh_token=str(data.get("refresh_token", "")),
            id_token=str(data.get("id_token", "")),
            expires_at=expires_at,
        )


def _expires_at_from_payload(data: dict[str, Any]) -> int | None:
    raw = data.get("expires_in")
    if isinstance(raw, (int, float)):
        return int(time.time() + int(raw))
    if isinstance(raw, str) and raw.isdigit():
        return int(time.time() + int(raw))
    return None


def load_tokens(path: Path) -> Tokens | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    expires_at: int | None = None
    raw_expires = data.get("expires_at")
    if isinstance(raw_expires, (int, float)):
        expires_at = int(raw_expires)
    elif isinstance(raw_expires, str) and raw_expires.isdigit():
        expires_at = int(raw_expires)

    return Tokens(
        access_token=str(data.get("access_token", "")),
        refresh_token=str(data.get("refresh_token", "")),
        id_token=str(data.get("id_token", "")),
        account_id=str(data.get("account_id", "")),
        expires_at=expires_at,
    )


def save_tokens(path: Path, tokens: Tokens) -> None:
    payload: dict[str, Any] = {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "id_token": tokens.id_token,
        "account_id": tokens.account_id,
    }
    if tokens.expires_at is not None:
        payload["expires_at"] = tokens.expires_at
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    path.chmod(0o600)


@dataclass(slots=True)
class TokenManager:
    home: Path
    issuer: str = DEFAULT_ISSUER
    client_id: str = DEFAULT_CLIENT_ID
    scope: str = DEFAULT_SCOPE
    redirect_uri: str = DEFAULT_REDIRECT_URI
    originator: str = DEFAULT_ORIGINATOR
    refresh_skew_seconds: int = 60

    @property
    def store_path(self) -> Path:
        return self.home / AUTH_FILE_NAME

    def load(self) -> Tokens | None:
        return load_tokens(self.store_path)

    def needs_refresh(self, tokens: Tokens) -> bool:
        if tokens.expires_at is None:
            return False
        return tokens.expires_at <= int(time.time()) + self.refresh_skew_seconds

    def refresh(self, tokens: Tokens) -> Tokens:
        payload = refresh_access_token(
            issuer=self.issuer,
            client_id=self.client_id,
            refresh_token=tokens.refresh_token,
        )
        refreshed = Tokens.from_response(payload)
        if not refreshed.refresh_token:
            refreshed.refresh_token = tokens.refresh_token
        if not refreshed.id_token:
            refreshed.id_token = tokens.id_token
        refreshed.account_id = extract_account_id(payload) or tokens.account_id
        save_tokens(self.store_path, refreshed)
        return refreshed

    def get_tokens(self) -> Tokens | None:
        tokens = self.load()
        if tokens and tokens.refresh_token:
            if not self.needs_refresh(tokens):
                return tokens
            try:
                return self.refresh(tokens)
            except Exception:
                return None
        return None

    def get_access_token(self) -> str | None:
        tokens = self.get_tokens()
        if not tokens:
            return None
        return tokens.access_token or None
