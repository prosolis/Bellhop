# Bellhop

A Matrix-authenticated web portal for submitting media requests to Radarr, Sonarr, and Lidarr. Users sign in with their Matrix homeserver credentials, search for movies, TV shows, or music, and submit requests — all through a clean single-page interface. Every request is logged to a Matrix room for auditing.

## Architecture

```
Browser ──► FastAPI app ──► Matrix homeserver (authentication)
                        ──► Radarr / Sonarr / Lidarr (search + add)
                        ──► Matrix room (audit log)
                        ──► SQLite (session storage)
```

All *arr communication happens server-side. API keys and service URLs are never exposed to the browser.

## Requirements

- Python 3.12+
- A Matrix homeserver (Synapse, Dendrite, Conduit, etc.)
- At least one of: Radarr, Sonarr, or Lidarr accessible over HTTPS
- (Optional) A Matrix bot account for audit logging

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/prosolis/Bellhop.git
cd Bellhop
cp .env.example .env
```

Edit `.env` with your actual values (see [Environment Variables](#environment-variables) below).

### 2. Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your browser.

### 3. Run with Docker

```bash
docker build -t bellhop .
docker run -d \
  --name bellhop \
  --env-file .env \
  -p 8000:8000 \
  -v bellhop-data:/app \
  bellhop
```

The SQLite database file is created at the path specified by `DATABASE_PATH` (default: `bellhop.db` in the working directory). Mount a volume if you want persistence across container recreations.

## Environment Variables

Create a `.env` file in the project root (or pass variables via Docker `--env-file`). See `.env.example` for a template.

### Required

| Variable | Description |
|---|---|
| `MATRIX_HOMESERVER_URL` | Base URL of your Matrix homeserver (e.g. `https://matrix.example.com`) |
| `SESSION_SECRET_KEY` | Random secret used internally. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"` |

### *arr Services

Configure one or more. If a service's URL or API key is left empty, that media type will return a "not configured" error when used.

| Variable | Default | Description |
|---|---|---|
| `RADARR_URL` | _(empty)_ | Radarr instance URL (e.g. `https://radarr.example.com`) |
| `RADARR_API_KEY` | _(empty)_ | Radarr API key (Settings > General in Radarr) |
| `RADARR_QUALITY_PROFILE_ID` | `1` | Quality profile ID to assign to new movies |
| `RADARR_ROOT_FOLDER` | `/movies` | Root folder path for movie storage |
| `SONARR_URL` | _(empty)_ | Sonarr instance URL |
| `SONARR_API_KEY` | _(empty)_ | Sonarr API key |
| `SONARR_QUALITY_PROFILE_ID` | `1` | Quality profile ID for new series |
| `SONARR_ROOT_FOLDER` | `/tv` | Root folder path for TV storage |
| `LIDARR_URL` | _(empty)_ | Lidarr instance URL |
| `LIDARR_API_KEY` | _(empty)_ | Lidarr API key |
| `LIDARR_QUALITY_PROFILE_ID` | `1` | Quality profile ID for new artists |
| `LIDARR_ROOT_FOLDER` | `/music` | Root folder path for music storage |

**Finding quality profile IDs:** Open your *arr instance, go to Settings > Profiles. The ID is visible in the URL when you click a profile, or query the API directly:

```bash
curl -H "X-Api-Key: YOUR_KEY" https://radarr.example.com/api/v3/qualityprofile
```

### Audit Bot (optional)

| Variable | Default | Description |
|---|---|---|
| `MATRIX_AUDIT_ROOM_ID` | _(empty)_ | Room ID for audit messages (e.g. `!abc123:example.com`) |
| `MATRIX_BOT_USER_ID` | _(empty)_ | Bot's Matrix user ID (e.g. `@bellhop-bot:example.com`) |
| `MATRIX_BOT_ACCESS_TOKEN` | _(empty)_ | Pre-authenticated access token for the bot |

If any of these are left empty, audit logging is silently disabled. The room must be **unencrypted** and the bot must already be joined to it.

**Getting a bot access token:**

```bash
curl -X POST https://matrix.example.com/_matrix/client/v3/login \
  -H "Content-Type: application/json" \
  -d '{"type":"m.login.password","identifier":{"type":"m.id.user","user":"@bellhop-bot:example.com"},"password":"bot-password"}'
```

Copy the `access_token` from the response.

### Other

| Variable | Default | Description |
|---|---|---|
| `DATABASE_PATH` | `bellhop.db` | Path to the SQLite database file |

## API Reference

### Authentication

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/login` | Authenticate with Matrix credentials. Rate-limited to 5 requests/minute per IP. |
| `POST` | `/auth/logout` | Destroy the current session. |
| `GET` | `/auth/me` | Return the current user's Matrix ID, or 401 if not authenticated. |

**Login request body:**

```json
{
  "username": "@user:example.com",
  "password": "your-password"
}
```

The username can be a full Matrix ID (`@user:example.com`) or a localpart (`user`) — the homeserver resolves it.

**Login response (200):**

```json
{
  "user_id": "@user:example.com"
}
```

A `bellhop_session` cookie is set automatically.

### Search

| Method | Path | Description |
|---|---|---|
| `GET` | `/search/movie?term=...` | Search Radarr for movies |
| `GET` | `/search/tv?term=...` | Search Sonarr for TV shows |
| `GET` | `/search/music?term=...` | Search Lidarr for artists |

All search endpoints require an active session (cookie). Results are capped at 25 items. Response fields are sanitized — only safe metadata (title, year, poster URL, IDs) is returned.

### Request

| Method | Path | Description |
|---|---|---|
| `POST` | `/request/movie` | Add a movie to Radarr |
| `POST` | `/request/tv` | Add a series to Sonarr |
| `POST` | `/request/music` | Add an artist to Lidarr |

**Movie request body:**

```json
{
  "title": "Movie Title",
  "tmdbId": 12345,
  "year": 2024
}
```

**TV request body:**

```json
{
  "title": "Show Title",
  "tvdbId": 67890,
  "year": 2024
}
```

**Music request body:**

```json
{
  "artistName": "Artist Name",
  "foreignArtistId": "mbid-uuid-here"
}
```

All items are added as monitored with "search on add" enabled. Quality profile and root folder are set from the corresponding environment variables.

**Success response (200):**

```json
{
  "ok": true,
  "message": "Movie added successfully"
}
```

### Frontend

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serves the single-page Alpine.js frontend |

## Project Structure

```
Bellhop/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app, lifespan, rate limiter, route mounting
│   ├── config.py         # Environment variable loading
│   ├── database.py       # Async SQLite session CRUD
│   ├── auth.py           # /auth/* routes, session cookie management
│   ├── arr.py            # /search/* and /request/* routes, *arr API proxying
│   ├── audit.py          # Fire-and-forget Matrix room messaging
│   ├── static/           # Static assets (served at /static)
│   └── templates/
│       └── index.html    # Alpine.js single-page frontend
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## Security

- **Session cookies** are set with `httponly`, `samesite=strict`, and `secure` flags. The `secure` flag means cookies are only sent over HTTPS — use a reverse proxy with TLS in production.
- **Login rate limiting** — 5 attempts per minute per IP address via slowapi.
- **Token validation** — every protected route verifies the Matrix access token against the homeserver's `/_matrix/client/v3/account/whoami` endpoint. If the token has been revoked, the session is deleted immediately. If the homeserver is unreachable, the local session is trusted as a fallback.
- **No credential leakage** — *arr API keys, URLs, and internal IDs are never included in any response to the browser. Search results are mapped to a safe subset of fields before returning.
- **Sessions expire** after 7 days (cookie `max_age`).

### Production Recommendations

- Run behind a reverse proxy (nginx, Caddy, Traefik) with TLS termination so the `secure` cookie flag works.
- Set `SESSION_SECRET_KEY` to a strong random value.
- Restrict network access to your *arr instances — only the Bellhop container needs to reach them.
- Use a dedicated Matrix bot account for audit logging rather than a personal account.

## How It Works

1. **User signs in** — the frontend POSTs Matrix credentials to `/auth/login`. The backend authenticates against the Matrix homeserver's Client-Server API (`m.login.password`), stores the resulting access token in SQLite, and returns a session cookie.

2. **User searches** — the frontend sends a search query to `/search/{type}`. The backend proxies the request to the appropriate *arr instance, strips internal fields, and returns sanitized results with poster URLs.

3. **User requests** — clicking "Request" on a result POSTs it to `/request/{type}`. The backend sends the add command to the *arr API with preconfigured quality profile and root folder. On success, an audit message is fired asynchronously to the configured Matrix room.

4. **Audit trail** — every successful request posts a message like `[REQUEST] @user:example.com → [Movie] "Title" (2024)` to the Matrix audit room. This is fire-and-forget — failures are logged but never block the user's request.

## Lidarr Notes

Lidarr uses MusicBrainz IDs (`foreignArtistId`) rather than TMDB/TVDB IDs. The lookup response includes this field and it is passed through directly to the add call. No independent MBID resolution is needed.

## License

See repository for license details.
