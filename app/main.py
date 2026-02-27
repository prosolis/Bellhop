from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.auth import router as auth_router
from app.arr import router as arr_router
from app.database import close_db, get_db

BASE_DIR = Path(__file__).resolve().parent

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_db()
    yield
    await close_db()


app = FastAPI(title="Bellhop", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Apply rate limit to login specifically
original_login = auth_router.routes
for route in auth_router.routes:
    if hasattr(route, "path") and route.path == "/login" and hasattr(route, "endpoint"):
        route.endpoint = limiter.limit("5/minute")(route.endpoint)
        break

app.include_router(auth_router)
app.include_router(arr_router)


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = BASE_DIR / "templates" / "index.html"
    return HTMLResponse(html_path.read_text())
