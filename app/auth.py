import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.config import MATRIX_HOMESERVER_URL
from app.database import create_session, delete_session, get_session

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_COOKIE = "bellhop_session"
MAX_SESSION_AGE = 60 * 60 * 24 * 7  # 7 days


@router.post("/login")
async def login(request: Request) -> Response:
    body = await request.json()
    username: str = body.get("username", "").strip()
    password: str = body.get("password", "")

    if not username or not password:
        return JSONResponse({"error": "Username and password are required"}, status_code=400)

    # Build the Matrix user identifier
    if username.startswith("@"):
        user_identifier = username
    else:
        user_identifier = username  # let the homeserver resolve it

    login_url = f"{MATRIX_HOMESERVER_URL.rstrip('/')}/_matrix/client/v3/login"
    payload = {
        "type": "m.login.password",
        "identifier": {"type": "m.id.user", "user": user_identifier},
        "password": password,
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(login_url, json=payload, timeout=15.0)
        except httpx.RequestError:
            return JSONResponse({"error": "Could not reach Matrix homeserver"}, status_code=502)

    if resp.status_code != 200:
        error_msg = resp.json().get("error", "Authentication failed")
        return JSONResponse({"error": error_msg}, status_code=401)

    data = resp.json()
    matrix_user_id: str = data["user_id"]
    matrix_access_token: str = data["access_token"]

    session_id = await create_session(matrix_user_id, matrix_access_token)

    response = JSONResponse({"user_id": matrix_user_id})
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        httponly=True,
        samesite="strict",
        secure=True,
        max_age=MAX_SESSION_AGE,
    )
    return response


@router.post("/logout")
async def logout(request: Request) -> Response:
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        await delete_session(session_id)
    response = JSONResponse({"ok": True})
    response.delete_cookie(key=SESSION_COOKIE)
    return response


@router.get("/me")
async def me(request: Request) -> Response:
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    session = await get_session(session_id)
    if not session:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    # Verify token is still valid with the homeserver
    whoami_url = f"{MATRIX_HOMESERVER_URL.rstrip('/')}/_matrix/client/v3/account/whoami"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                whoami_url,
                headers={"Authorization": f"Bearer {session['matrix_access_token']}"},
                timeout=10.0,
            )
        except httpx.RequestError:
            # If homeserver is unreachable, trust the local session
            return JSONResponse({"user_id": session["matrix_user_id"]})

    if resp.status_code != 200:
        await delete_session(session_id)
        response = JSONResponse({"error": "Session expired"}, status_code=401)
        response.delete_cookie(key=SESSION_COOKIE)
        return response

    return JSONResponse({"user_id": session["matrix_user_id"]})


async def require_session(request: Request) -> dict | None:
    """Utility: extract and validate session from a request. Returns session dict or None."""
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        return None
    session = await get_session(session_id)
    if not session:
        return None

    # Verify token is still valid
    whoami_url = f"{MATRIX_HOMESERVER_URL.rstrip('/')}/_matrix/client/v3/account/whoami"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                whoami_url,
                headers={"Authorization": f"Bearer {session['matrix_access_token']}"},
                timeout=10.0,
            )
        except httpx.RequestError:
            return session  # trust local session if homeserver unreachable

    if resp.status_code != 200:
        await delete_session(session_id)
        return None

    return session
