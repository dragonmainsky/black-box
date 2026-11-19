from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine

from blackbox.events.narrator import narrate_event
from blackbox.status import get_system_status
from blackbox.store.events import get_open_events, recent_events
from blackbox.store.probes import recent_probes

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "testserver"}


def token_path(data_dir: Path) -> Path:
    return data_dir / "api.token"


def save_token(token_file: Path, token: str) -> None:
    token_file.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    mode = 0o600
    fd = os.open(str(token_file), flags, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(token.strip())
    try:
        os.chmod(token_file, 0o600)
    except Exception:
        pass


def load_or_create_token(data_dir: Path) -> str:
    path = token_path(data_dir)
    if path.is_file():
        try:
            token = path.read_text(encoding="utf-8").strip()
            if token:
                return token
        except Exception:
            pass
    token = secrets.token_urlsafe(32)
    save_token(path, token)
    return token


class SecurityMiddleware:
    """ตรวจ Host/Origin/Referer และ token ก่อนปล่อย request เข้า API

    ใช้กับ local API เท่านั้น: bind 127.0.0.1, ไม่เปิด CORS
    """

    _LOCAL_SCHEMES = {"pywebview", "app", "file", ""}

    def __init__(
        self,
        app: Any,
        token: str,
        allowed_hosts: set[str] | None = None,
    ) -> None:
        self.app = app
        self.token = token
        self.allowed_hosts = {h.lower() for h in (allowed_hosts or ALLOWED_HOSTS)}

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        if not self._host_ok(headers):
            await self._reject(
                scope, receive, send, 403, "Forbidden: Invalid Host header"
            )
            return
        if not self._url_ok(self._header(headers, b"origin"), allow_null=True):
            await self._reject(
                scope, receive, send, 403, "Forbidden: Untrusted Origin"
            )
            return
        if not self._url_ok(self._header(headers, b"referer")):
            await self._reject(
                scope, receive, send, 403, "Forbidden: Untrusted Referer"
            )
            return
        if scope.get("path") == "/health":
            await self.app(scope, receive, send)
            return
        if not self._token_ok(headers, scope):
            await self._reject(
                scope, receive, send, 401, "Unauthorized: Invalid or missing token"
            )
            return
        await self.app(scope, receive, send)

    @staticmethod
    def _header(headers: dict[bytes, bytes], name: bytes) -> str:
        return headers.get(name, b"").decode("utf-8", errors="replace")

    def _host_ok(self, headers: dict[bytes, bytes]) -> bool:
        raw = self._header(headers, b"host")
        host = raw.split(":")[0].lower() if raw else ""
        return bool(host and host in self.allowed_hosts)

    def _url_ok(self, raw: str, *, allow_null: bool = False) -> bool:
        if not raw or (allow_null and raw == "null"):
            return True
        parsed = urlparse(raw)
        if parsed.scheme in self._LOCAL_SCHEMES:
            return True
        host = parsed.hostname.lower() if parsed.hostname else ""
        return bool(host and host in self.allowed_hosts)

    def _token_ok(self, headers: dict[bytes, bytes], scope: dict[str, Any]) -> bool:
        auth = self._header(headers, b"authorization")
        api_token = self._header(headers, b"x-api-token")
        if auth.startswith("Bearer "):
            provided = auth[7:].strip()
        elif api_token:
            provided = api_token.strip()
        else:
            query = parse_qs(
                scope.get("query_string", b"").decode("utf-8", errors="replace")
            )
            provided = (query.get("token") or [""])[0].strip()
        return bool(provided) and hmac.compare_digest(provided, self.token)

    @staticmethod
    async def _reject(
        scope: dict[str, Any],
        receive: Any,
        send: Any,
        status_code: int,
        detail: str,
    ) -> None:
        response = JSONResponse({"detail": detail}, status_code=status_code)
        await response(scope, receive, send)


api_router = APIRouter(prefix="/api")


@api_router.get("/status")
def get_status(request: Request, limit: int = 5) -> dict[str, Any]:
    engine: Engine = request.app.state.engine
    status = get_system_status(engine, recent_limit=limit)
    return status.to_dict()


@api_router.get("/events")
def get_events(
    request: Request,
    limit: int = 50,
    type: str | None = None,
    open_only: bool = False,
) -> list[dict[str, Any]]:
    engine: Engine = request.app.state.engine
    if open_only:
        evts = get_open_events(engine)
        if type:
            evts = [e for e in evts if e.get("type") == type]
        evts = evts[:limit]
    else:
        evts = recent_events(engine, limit=limit, event_type=type)

    for e in evts:
        if "narrative" not in e:
            e["narrative"] = narrate_event(e)
    return evts


@api_router.get("/probes")
def get_probes(
    request: Request,
    limit: int = 50,
    probe: str | None = None,
) -> list[dict[str, Any]]:
    engine: Engine = request.app.state.engine
    return recent_probes(engine, limit=limit, probe=probe)


def create_app(
    engine: Engine,
    token: str | None = None,
    data_dir: Path | None = None,
    allowed_hosts: set[str] | None = None,
) -> FastAPI:
    if not token:
        if data_dir:
            token = load_or_create_token(data_dir)
        else:
            token = secrets.token_urlsafe(32)

    app = FastAPI(title="Home Network Black Box API", version="0.1.0")
    app.state.engine = engine
    app.state.token = token

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    app.include_router(api_router)
    app.add_middleware(
        SecurityMiddleware,
        token=token,
        allowed_hosts=allowed_hosts,
    )
    return app


def run_api(
    engine: Engine,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    token: str | None = None,
    data_dir: Path | None = None,
) -> None:
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("Security constraint: API must bind to 127.0.0.1 only")

    import uvicorn

    app = create_app(engine, token=token, data_dir=data_dir)
    print(f"API server running on http://{host}:{port}")
    print(f"Token: {app.state.token}")
    uvicorn.run(app, host=host, port=port, log_level="info")
