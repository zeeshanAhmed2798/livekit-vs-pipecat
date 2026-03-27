"""
VoxKit Test Server — Pipecat + Daily + Twilio
==============================================
FastAPI server that orchestrates:
  1. Receives Twilio webhook on POST /call
  2. Creates a Daily room with SIP enabled
  3. Spawns a bot.py subprocess with room details
  4. Returns TwiML with hold music to Twilio

Run: uvicorn server:app --host 0.0.0.0 --port 8000
"""

import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voxkit-server")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DAILY_API_KEY = os.getenv("DAILY_API_KEY")
DAILY_API_URL = os.getenv("DAILY_API_URL", "https://api.daily.co/v1")

app = FastAPI(title="VoxKit Pipecat Test Server")


# ---------------------------------------------------------------------------
# Daily helpers
# ---------------------------------------------------------------------------

async def create_daily_room() -> dict:
    """Create a Daily room with SIP dial-in enabled."""
    expiry = datetime.now(timezone.utc) + timedelta(hours=1)

    room_config = {
        "properties": {
            "sip": {
                "display_name": "VoxKit Caller",
                "sip_mode": "dial-in",
                "num_endpoints": 1,
            },
            "exp": int(expiry.timestamp()),
            "enable_chat": False,
            "start_video_off": True,
            "start_audio_off": False,
        },
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DAILY_API_URL}/rooms",
            headers={"Authorization": f"Bearer {DAILY_API_KEY}"},
            json=room_config,
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

    logger.info("Created Daily room: %s", data.get("url"))
    return data


async def get_daily_token(room_name: str) -> str:
    """Get a meeting token for the bot to join the room."""
    token_config = {
        "properties": {
            "room_name": room_name,
            "is_owner": True,
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        },
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{DAILY_API_URL}/meeting-tokens",
            headers={"Authorization": f"Bearer {DAILY_API_KEY}"},
            json=token_config,
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

    return data["token"]


# ---------------------------------------------------------------------------
# Twilio webhook — called when someone dials your Twilio number
# ---------------------------------------------------------------------------

@app.post("/call")
async def handle_incoming_call(request: Request):
    """
    Twilio sends a POST here when a call comes in.

    We:
      1. Extract the CallSid
      2. Create a Daily room with SIP
      3. Spawn bot.py as a subprocess
      4. Return TwiML with hold music so the caller waits
    """
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "unknown")
    caller = form_data.get("From", "unknown")
    called = form_data.get("To", "unknown")

    logger.info(
        "Incoming call — SID=%s, From=%s, To=%s",
        call_sid, caller, called,
    )

    try:
        # 1. Create Daily room
        room = await create_daily_room()
        room_url = room["url"]
        room_name = room["name"]
        sip_endpoint = room.get("config", {}).get("sip", {}).get("sip_uri", "")

        # If sip_uri not in config, construct it from the room's sip_endpoint field
        if not sip_endpoint:
            sip_info = room.get("config", {}).get("sip", {})
            # The SIP endpoint is typically available in the room config
            # For Daily rooms with SIP enabled, the endpoint format is:
            # sip:<room-specific-id>@sip.daily.co
            sip_endpoint = f"sip:{room_name}@sip.daily.co"
            logger.info("Constructed SIP endpoint: %s", sip_endpoint)

        # 2. Get bot token
        token = await get_daily_token(room_name)

        # 3. Spawn bot process
        bot_cmd = [
            sys.executable, "bot.py",
            "--room-url", room_url,
            "--token", token,
            "--call-sid", call_sid,
            "--sip-endpoint", sip_endpoint,
        ]

        logger.info("Spawning bot process for call %s", call_sid)
        subprocess.Popen(
            bot_cmd,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            env={**os.environ},
        )

        # 4. Return TwiML — hold music while bot initializes
        # The bot's on_dialin_ready handler will update this call via Twilio API
        # to forward audio to Daily's SIP endpoint
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play loop="10">http://com.twilio.sounds.music.s3.amazonaws.com/ClockworkWaltz.mp3</Play>
</Response>"""

        logger.info("Returning hold music TwiML for call %s", call_sid)
        return PlainTextResponse(content=twiml, media_type="text/xml")

    except Exception as e:
        logger.error("Failed to handle incoming call: %s", e, exc_info=True)
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>We're sorry, there was an error connecting your call. Please try again later.</Say>
    <Hangup/>
</Response>"""
        return PlainTextResponse(content=twiml, media_type="text/xml")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "voxkit-pipecat-test",
        "daily_api_url": DAILY_API_URL,
    }


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    logger.info("Starting VoxKit Pipecat server on port %d", port)
    uvicorn.run(app, host="0.0.0.0", port=port)
