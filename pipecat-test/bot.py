"""
VoxKit Test Bot — Pipecat Framework
====================================
Uses: Soniox STT (Urdu + English) → OpenAI GPT-4o → OpenAI TTS → Phone audio
Requires: Daily + Twilio SIP dial-in

This bot is spawned by server.py for each incoming call.
"""

import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
from twilio.rest import Client as TwilioClient

from pipecat.audio.vad.silero import SileroVADAnalyzer, VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai.tts import OpenAITTSService
from pipecat.services.soniox.stt import SonioxSTTService
from pipecat.transports.daily.transport import DailyTransport, DailyParams

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voxkit-bot")

# ---------------------------------------------------------------------------
# Shared configuration — identical to LiveKit test
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a friendly restaurant ordering assistant for VoxKit. "
    "You speak Urdu and English. You greet callers warmly and help them "
    "with their questions. Keep responses concise and natural for voice "
    "conversation."
)

OPENAI_MODEL = "gpt-4o"
OPENAI_TTS_VOICE = "nova"
SONIOX_LANGUAGES = ["en", "ur"]


async def run_bot(
    room_url: str,
    token: str,
    call_sid: str,
    sip_endpoint: str,
) -> None:
    """Main bot entrypoint — called once per phone call."""

    # --- Twilio client for call forwarding ---
    twilio_client = TwilioClient(
        os.getenv("TWILIO_ACCOUNT_SID"),
        os.getenv("TWILIO_AUTH_TOKEN"),
    )

    # --- Daily WebRTC transport ---
    transport = DailyTransport(
        room_url,
        token,
        "VoxKit Bot",
        DailyParams(
            api_key=os.getenv("DAILY_API_KEY"),
            audio_in_enabled=True,
            audio_out_enabled=True,
            video_out_enabled=False,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.3)),
        ),
    )

    # --- Guard against duplicate on_dialin_ready events ---
    call_forwarded = False

    @transport.event_handler("on_dialin_ready")
    async def on_dialin_ready(transport_ref, cdata):
        nonlocal call_forwarded
        if call_forwarded:
            return
        call_forwarded = True
        logger.info("SIP endpoint ready — forwarding Twilio call %s", call_sid)

        try:
            twilio_client.calls(call_sid).update(
                twiml=f'<Response><Dial><Sip>{sip_endpoint}</Sip></Dial></Response>'
            )
            logger.info("Call forwarded successfully to Daily SIP endpoint")
        except Exception as e:
            logger.error("Failed to forward call: %s", e)

    @transport.event_handler("on_participant_joined")
    async def on_participant_joined(transport_ref, participant):
        logger.info("Participant joined: %s", participant.get("info", {}).get("userName", "unknown"))

    @transport.event_handler("on_participant_left")
    async def on_participant_left(transport_ref, participant, reason):
        logger.info("Participant left: %s (reason: %s)", participant.get("info", {}).get("userName", "unknown"), reason)

    @transport.event_handler("on_dialin_error")
    async def on_dialin_error(transport_ref, data):
        logger.error("Dial-in error: %s", data)

    # --- AI services ---
    stt = SonioxSTTService(
        api_key=os.getenv("SONIOX_API_KEY"),
        language_hints=SONIOX_LANGUAGES,
    )

    llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY"),
        model=OPENAI_MODEL,
    )

    tts = OpenAITTSService(
        api_key=os.getenv("OPENAI_API_KEY"),
        voice=OPENAI_TTS_VOICE,
    )

    # --- Conversation context with system prompt + initial greeting ---
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "system",
            "content": (
                "Greet the caller warmly. Say hello and ask how you can help "
                "them today. Keep it brief and natural."
            ),
        },
    ]

    context = OpenAILLMContext(messages=messages)
    context_aggregator = llm.create_context_aggregator(context)

    # --- Pipeline ---
    pipeline = Pipeline(
        [
            transport.input(),               # Phone audio in
            stt,                             # Speech → text
            context_aggregator.user(),       # Accumulate user messages
            llm,                             # Generate response
            tts,                             # Text → speech
            transport.output(),              # Audio back to phone
            context_aggregator.assistant(),  # Accumulate assistant messages
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
        ),
    )

    # --- Run ---
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport_ref, participant):
        logger.info("Client connected — starting conversation")
        # Trigger the initial greeting by running the LLM with our seeded context
        await task.queue_frames([context_aggregator.user().get_context_frame()])

    runner = PipelineRunner()

    logger.info("Bot starting — room=%s, call_sid=%s", room_url, call_sid)
    await runner.run(task)
    logger.info("Bot finished — call ended")


# ---------------------------------------------------------------------------
# CLI entry point — receives args from server.py subprocess
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="VoxKit Pipecat Bot")
    parser.add_argument("--room-url", required=True, help="Daily room URL")
    parser.add_argument("--token", required=True, help="Daily room token")
    parser.add_argument("--call-sid", required=True, help="Twilio Call SID")
    parser.add_argument("--sip-endpoint", required=True, help="Daily SIP endpoint")
    args = parser.parse_args()

    asyncio.run(
        run_bot(
            room_url=args.room_url,
            token=args.token,
            call_sid=args.call_sid,
            sip_endpoint=args.sip_endpoint,
        )
    )


if __name__ == "__main__":
    main()
