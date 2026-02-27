import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


# Matrix
MATRIX_HOMESERVER_URL: str = _require("MATRIX_HOMESERVER_URL")
MATRIX_AUDIT_ROOM_ID: str = os.getenv("MATRIX_AUDIT_ROOM_ID", "")
MATRIX_BOT_USER_ID: str = os.getenv("MATRIX_BOT_USER_ID", "")
MATRIX_BOT_ACCESS_TOKEN: str = os.getenv("MATRIX_BOT_ACCESS_TOKEN", "")

# Radarr
RADARR_URL: str = os.getenv("RADARR_URL", "")
RADARR_API_KEY: str = os.getenv("RADARR_API_KEY", "")
RADARR_QUALITY_PROFILE_ID: int = int(os.getenv("RADARR_QUALITY_PROFILE_ID", "1"))
RADARR_ROOT_FOLDER: str = os.getenv("RADARR_ROOT_FOLDER", "/movies")

# Sonarr
SONARR_URL: str = os.getenv("SONARR_URL", "")
SONARR_API_KEY: str = os.getenv("SONARR_API_KEY", "")
SONARR_QUALITY_PROFILE_ID: int = int(os.getenv("SONARR_QUALITY_PROFILE_ID", "1"))
SONARR_ROOT_FOLDER: str = os.getenv("SONARR_ROOT_FOLDER", "/tv")

# Lidarr
LIDARR_URL: str = os.getenv("LIDARR_URL", "")
LIDARR_API_KEY: str = os.getenv("LIDARR_API_KEY", "")
LIDARR_QUALITY_PROFILE_ID: int = int(os.getenv("LIDARR_QUALITY_PROFILE_ID", "1"))
LIDARR_ROOT_FOLDER: str = os.getenv("LIDARR_ROOT_FOLDER", "/music")

# App
SESSION_SECRET_KEY: str = _require("SESSION_SECRET_KEY")
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "bellhop.db")
