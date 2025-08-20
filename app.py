#!/usr/bin/env python3
"""
Flask API to trigger ElevenLabs Conversational AI outbound calls (Monky-ski edition).
- POST /call   -> one call (JSON with to_number, agent_id, agent_phone_number_id)
- POST /batch  -> many calls (JSON { items: [...] })
- GET  /ping   -> pong
"""

import os
import time
from typing import Dict, Any, List
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

# ---------- Helpers ----------
def dial_once(payload: Dict[str, Any]) -> Dict[str, Any]:
    provider = (payload.get("provider") or "twilio").lower()
    to_number = payload.get("to_number")
    agent_id = payload.get("agent_id")
    agent_phone_number_id = payload.get("agent_phone_number_id")

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
            return {
                "ok": True,
                "provider": "sip",
                "conversation_id": getattr(resp, "conversation_id", None) if resp else None,
                "sip_call_id": getattr(resp, "sip_call_id", None) if resp else None,
            }

        resp = client.conversational_ai.twilio.outbound_call(
            agent_id=agent_id,
            agent_phone_number_id=agent_phone_number_id,
            to_number=to_number,
        )
        return {
            "ok": True,
            "provider": "twilio",
            "conversation_id": getattr(resp, "conversation_id", None) if resp else None,
            "callSid": getattr(resp, "callSid", None) if resp else None,
        }

    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

def dial_with_retries(item: Dict[str, Any], retries: int = 2, backoff_seconds: float = 2.0) -> Dict[str, Any]:
    attempts = 0
    last = None
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

    results = []
    for i, item in enumerate(items, start=1):
        res = dial_with_retries(item, retries=retries, backoff_seconds=backoff)
        res["index"] = i
        results.append(res)
        if delay_seconds > 0 and i < len(items):
            time.sleep(delay_seconds)

    ok_count = sum(1 for r in results if r.get("ok"))
    return jsonify({"ok": True, "total": len(items), "successes": ok_count, "results": results}), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5055"))  # use 5055 by default on macOS
    app.run(host="0.0.0.0", port=port)
