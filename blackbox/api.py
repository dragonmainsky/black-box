from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
    """Security enforcement:
    1. Validates Host header against allowed local hosts (DNS rebinding defense).
    2. Validates Origin and Referer headers against allowed local origins.
    3. Enforces token authentication via Bearer, X-API-Token, or query parameter.
    4. CORS is intentionally not enabled.
    """

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

        # 1. Host header validation
        raw_host = headers.get(b"host", b"").decode("ascii", errors="replace")
        host = raw_host.split(":")[0].lower() if raw_host else ""
        if not host or host not in self.allowed_hosts:
            response = JSONResponse(
                {"detail": "Forbidden: Invalid Host header"}, status_code=403
            )
            await response(scope, receive, send)
            return

        # 2. Origin header validation
        raw_origin = headers.get(b"origin", b"").decode("utf-8", errors="replace")
        if raw_origin and raw_origin != "null":
            parsed = urlparse(raw_origin)
            if parsed.scheme not in ("pywebview", "app", "file", ""):
                orig_host = parsed.hostname.lower() if parsed.hostname else ""
                if not orig_host or orig_host not in self.allowed_hosts:
                    response = JSONResponse(
                        {"detail": "Forbidden: Untrusted Origin"}, status_code=403
                    )
                    await response(scope, receive, send)
                    return

        # 3. Referer header validation
        raw_referer = headers.get(b"referer", b"").decode("utf-8", errors="replace")
        if raw_referer:
            parsed = urlparse(raw_referer)
            if parsed.scheme not in ("pywebview", "app", "file", ""):
                ref_host = parsed.hostname.lower() if parsed.hostname else ""
                if not ref_host or ref_host not in self.allowed_hosts:
                    response = JSONResponse(
                        {"detail": "Forbidden: Untrusted Referer"}, status_code=403
                    )
                    await response(scope, receive, send)
                    return

        # 4. Exemption for liveness probe
        path = scope.get("path", "")
        if path == "/health":
            await self.app(scope, receive, send)
            return

        # 5. Token authentication
        auth = headers.get(b"authorization", b"").decode("utf-8", errors="replace")
        api_token = headers.get(b"x-api-token", b"").decode("utf-8", errors="replace")

        query_string = scope.get("query_string", b"").decode("utf-8", errors="replace")
        query_token = ""
        if "token=" in query_string:
            for part in query_string.split("&"):
                if part.startswith("token="):
                    query_token = part[6:]
                    break

        provided = ""
        if auth.startswith("Bearer "):
            provided = auth[7:].strip()
        elif api_token:
            provided = api_token.strip()
        elif query_token:
            provided = query_token.strip()

        if not provided or not hmac.compare_digest(provided, self.token):
            response = JSONResponse(
                {"detail": "Unauthorized: Invalid or missing token"},
                status_code=401,
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


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
