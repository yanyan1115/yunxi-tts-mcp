from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import secrets
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.fastmcp import FastMCP
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse, Response

try:
    from mcp.server.transport_security import TransportSecuritySettings
except Exception:  # pragma: no cover - older MCP SDKs may not expose this.
    TransportSecuritySettings = None  # type: ignore[assignment]


DEFAULT_VOICE = "zh-CN-YunxiNeural"
DEFAULT_RATE = "-5%"
DEFAULT_PITCH = "-8Hz"
DEFAULT_VOLUME = "+0%"
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = Path(os.getenv("TTS_OUTPUT_DIR", str(BASE_DIR / "output"))).expanduser()
DEFAULT_OAUTH_STORE = Path(os.getenv("MCP_OAUTH_STORE", str(BASE_DIR / "oauth_store.json"))).expanduser()
OAUTH_SCOPE = "text_to_speech"
OAUTH_ACCESS_TOKEN_TTL_SECONDS = 3600
OAUTH_REFRESH_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 90
OAUTH_AUTH_CODE_TTL_SECONDS = 300
EDGE_TTS_COMMAND = (
    Path(sys.executable).with_name("edge-tts.exe")
    if sys.platform == "win32"
    else Path(sys.executable).with_name("edge-tts")
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def _env_list(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [part.strip() for part in raw.split(",") if part.strip()]


def _output_root() -> Path:
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_OUTPUT_DIR.resolve()


def _public_base_url() -> str:
    return os.getenv("TTS_PUBLIC_BASE_URL", "").strip().rstrip("/")


def _oauth_enabled() -> bool:
    return os.getenv("MCP_OAUTH_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _oauth_store_path() -> Path:
    return DEFAULT_OAUTH_STORE


def _build_transport_security() -> Any:
    allowed_hosts = _env_list("MCP_ALLOWED_HOSTS")
    allowed_origins = _env_list("MCP_ALLOWED_ORIGINS")
    if TransportSecuritySettings is None or (not allowed_hosts and not allowed_origins):
        return None
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


class LocalOAuthProvider:
    def __init__(self, store_path: Path) -> None:
        self.store_path = store_path
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.auth_codes: dict[str, AuthorizationCode] = {}
        self.refresh_tokens: dict[str, RefreshToken] = {}
        self.access_tokens: dict[str, AccessToken] = {}
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.store_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except Exception:
            logging.warning("Could not read OAuth store; starting with an empty store")
            return
        for client_id, payload in data.get("clients", {}).items():
            self.clients[client_id] = OAuthClientInformationFull.model_validate(payload)
        for code, payload in data.get("auth_codes", {}).items():
            self.auth_codes[code] = AuthorizationCode.model_validate(payload)
        for token, payload in data.get("refresh_tokens", {}).items():
            self.refresh_tokens[token] = RefreshToken.model_validate(payload)
        for token, payload in data.get("access_tokens", {}).items():
            self.access_tokens[token] = AccessToken.model_validate(payload)
        self._prune_expired(save=False)

    def _save(self) -> None:
        self._prune_expired(save=False)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "clients": {key: value.model_dump(mode="json") for key, value in self.clients.items()},
            "auth_codes": {key: value.model_dump(mode="json") for key, value in self.auth_codes.items()},
            "refresh_tokens": {key: value.model_dump(mode="json") for key, value in self.refresh_tokens.items()},
            "access_tokens": {key: value.model_dump(mode="json") for key, value in self.access_tokens.items()},
        }
        tmp_path = self.store_path.with_suffix(self.store_path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self.store_path)
        try:
            os.chmod(self.store_path, 0o600)
        except OSError:
            pass

    def _prune_expired(self, *, save: bool = True) -> None:
        now = int(time.time())
        changed = False
        for mapping in (self.auth_codes, self.refresh_tokens, self.access_tokens):
            for key, value in list(mapping.items()):
                expires_at = getattr(value, "expires_at", None)
                if expires_at is not None and expires_at < now:
                    mapping.pop(key, None)
                    changed = True
        if changed and save:
            self._save()

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self.clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        if not client_info.client_id:
            raise ValueError("client_id is required")
        self.clients[client_info.client_id] = client_info
        self._save()

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        query = {
            "client_id": client.client_id or "",
            "response_type": "code",
            "code_challenge": params.code_challenge,
            "redirect_uri": str(params.redirect_uri),
        }
        if params.state is not None:
            query["state"] = params.state
        if params.scopes:
            query["scope"] = " ".join(params.scopes)
        if params.resource is not None:
            query["resource"] = params.resource
        return "/oauth/authorize?" + urlencode(query)

    def authorize_url(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        if not client.client_id:
            raise AuthorizeError("invalid_request", "client_id is required")
        scopes = params.scopes or [OAUTH_SCOPE]
        code = secrets.token_urlsafe(32)
        self.auth_codes[code] = AuthorizationCode(
            code=code,
            scopes=scopes,
            expires_at=int(time.time()) + OAUTH_AUTH_CODE_TTL_SECONDS,
            client_id=client.client_id,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
        )
        self._save()
        return construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state)

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        code = self.auth_codes.get(authorization_code)
        if code is None or code.client_id != client.client_id or code.expires_at < time.time():
            return None
        return code

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        self.auth_codes.pop(authorization_code.code, None)
        if authorization_code.client_id != client.client_id:
            raise TokenError("invalid_grant", "authorization code is not valid for this client")
        return self._issue_tokens(client, authorization_code.scopes, authorization_code.resource)

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> RefreshToken | None:
        token = self.refresh_tokens.get(refresh_token)
        if token is None or token.client_id != client.client_id:
            return None
        if token.expires_at is not None and token.expires_at < time.time():
            return None
        return token

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        self.refresh_tokens.pop(refresh_token.token, None)
        if refresh_token.client_id != client.client_id:
            raise TokenError("invalid_grant", "refresh token is not valid for this client")
        requested_scopes = scopes or refresh_token.scopes
        if not set(requested_scopes).issubset(set(refresh_token.scopes)):
            raise TokenError("invalid_scope", "requested scope was not granted")
        return self._issue_tokens(client, requested_scopes)

    async def load_access_token(self, token: str) -> AccessToken | None:
        access_token = self.access_tokens.get(token)
        if access_token is None:
            return None
        if access_token.expires_at is not None and access_token.expires_at < time.time():
            self.access_tokens.pop(token, None)
            self._save()
            return None
        return access_token

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        self.access_tokens.pop(token.token, None)
        self.refresh_tokens.pop(token.token, None)
        if isinstance(token, RefreshToken):
            for access_token, value in list(self.access_tokens.items()):
                if value.client_id == token.client_id:
                    self.access_tokens.pop(access_token, None)
        self._save()

    def _issue_tokens(self, client: OAuthClientInformationFull, scopes: list[str], resource: str | None = None) -> OAuthToken:
        if not client.client_id:
            raise TokenError("invalid_client", "client_id is required")
        access_token_value = secrets.token_urlsafe(32)
        refresh_token_value = secrets.token_urlsafe(32)
        now = int(time.time())
        self.access_tokens[access_token_value] = AccessToken(
            token=access_token_value,
            client_id=client.client_id,
            scopes=scopes,
            expires_at=now + OAUTH_ACCESS_TOKEN_TTL_SECONDS,
            resource=resource,
        )
        self.refresh_tokens[refresh_token_value] = RefreshToken(
            token=refresh_token_value,
            client_id=client.client_id,
            scopes=scopes,
            expires_at=now + OAUTH_REFRESH_TOKEN_TTL_SECONDS,
        )
        self._save()
        return OAuthToken(
            access_token=access_token_value,
            expires_in=OAUTH_ACCESS_TOKEN_TTL_SECONDS,
            scope=" ".join(scopes),
            refresh_token=refresh_token_value,
        )


def _build_oauth(provider: LocalOAuthProvider) -> tuple[AuthSettings, LocalOAuthProvider]:
    issuer_url = os.getenv("MCP_OAUTH_ISSUER_URL", "").strip()
    resource_url = os.getenv("MCP_OAUTH_RESOURCE_URL", "").strip() or issuer_url.rstrip("/") + "/mcp"
    if not issuer_url:
        raise RuntimeError("MCP_OAUTH_ISSUER_URL is required when MCP_OAUTH_ENABLED is set")
    return (
        AuthSettings(
            issuer_url=issuer_url,
            resource_server_url=resource_url,
            required_scopes=[OAUTH_SCOPE],
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                valid_scopes=[OAUTH_SCOPE],
                default_scopes=[OAUTH_SCOPE],
            ),
            revocation_options=RevocationOptions(enabled=True),
        ),
        provider,
    )


def _html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _auth_params_from_query(query: dict[str, str], redirect_uri_provided: bool) -> AuthorizationParams:
    scopes = query.get("scope", OAUTH_SCOPE).split()
    return AuthorizationParams(
        state=query.get("state"),
        scopes=scopes or [OAUTH_SCOPE],
        code_challenge=query["code_challenge"],
        redirect_uri=query["redirect_uri"],
        redirect_uri_provided_explicitly=redirect_uri_provided,
        resource=query.get("resource"),
    )


def _register_oauth_routes(server: FastMCP, provider: LocalOAuthProvider) -> None:
    @server.custom_route("/oauth/authorize", methods=["GET", "POST"])
    async def oauth_authorize(request: Request) -> Response:
        connect_secret = os.getenv("MCP_OAUTH_CONNECT_SECRET", "")
        if not connect_secret:
            return PlainTextResponse("MCP_OAUTH_CONNECT_SECRET is not configured", status_code=503)

        if request.method == "POST":
            form = await request.form()
            query = {key: str(value) for key, value in form.items() if key != "connect_secret"}
            submitted_secret = str(form.get("connect_secret", ""))
            if not secrets.compare_digest(submitted_secret, connect_secret):
                return _oauth_form(query, "Invalid connection secret.", status_code=403)
            return await _complete_oauth_authorization(provider, query)

        query = {key: value for key, value in request.query_params.items()}
        return _oauth_form(query)


def _oauth_form(query: dict[str, str], error: str | None = None, *, status_code: int = 200) -> HTMLResponse:
    hidden = "\n".join(
        f'<input type="hidden" name="{_html_escape(key)}" value="{_html_escape(value)}">'
        for key, value in query.items()
    )
    error_html = f'<p class="error">{_html_escape(error)}</p>' if error else ""
    client_name = _html_escape(query.get("client_id", "Claude connector"))
    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Authorize Yunxi TTS MCP</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 36rem; line-height: 1.5; }}
    label {{ display: block; font-weight: 600; margin: 1rem 0 0.35rem; }}
    input[type=password] {{ box-sizing: border-box; width: 100%; padding: 0.65rem; font: inherit; }}
    button {{ margin-top: 1rem; padding: 0.65rem 1rem; font: inherit; cursor: pointer; }}
    .error {{ color: #b00020; }}
    .muted {{ color: #555; }}
  </style>
</head>
<body>
  <h1>Authorize Yunxi TTS MCP</h1>
  <p class="muted">Client: {client_name}</p>
  {error_html}
  <form method="post">
    {hidden}
    <label for="connect_secret">Connection secret</label>
    <input id="connect_secret" name="connect_secret" type="password" autocomplete="current-password" autofocus>
    <button type="submit">Authorize</button>
  </form>
</body>
</html>"""
    return HTMLResponse(body, status_code=status_code)


async def _complete_oauth_authorization(provider: LocalOAuthProvider, query: dict[str, str]) -> Response:
    required = {"client_id", "response_type", "code_challenge", "redirect_uri"}
    missing = sorted(required - set(query))
    if missing:
        return PlainTextResponse(f"Missing OAuth parameter: {', '.join(missing)}", status_code=400)
    if query["response_type"] != "code":
        return PlainTextResponse("Unsupported response_type", status_code=400)
    client = await provider.get_client(query["client_id"])
    if client is None:
        return PlainTextResponse("Unknown OAuth client", status_code=400)
    try:
        redirect_uri = client.validate_redirect_uri(AnyUrl(query["redirect_uri"]))
        params = _auth_params_from_query({**query, "redirect_uri": str(redirect_uri)}, True)
        url = provider.authorize_url(client, params)
    except Exception as exc:
        return PlainTextResponse(str(exc), status_code=400)
    return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})


def _resolve_output_dir(output_dir: str | None) -> Path:
    root = _output_root()
    if output_dir:
        path = Path(output_dir).expanduser()
        if not path.is_absolute():
            path = root / path
    else:
        path = root

    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"output_dir must be inside {root}") from exc
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_stem(text: str, filename: str | None) -> str:
    if filename:
        stem = Path(filename).stem
        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
        stem = f"tts-{timestamp}-{secrets.token_urlsafe(8)}-{digest}"

    if not stem:
        stem = "tts"
    return stem[:96]


def _safe_mp3_filename(text: str, filename: str | None) -> str:
    return f"{_safe_stem(text, filename)}.mp3"


def _media_url(media_path: Path, route: str) -> str | None:
    base_url = _public_base_url()
    if not base_url:
        return None
    root = _output_root()
    try:
        relative = media_path.resolve().relative_to(root)
    except ValueError:
        return None
    return f"{base_url}/{route}/{'/'.join(relative.parts)}"


def _audio_url(audio_path: Path) -> str | None:
    return _media_url(audio_path, "audio")


def _voice_url(voice_path: Path) -> str | None:
    return _media_url(voice_path, "voice")


def _bot_token() -> str:
    token_env = os.getenv("TTS_TELEGRAM_BOT_TOKEN_ENV", "").strip()
    if token_env:
        return os.getenv(token_env, "").strip()

    for name in ("TTS_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


async def synthesize_speech(
    text: str,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    volume: str = DEFAULT_VOLUME,
    pitch: str = DEFAULT_PITCH,
    output_dir: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    """Generate an MP3 file and return its absolute path plus metadata."""
    cleaned_text = text.strip()
    if not cleaned_text:
        raise ValueError("text must not be empty")

    target_dir = _resolve_output_dir(output_dir)
    audio_path = target_dir / _safe_mp3_filename(cleaned_text, filename)

    text_file = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        suffix=".txt",
        delete=False,
    )
    process: asyncio.subprocess.Process | None = None
    try:
        with text_file:
            text_file.write(cleaned_text)

        process = await asyncio.create_subprocess_exec(
            str(EDGE_TTS_COMMAND),
            "--voice",
            voice,
            "--file",
            text_file.name,
            f"--rate={rate}",
            f"--volume={volume}",
            f"--pitch={pitch}",
            "--write-media",
            str(audio_path),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
    finally:
        Path(text_file.name).unlink(missing_ok=True)

    if process is None or process.returncode != 0 or not audio_path.exists() or audio_path.stat().st_size == 0:
        audio_path.unlink(missing_ok=True)
        error_text = stderr.decode("utf-8", errors="replace").strip()
        output_text = stdout.decode("utf-8", errors="replace").strip()
        details = error_text or output_text or "edge-tts did not produce audio"
        raise RuntimeError(details)

    result: dict[str, Any] = {
        "audio_path": str(audio_path),
        "voice": voice,
        "rate": rate,
        "volume": volume,
        "pitch": pitch,
        "characters": len(cleaned_text),
        "format": "mp3",
    }
    url = _audio_url(audio_path)
    if url:
        result["audio_url"] = url
    return result


async def convert_mp3_to_ogg(mp3_path: str | Path, ogg_path: str | Path | None = None) -> dict[str, Any]:
    """Convert an MP3 into Telegram voice-note friendly OGG/Opus."""
    source = Path(mp3_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"MP3 file not found: {source}")

    root = _output_root()
    if ogg_path is None:
        target = source.with_suffix(".ogg")
    else:
        target = Path(ogg_path).expanduser()
        if not target.is_absolute():
            target = root / target
        target = target.resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"ogg_path must be inside {root}") from exc

    target.parent.mkdir(parents=True, exist_ok=True)
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-c:a",
        "libopus",
        str(target),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0 or not target.exists() or target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        error_text = stderr.decode("utf-8", errors="replace").strip()
        output_text = stdout.decode("utf-8", errors="replace").strip()
        details = error_text or output_text or "ffmpeg did not produce OGG/Opus audio"
        raise RuntimeError(details)

    result: dict[str, Any] = {
        "voice_path": str(target),
        "voice_format": "ogg",
        "codec": "opus",
    }
    url = _voice_url(target)
    if url:
        result["voice_url"] = url
    return result


async def send_telegram_voice(chat_id: str, voice_path: str | Path, caption: str | None = None) -> dict[str, Any]:
    """Send an OGG/Opus file as a Telegram voice message using sendVoice."""
    token = _bot_token()
    if not token:
        raise RuntimeError("Telegram bot token is not configured")

    path = Path(voice_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Voice file not found: {path}")

    data = {"chat_id": str(chat_id)}
    if caption:
        data["caption"] = caption

    url = f"https://api.telegram.org/bot{token}/sendVoice"
    async with httpx.AsyncClient(timeout=60) as client:
        with path.open("rb") as voice_file:
            response = await client.post(url, data=data, files={"voice": (path.name, voice_file, "audio/ogg")})

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"Telegram sendVoice returned non-JSON HTTP {response.status_code}") from exc

    if response.status_code >= 400 or not payload.get("ok"):
        description = str(payload.get("description", f"HTTP {response.status_code}"))
        raise RuntimeError(f"Telegram sendVoice failed: {description}")

    message = payload.get("result") or {}
    voice = message.get("voice") or {}
    return {
        "telegram_ok": True,
        "message_id": message.get("message_id"),
        "chat_id": (message.get("chat") or {}).get("id"),
        "voice_file_id": voice.get("file_id"),
        "voice_duration": voice.get("duration"),
        "voice_mime_type": voice.get("mime_type"),
    }


async def synthesize_voice_note(
    text: str,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    volume: str = DEFAULT_VOLUME,
    pitch: str = DEFAULT_PITCH,
    output_dir: str | None = None,
    filename: str | None = None,
    chat_id: str | None = None,
    caption: str | None = None,
) -> dict[str, Any]:
    """Generate MP3, convert it to OGG/Opus, and optionally send a Telegram voice note."""
    speech = await synthesize_speech(
        text=text,
        voice=voice,
        rate=rate,
        volume=volume,
        pitch=pitch,
        output_dir=output_dir,
        filename=filename,
    )
    voice_note = await convert_mp3_to_ogg(speech["audio_path"])
    result = {
        **speech,
        **voice_note,
        "audio_format": speech["format"],
        "telegram_voice_sent": False,
    }
    if chat_id:
        sent = await send_telegram_voice(chat_id=chat_id, voice_path=voice_note["voice_path"], caption=caption)
        result.update(sent)
        result["telegram_voice_sent"] = True
    return result


def _build_mcp() -> FastMCP:
    kwargs: dict[str, Any] = {
        "host": os.getenv("MCP_HOST", "127.0.0.1"),
        "port": int(os.getenv("MCP_PORT", "8891")),
        "instructions": (
            "Generate speech audio files from text with Microsoft Edge TTS. "
            "The default voice is zh-CN-YunxiNeural."
        ),
    }
    transport_security = _build_transport_security()
    if transport_security is not None:
        kwargs["transport_security"] = transport_security
    oauth_provider: LocalOAuthProvider | None = None
    if _oauth_enabled():
        oauth_provider = LocalOAuthProvider(_oauth_store_path())
        auth, provider = _build_oauth(oauth_provider)
        kwargs["auth"] = auth
        kwargs["auth_server_provider"] = provider

    server = FastMCP("edge-tts-yunxi", **kwargs)
    if oauth_provider is not None:
        _register_oauth_routes(server, oauth_provider)

    async def _media_file(request: Request, suffix: str, media_type: str) -> Response:
        requested = str(request.path_params["file_path"])
        root = _output_root()
        path = (root / requested).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            return PlainTextResponse("Not found", status_code=404)
        if not path.is_file() or path.suffix.lower() != suffix:
            return PlainTextResponse("Not found", status_code=404)
        return FileResponse(path, media_type=media_type, filename=path.name)

    @server.custom_route("/audio/{file_path:path}", methods=["GET"])
    async def audio_file(request: Request) -> Response:
        return await _media_file(request, ".mp3", "audio/mpeg")

    @server.custom_route("/voice/{file_path:path}", methods=["GET"])
    async def voice_file(request: Request) -> Response:
        return await _media_file(request, ".ogg", "audio/ogg")

    return server


mcp = _build_mcp()


@mcp.tool()
async def text_to_speech(
    text: str,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    volume: str = DEFAULT_VOLUME,
    pitch: str = DEFAULT_PITCH,
    output_dir: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    """Turn input text into an MP3 audio file with edge-tts."""
    return await synthesize_speech(
        text=text,
        voice=voice,
        rate=rate,
        volume=volume,
        pitch=pitch,
        output_dir=output_dir,
        filename=filename,
    )


@mcp.tool()
async def text_to_voice_note(
    text: str,
    chat_id: str | None = None,
    caption: str | None = None,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    volume: str = DEFAULT_VOLUME,
    pitch: str = DEFAULT_PITCH,
    output_dir: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    """Generate an OGG/Opus Telegram voice note, and optionally send it with sendVoice."""
    return await synthesize_voice_note(
        text=text,
        chat_id=chat_id,
        caption=caption,
        voice=voice,
        rate=rate,
        volume=volume,
        pitch=pitch,
        output_dir=output_dir,
        filename=filename,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Yunxi TTS MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="MCP transport to run",
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
