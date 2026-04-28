"""WebSocket endpoint for the PPIS Campus Agent.

Ported from whatsapp-bot-backend. Allows the campus agent to connect
and serve camera snapshots for both app and WhatsApp users.

Protocol:
  Server sends: snapshot_request {classroom, request_id}
  Agent sends:  snapshot_image   {request_id, image_base64, ...}
  Agent sends:  snapshot_complete {request_id, image_count}
"""

import asyncio
import json
import logging
import os
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()

_agent_ws: WebSocket | None = None
_pending_requests: dict[str, asyncio.Future] = {}
_pending_images: dict[str, list] = {}

AGENT_SECRET = os.environ.get("AGENT_SECRET", "")


def is_agent_connected() -> bool:
    return _agent_ws is not None


async def request_snapshot(classroom: str, timeout: float = 60.0) -> dict:
    """Request a snapshot from the campus agent.

    Returns dict with: success, images, image_count, error.
    """
    global _agent_ws
    if _agent_ws is None:
        return {"success": False, "error": "Campus agent is not connected"}

    request_id = str(uuid.uuid4())
    future: asyncio.Future = asyncio.get_event_loop().create_future()
    _pending_requests[request_id] = future
    _pending_images[request_id] = []

    try:
        await _agent_ws.send_json({
            "type": "snapshot_request",
            "classroom": classroom,
            "request_id": request_id,
        })
        logger.info(f"Snapshot request {request_id} for: {classroom}")
        result = await asyncio.wait_for(future, timeout=timeout)
        return result
    except asyncio.TimeoutError:
        collected = _pending_images.pop(request_id, [])
        if collected:
            return {
                "success": True,
                "classroom": classroom,
                "image_count": len(collected),
                "images": collected,
            }
        return {"success": False, "error": "Snapshot request timed out"}
    except Exception as e:
        logger.error(f"Snapshot error: {e}")
        return {"success": False, "error": str(e)}
    finally:
        _pending_requests.pop(request_id, None)
        _pending_images.pop(request_id, None)


@router.websocket("/ws/agent")
async def agent_websocket(websocket: WebSocket):
    """WebSocket endpoint for the PPIS Campus Agent."""
    global _agent_ws

    secret = websocket.headers.get("x-agent-secret", "")
    if AGENT_SECRET and secret != AGENT_SECRET:
        logger.warning("Agent WebSocket rejected: invalid secret")
        await websocket.close(code=4001, reason="Invalid agent secret")
        return

    await websocket.accept()
    _agent_ws = websocket
    logger.info("Campus agent connected via WebSocket")

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "")

            if msg_type == "agent_hello":
                logger.info(
                    f"Agent hello: {data.get('dvr_count', 0)} DVRs, "
                    f"{data.get('camera_count', 0)} cameras"
                )

            elif msg_type == "snapshot_image":
                request_id = data.get("request_id", "")
                if request_id in _pending_images:
                    _pending_images[request_id].append({
                        "image_base64": data.get("image_base64", ""),
                        "description": data.get("description", ""),
                        "filename": data.get("filename", "snapshot.jpg"),
                    })

            elif msg_type == "snapshot_complete":
                request_id = data.get("request_id", "")
                future = _pending_requests.get(request_id)
                if future and not future.done():
                    images = _pending_images.get(request_id, [])
                    future.set_result({
                        "success": True,
                        "classroom": data.get("classroom", ""),
                        "image_count": len(images),
                        "images": images,
                    })

            elif msg_type == "snapshot_response":
                # Legacy v1 protocol
                request_id = data.get("request_id", "")
                future = _pending_requests.get(request_id)
                if future and not future.done():
                    future.set_result(data)

    except WebSocketDisconnect:
        logger.info("Campus agent disconnected")
    except Exception as e:
        logger.error(f"Agent WebSocket error: {e}")
    finally:
        if _agent_ws is websocket:
            _agent_ws = None
