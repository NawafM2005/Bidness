#!/usr/bin/env python3
"""
Flask API to trigger ElevenLabs Conversational AI outbound calls (Monky-ski edition).
- POST /call   -> one call (JSON: to_number, agent_id, agent_phone_number_id, provider?, retries?, backoff_seconds?, debug?)
- POST /batch  -> many calls (JSON: { items: [...], delay_seconds?, retries?, backoff_seconds? })
- GET  /ping   -> pong

Security: none (intentionally). Do NOT expose publicly unless you're comfy with that.
"""

import os
import time
from typing import Dict, Any, List, Optional

from flask import Flask, request, jsonify
from dotenv import load_dotenv
from elevenlabs import ElevenLabs

# ---------- Setup ----------
load_dotenv()
app = Flask(__name__)

ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY", "")
if not ELEVEN_KEY:
    raise SystemExit("Missing ELEVENLABS_API_KEY in environment")

client = ElevenLabs(api_key=ELEVEN_KEY)

# ---------- Utils ----------
def _to_dict(resp: Any) -> Dict[str, Any]:
    """
    Normalize SDK response (pydantic model / object / dict) -> dict.
    """
    if isinstance(resp, dict):
        return resp
    # pydantic v2 uses model_dump; v1 uses dict
    for attr in ("model_dump", "dict"):
        fn = getattr(resp, attr, None)
        if callable(fn):
            try:
                d = fn()
                if isinstance(d, dict):
                    return d
            except Exception:
                pass
    try:
        return {k: v for k, v in getattr(resp, "__dict__", {}).items() if not k.startswith("_")}
    except Exception:
        return {"raw": str(resp)}

def _pick(d: Dict[str, Any], *keys: str, default: Optional[Any] = None) -> Any:
    """
    Return the first present & non-None key from dict `d`.
    Tries both given key and simple case-mapped variants.
    """
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
        # try a couple variants
        snake = k.replace("Id", "_id").replace("SID", "sid").replace("Sid", "sid")
        camel = "".join([w.capitalize() if i else w for i, w in enumerate(k.split("_"))])
        for alt in {snake, camel}:
            if alt in d and d[alt] is not None:
                return d[alt]
    return default

# ---------- Core dialers ----------
def dial_once(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform one outbound call via ElevenLabs using Twilio or SIP trunk.
    Required keys:
      - to_number
      - agent_id
      - agent_phone_number_id
    Optional:
      - provider: "twilio" (default) or "sip"
      - debug: bool (include raw SDK payload)
    """
    provider = (payload.get("provider") or "twilio").lower()
    to_number = payload.get("to_number")
    agent_id = payload.get("agent_id")
    agent_phone_number_id = payload.get("agent_phone_number_id")
    debug = bool(payload.get("debug", False))

    # basic validation
    missing = [k for k in ["to_number", "agent_id", "agent_phone_number_id"] if not payload.get(k)]
    if missing:
        return {"ok": False, "error": f"Missing fields: {', '.join(missing)}"}

    try:
        if provider == "sip":
            resp = client.conversational_ai.sip_trunk.outbound_call(
                agent_id=agent_id,
                agent_phone_number_id=agent_phone_number_id,
                to_number=to_number,
            )
            resp_dict = _to_dict(resp)
            out = {
                "ok": True,
                "provider": "sip",
                "conversation_id": _pick(resp_dict, "conversation_id", "conversationId", "conversation"),
                "sip_call_id": _pick(resp_dict, "sip_call_id", "sipCallId", "call_id", "sid"),
            }
            if debug:
                out["raw"] = resp_dict
            return out

        # default: twilio
        resp = client.conversational_ai.twilio.outbound_call(
            agent_id=agent_id,
            agent_phone_number_id=agent_phone_number_id,
            to_number=to_number,
        )
        resp_dict = _to_dict(resp)
        out = {
            "ok": True,
            "provider": "twilio",
            "conversation_id": _pick(resp_dict, "conversation_id", "conversationId", "conversation"),
            "callSid": _pick(resp_dict, "callSid", "call_sid", "sid", "twilio_call_sid"),
        }
        if debug:
            out["raw"] = resp_dict
        return out

    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

def dial_with_retries(item: Dict[str, Any], retries: int = 2, backoff_seconds: float = 2.0) -> Dict[str, Any]:
    """
    Retry wrapper. Returns final dict result with "attempts".
    """
    attempts = 0
    last: Optional[Dict[str, Any]] = None
    while attempts <= retries:
        attempts += 1
        result = dial_once(item)
        if result.get("ok"):
            result["attempts"] = attempts
            return result
        last = result
        time.sleep(min(backoff_seconds * attempts, 6.0))
    last = last or {"ok": False, "error": "Unknown error"}
    last["attempts"] = attempts
    return last

# ---------- Routes ----------
@app.get("/ping")
def ping():
    return jsonify({"ok": True, "message": "pong"})

@app.post("/call")
def api_call_single():
    data = request.get_json(silent=True) or {}
    retries = int(data.get("retries", 2))
    backoff = float(data.get("backoff_seconds", 2.0))

    result = dial_with_retries(data, retries=retries, backoff_seconds=backoff)
    return jsonify(result), (200 if result.get("ok") else 400)

@app.post("/batch")
def api_call_batch():
    payload = request.get_json(silent=True) or {}
    items: List[Dict[str, Any]] = payload.get("items") or []
    if not isinstance(items, list) or not items:
        return jsonify({"ok": False, "error": "Provide JSON { items: [...] }"}), 400

    delay_seconds = float(payload.get("delay_seconds", 0.0))
    retries = int(payload.get("retries", 2))
    backoff = float(payload.get("backoff_seconds", 2.0))

    results: List[Dict[str, Any]] = []
    for i, item in enumerate(items, start=1):
        res = dial_with_retries(item, retries=retries, backoff_seconds=backoff)
        res["index"] = i
        results.append(res)
        if delay_seconds > 0 and i < len(items):
            time.sleep(delay_seconds)

    ok_count = sum(1 for r in results if r.get("ok"))
    return jsonify({"ok": True, "total": len(items), "successes": ok_count, "results": results}), 200

# ---------- Entrypoint ----------
if __name__ == "__main__":
    # Default 5055 to dodge macOS AirPlay Receiver on 5000
    port = int(os.getenv("PORT", "5055"))
    app.run(host="0.0.0.0", port=port)
