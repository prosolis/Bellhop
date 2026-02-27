"""Proxy layer for Radarr, Sonarr, and Lidarr APIs."""

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.auth import require_session
from app.audit import send_audit_message
from app.config import (
    LIDARR_API_KEY,
    LIDARR_QUALITY_PROFILE_ID,
    LIDARR_ROOT_FOLDER,
    LIDARR_URL,
    RADARR_API_KEY,
    RADARR_QUALITY_PROFILE_ID,
    RADARR_ROOT_FOLDER,
    RADARR_URL,
    SONARR_API_KEY,
    SONARR_QUALITY_PROFILE_ID,
    SONARR_ROOT_FOLDER,
    SONARR_URL,
)

router = APIRouter(tags=["arr"])

SERVICE_CONFIG = {
    "movie": {
        "url": RADARR_URL,
        "api_key": RADARR_API_KEY,
        "quality_profile_id": RADARR_QUALITY_PROFILE_ID,
        "root_folder": RADARR_ROOT_FOLDER,
        "lookup_path": "/api/v3/movie/lookup",
        "add_path": "/api/v3/movie",
        "label": "Movie",
    },
    "tv": {
        "url": SONARR_URL,
        "api_key": SONARR_API_KEY,
        "quality_profile_id": SONARR_QUALITY_PROFILE_ID,
        "root_folder": SONARR_ROOT_FOLDER,
        "lookup_path": "/api/v3/series/lookup",
        "add_path": "/api/v3/series",
        "label": "Show",
    },
    "music": {
        "url": LIDARR_URL,
        "api_key": LIDARR_API_KEY,
        "quality_profile_id": LIDARR_QUALITY_PROFILE_ID,
        "root_folder": LIDARR_ROOT_FOLDER,
        "lookup_path": "/api/v1/artist/lookup",
        "add_path": "/api/v1/artist",
        "label": "Artist",
    },
}

VALID_TYPES = set(SERVICE_CONFIG.keys())


def _headers(api_key: str) -> dict[str, str]:
    return {"X-Api-Key": api_key}


def _safe_result_movie(item: dict) -> dict:
    return {
        "title": item.get("title", ""),
        "year": item.get("year"),
        "tmdbId": item.get("tmdbId"),
        "overview": item.get("overview", ""),
        "remotePoster": item.get("remotePoster", ""),
        "hasFile": item.get("hasFile", False),
    }


def _safe_result_tv(item: dict) -> dict:
    return {
        "title": item.get("title", ""),
        "year": item.get("year"),
        "tvdbId": item.get("tvdbId"),
        "overview": item.get("overview", ""),
        "remotePoster": item.get("remotePoster", ""),
        "statistics": item.get("statistics", {}),
    }


def _safe_result_music(item: dict) -> dict:
    return {
        "artistName": item.get("artistName", ""),
        "foreignArtistId": item.get("foreignArtistId", ""),
        "overview": item.get("overview", ""),
        "remotePoster": (item.get("images") or [{}])[0].get("remoteUrl", "") if item.get("images") else "",
    }


SAFE_MAPPERS = {
    "movie": _safe_result_movie,
    "tv": _safe_result_tv,
    "music": _safe_result_music,
}


@router.get("/search/{media_type}")
async def search(media_type: str, term: str, request: Request) -> JSONResponse:
    session = await require_session(request)
    if not session:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    if media_type not in VALID_TYPES:
        return JSONResponse({"error": f"Invalid type. Must be one of: {', '.join(VALID_TYPES)}"}, status_code=400)

    if not term or not term.strip():
        return JSONResponse({"error": "Search term is required"}, status_code=400)

    cfg = SERVICE_CONFIG[media_type]
    if not cfg["url"] or not cfg["api_key"]:
        return JSONResponse({"error": f"{cfg['label']} service is not configured"}, status_code=503)

    lookup_url = f"{cfg['url'].rstrip('/')}{cfg['lookup_path']}"
    params = {"term": term.strip()}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                lookup_url,
                params=params,
                headers=_headers(cfg["api_key"]),
                timeout=15.0,
            )
        except httpx.RequestError:
            return JSONResponse({"error": f"Could not reach {cfg['label']} service"}, status_code=502)

    if resp.status_code != 200:
        return JSONResponse({"error": f"{cfg['label']} lookup failed"}, status_code=resp.status_code)

    results = resp.json()
    mapper = SAFE_MAPPERS[media_type]
    safe_results = [mapper(item) for item in results[:25]]

    return JSONResponse(safe_results)


@router.post("/request/{media_type}")
async def add_request(media_type: str, request: Request) -> JSONResponse:
    session = await require_session(request)
    if not session:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    if media_type not in VALID_TYPES:
        return JSONResponse({"error": f"Invalid type. Must be one of: {', '.join(VALID_TYPES)}"}, status_code=400)

    body = await request.json()
    cfg = SERVICE_CONFIG[media_type]

    if not cfg["url"] or not cfg["api_key"]:
        return JSONResponse({"error": f"{cfg['label']} service is not configured"}, status_code=503)

    add_url = f"{cfg['url'].rstrip('/')}{cfg['add_path']}"

    if media_type == "movie":
        payload = _build_movie_payload(body, cfg)
        title_display = f"\"{body.get('title', 'Unknown')}\" ({body.get('year', '?')})"
    elif media_type == "tv":
        payload = _build_tv_payload(body, cfg)
        title_display = f"\"{body.get('title', 'Unknown')}\" ({body.get('year', '?')})"
    else:
        payload = _build_music_payload(body, cfg)
        title_display = f"\"{body.get('artistName', 'Unknown')}\" ({body.get('foreignArtistId', '?')})"

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                add_url,
                json=payload,
                headers=_headers(cfg["api_key"]),
                timeout=15.0,
            )
        except httpx.RequestError:
            return JSONResponse({"error": f"Could not reach {cfg['label']} service"}, status_code=502)

    if resp.status_code not in (200, 201):
        error_detail = ""
        try:
            error_body = resp.json()
            if isinstance(error_body, list):
                error_detail = "; ".join(e.get("errorMessage", "") for e in error_body if e.get("errorMessage"))
            elif isinstance(error_body, dict):
                error_detail = error_body.get("message", "") or error_body.get("errorMessage", "")
        except Exception:
            pass
        msg = f"Failed to add to {cfg['label']}"
        if error_detail:
            msg += f": {error_detail}"
        return JSONResponse({"error": msg}, status_code=resp.status_code)

    # Fire-and-forget audit message
    user_id = session["matrix_user_id"]
    audit_msg = f"[REQUEST] {user_id} → [{cfg['label']}] {title_display}"
    send_audit_message(audit_msg)

    return JSONResponse({"ok": True, "message": f"{cfg['label']} added successfully"})


def _build_movie_payload(body: dict, cfg: dict) -> dict:
    return {
        "title": body.get("title", ""),
        "tmdbId": body.get("tmdbId"),
        "year": body.get("year"),
        "qualityProfileId": cfg["quality_profile_id"],
        "rootFolderPath": cfg["root_folder"],
        "monitored": True,
        "addOptions": {"searchForMovie": True},
    }


def _build_tv_payload(body: dict, cfg: dict) -> dict:
    return {
        "title": body.get("title", ""),
        "tvdbId": body.get("tvdbId"),
        "year": body.get("year"),
        "qualityProfileId": cfg["quality_profile_id"],
        "rootFolderPath": cfg["root_folder"],
        "monitored": True,
        "addOptions": {"searchForMissingEpisodes": True},
    }


def _build_music_payload(body: dict, cfg: dict) -> dict:
    return {
        "artistName": body.get("artistName", ""),
        "foreignArtistId": body.get("foreignArtistId", ""),
        "qualityProfileId": cfg["quality_profile_id"],
        "rootFolderPath": cfg["root_folder"],
        "monitored": True,
        "addOptions": {"searchForMissingAlbums": True},
    }
