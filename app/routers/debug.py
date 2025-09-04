"""Debug endpoints to inspect active sessions, tasks, and websockets."""
from fastapi import APIRouter
from typing import Dict, Any, List

from ..utils.logging import get_logger
from ..core.netsapiens_handler import netsapiens_handler

logger = get_logger(__name__)
router = APIRouter(prefix="/debug", tags=["debug"]) 


@router.get("/sessions")
async def list_sessions() -> Dict[str, Any]:
    """Return current active sessions, task states, and websocket count.
    Intended for troubleshooting lingering resources after hangups.
    """
    sm = netsapiens_handler.session_manager
    sessions = sm.get_active_sessions()

    sessions_list: List[Dict[str, Any]] = []
    for sid, sess in sessions.items():
        try:
            sessions_list.append({
                "session_id": sid,
                "is_active": bool(getattr(sess, "is_active", False)),
                "has_live_events": bool(getattr(sess, "live_events", None) is not None),
                "has_live_request_queue": bool(getattr(sess, "live_request_queue", None) is not None),
                "external_id": getattr(sess, "external_id", None),
                "business_domain": getattr(sess, "business_domain", None),
            })
        except Exception:
            # Never let a single bad attribute block the debug payload
            sessions_list.append({"session_id": sid, "error": "session_introspection_failed"})

    # Task states
    task_states: Dict[str, Any] = {}
    for sid, task in sm.session_tasks.items():
        task_states[sid] = {
            "done": task.done(),
            "cancelled": task.cancelled(),
            "state": str(task._state) if hasattr(task, "_state") else ("done" if task.done() else "pending"),
        }

    # WebSocket connections
    ws_count = len(netsapiens_handler.active_connections)
    ws_sessions = list(netsapiens_handler.active_connections.keys())

    return {
        "active_sessions_count": len(sessions),
        "active_sessions": sessions_list,
        "session_tasks": task_states,
        "active_websockets_count": ws_count,
        "websocket_sessions": ws_sessions,
    }


@router.post("/gc/{session_id}")
async def force_cleanup(session_id: str) -> Dict[str, Any]:
    """Force cleanup of a session and close its websocket if present.
    Useful if a session appears to linger after a hangup.
    """
    try:
        await netsapiens_handler.session_manager.end_session(session_id)
        # Also ensure websocket is removed/closed
        await netsapiens_handler.disconnect(session_id)
        return {"status": "ok", "session_id": session_id}
    except Exception as e:
        logger.error(f"force_cleanup failed for {session_id}: {e}")
        return {"status": "error", "session_id": session_id, "message": str(e)}
