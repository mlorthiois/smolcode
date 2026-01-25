"""
OAuth Login Flow Sequence
=======================

    ┌──────┐          ┌─────────┐         ┌────────────┐        ┌──────────┐
    │ CLI  │          │ Browser │         │ Auth Server│        │ Callback │
    └──┬───┘          └────┬────┘         └─────┬──────┘        └────┬─────┘
       │                   │                    │                    │
       │  1. Generate PKCE pair                 │                    │
       │     (verifier + challenge)             │                    │
       │                   │                    │                    │
       │  2. Start local HTTP server ───────────────────────────────►│
       │     on localhost:1455                  │                    │
       │                   │                    │                    │
       │  3. Print authorize URL                │                    │
       │──────────────────►│                    │                    │
       │                   │                    │                    │
       │                   │  4. User opens URL │                    │
       │                   │───────────────────►│                    │
       │                   │                    │                    │
       │                   │  5. User logs in   │                    │
       │                   │◄──────────────────►│                    │
       │                   │                    │                    │
       │                   │  6. Redirect with  │                    │
       │                   │     auth code      │                    │
       │                   │◄───────────────────│                    │
       │                   │                    │                    │
       │                   │  7. Browser hits   │                    │
       │                   │     callback       │                    │
       │                   │────────────────────────────────────────►│
       │                   │                    │                    │
       │  8. Callback server receives code ◄─────────────────────────│
       │                   │                    │                    │
       │  9. Exchange code + verifier ─────────►│                    │
       │     for tokens                         │                    │
       │                   │                    │                    │
       │  10. Receive tokens ◄──────────────────│                    │
       │                   │                    │                    │
       │  11. Save tokens to disk               │                    │
       │                   │                    │                    │
    ┌──┴───┐          ┌────┴────┐         ┌─────┴──────┐        ┌────┴─────┐
    │ CLI  │          │ Browser │         │ Auth Server│        │ Callback │
    └──────┘          └─────────┘         └────────────┘        └──────────┘
"""

import base64
import hashlib
import http.server
import secrets
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from .oauth_token import (
    AUTH_FILE_NAME,
    DEFAULT_CLIENT_ID,
    DEFAULT_ISSUER,
    DEFAULT_ORIGINATOR,
    DEFAULT_REDIRECT_URI,
    DEFAULT_SCOPE,
    Tokens,
    http_post_form,
    save_tokens,
)

DEFAULT_TIMEOUT_SECONDS: Final[int] = 5 * 60

HTML_SUCCESS: Final[str] = """<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Codex Authorization Successful</title>
  </head>
  <body>
    <h1>Authorization Successful</h1>
    <p>You can close this window and return to the CLI.</p>
    <script>
      setTimeout(() => window.close(), 2000)
    </script>
  </body>
</html>
"""


def _html_error(message: str) -> str:
    safe_message = message.replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Codex Authorization Failed</title>
  </head>
  <body>
    <h1>Authorization Failed</h1>
    <p>{safe_message}</p>
  </body>
</html>
"""


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


@dataclass(slots=True)
class LoginFlow:
    home: Path
    issuer: str = DEFAULT_ISSUER
    client_id: str = DEFAULT_CLIENT_ID
    scope: str = DEFAULT_SCOPE
    redirect_uri: str = DEFAULT_REDIRECT_URI
    originator: str = DEFAULT_ORIGINATOR
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    def run(self) -> Tokens:
        verifier, challenge = self._generate_pkce_pair()
        state = self._generate_state()
        authorize_url = self._build_authorize_url(challenge, state)

        self._print_instructions(authorize_url)
        authorization_code = self._wait_for_authorization_code(state)

        token_payload = self._exchange_code_for_tokens(authorization_code, verifier)
        tokens = Tokens.from_response(token_payload)

        save_tokens(self.home / AUTH_FILE_NAME, tokens)
        return tokens

    def _generate_pkce_pair(self) -> tuple[str, str]:
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
        verifier = "".join(secrets.choice(chars) for _ in range(43))
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = _b64url_encode(digest)
        return verifier, challenge

    def _generate_state(self) -> str:
        return _b64url_encode(secrets.token_bytes(32))

    def _build_authorize_url(self, code_challenge: str, state: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scope,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
            "state": state,
            "originator": self.originator,
        }
        query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        return f"{self.issuer.rstrip('/')}/oauth/authorize?{query}"

    def _print_instructions(self, authorize_url: str) -> None:
        print("1) Open this link in your browser and sign in:")
        print(f"   {authorize_url}\n")
        print("2) Complete the sign-in flow in your browser.\n")
        print(f"Waiting for authorization on {self.redirect_uri}...")

    def _exchange_code_for_tokens(
        self, authorization_code: str, code_verifier: str
    ) -> dict[str, Any]:
        payload = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "code_verifier": code_verifier,
        }
        status, body = http_post_form(f"{self.issuer.rstrip('/')}/oauth/token", payload)
        if status != 200 or not isinstance(body, dict):
            raise RuntimeError(f"Token exchange failed (status={status}): {body}")
        return body

    def _wait_for_authorization_code(self, expected_state: str) -> str:
        redirect = urllib.parse.urlparse(self.redirect_uri)
        if redirect.scheme not in ("http", "https"):
            raise ValueError("redirect_uri must be http or https")

        host = redirect.hostname or "localhost"
        port = redirect.port or (443 if redirect.scheme == "https" else 80)
        path = redirect.path or "/"

        code: str | None = None
        error: str | None = None

        class CallbackHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(handler_self) -> None:
                nonlocal code, error
                parsed = urllib.parse.urlparse(handler_self.path)
                if parsed.path != path:
                    handler_self._send_html(404, _html_error("Not found"))
                    return

                params = urllib.parse.parse_qs(parsed.query)
                code_param = params.get("code", [""])[0]
                state_param = params.get("state", [""])[0]
                error_param = params.get("error", [""])[0]
                error_description = params.get("error_description", [""])[0]

                if error_param:
                    error = error_description or error_param
                    handler_self._send_html(400, _html_error(error))
                    return

                if not code_param:
                    error = "Missing authorization code"
                    handler_self._send_html(400, _html_error(error))
                    return

                if state_param != expected_state:
                    error = "Invalid state - potential CSRF attack"
                    handler_self._send_html(400, _html_error(error))
                    return

                code = code_param
                handler_self._send_html(200, HTML_SUCCESS)

            def _send_html(handler_self, status: int, body: str) -> None:
                handler_self.send_response(status)
                handler_self.send_header("Content-Type", "text/html; charset=utf-8")
                handler_self.end_headers()
                handler_self.wfile.write(body.encode("utf-8"))

            def log_message(handler_self, format: str, *args: Any) -> None:
                return

        class ReuseHTTPServer(http.server.HTTPServer):
            allow_reuse_address = True

        try:
            server = ReuseHTTPServer((host, port), CallbackHandler)
        except OSError as exc:
            raise RuntimeError(
                f"Failed to start callback server on {host}:{port}"
            ) from exc

        server.timeout = 1
        deadline = time.monotonic() + self.timeout_seconds
        try:
            while time.monotonic() < deadline and not code and not error:
                server.handle_request()
        finally:
            server.server_close()

        if error:
            raise RuntimeError(f"Authorization failed: {error}")
        if not code:
            raise TimeoutError("Authorization timed out")
        return code
