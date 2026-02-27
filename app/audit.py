"""Matrix audit log — fire-and-forget messages to an unencrypted room."""

import asyncio
import logging

import httpx

from app.config import (
    MATRIX_AUDIT_ROOM_ID,
    MATRIX_BOT_ACCESS_TOKEN,
    MATRIX_HOMESERVER_URL,
)

logger = logging.getLogger(__name__)


def send_audit_message(message: str) -> None:
    """Schedule an audit message to be sent without blocking the caller."""
    if not MATRIX_AUDIT_ROOM_ID or not MATRIX_BOT_ACCESS_TOKEN:
        logger.debug("Audit log not configured, skipping")
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    loop.create_task(_send(message))


async def _send(message: str) -> None:
    import time

    room_id = MATRIX_AUDIT_ROOM_ID
    txn_id = str(int(time.time() * 1000))

    url = (
        f"{MATRIX_HOMESERVER_URL.rstrip('/')}/_matrix/client/v3/rooms/"
        f"{room_id}/send/m.room.message/{txn_id}"
    )
    body = {
        "msgtype": "m.text",
        "body": message,
    }
    headers = {"Authorization": f"Bearer {MATRIX_BOT_ACCESS_TOKEN}"}

    try:
        async with httpx.AsyncClient() as client:
            await client.put(url, json=body, headers=headers, timeout=10.0)
    except Exception:
        logger.warning("Failed to send audit message: %s", message, exc_info=True)
