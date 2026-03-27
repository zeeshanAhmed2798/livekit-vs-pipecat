"""
VoxKit Test Bot - Pipecat Framework
===================================
Uses: Soniox STT (Urdu + English) -> OpenAI GPT-4o -> OpenAI TTS -> Phone audio
Requires: Daily + Twilio SIP dial-in

This bot is spawned by server.py for each incoming call.
"""

import argparse
import asyncio
import logging
import os

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
from pipecat.transports.daily.transport import DailyParams, DailyTransport

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voxkit-bot")

SYSTEM_PROMPT = (
    "You are a friendly restaurant ordering assistant for VoxKit. "
    "You speak Urdu and English. You greet callers warmly and help them "
    "with their questions. Keep responses concise and natural for voice "
    "conversation."
)

OPENAI_MODEL = "gpt-4o"
OPENAI_TTS_VOICE = "nova"
SONIOX_LANGUAGES = ["en", "ur"]


def mask_secret(value: str | None, visible_start: int = 4, visible_end: int = 2) -> str:
    if not value:
        return "<missing>"
    if len(value) <= visible_start + visible_end:
        return "*" * len(value)
    return f"{value[:visible_start]}{'*' * (len(value) - visible_start - visible_end)}{value[-visible_end:]}"


def extract_daily_sip_endpoint(cdata, fallback: str) -> str:
    """Prefer the actual SIP endpoint emitted by Daily over a constructed fallback."""
    if isinstance(cdata, str) and cdata:
        return cdata
    if isinstance(cdata, dict):
        return (
            cdata.get("sip_endpoint")
            or cdata.get("sipEndpoint")
            or cdata.get("sip_uri")
            or cdata.get("sipUri")
            or fallback
        )
    return fallback


def is_remote_participant(participant: dict) -> bool:
    """Best-effort filter so we greet only the real caller, not the local bot."""
    if participant.get("local") is True:
        return False

    info = participant.get("info", {})
    if info.get("isLocal") is True:
        return False
    if info.get("userName") == "VoxKit Bot":
        return False

    return True


async def run_bot(
    room_url: str,
    token: str,
    call_sid: str,
    sip_endpoint: str,
) -> None:
    """Main bot entrypoint - called once per phone call."""

    twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")

    logger.info("Twilio env loaded: account_sid=%s", mask_secret(twilio_account_sid))
    logger.info("Twilio env loaded: auth_token=%s", mask_secret(twilio_auth_token))

    twilio_client = TwilioClient(
        twilio_account_sid,
        twilio_auth_token,
    )

    transport = DailyTransport(
        room_url,
        token,
        "VoxKit Bot",
        DailyParams(
            api_key=os.getenv("DAILY_API_KEY"),
            audio_in_enabled=True,
            audio_out_enabled=True,
            video_out_enabled=False,
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.3)),
        ),
    )

    stt = SonioxSTTService(
        api_key=os.getenv("SONIOX_API_KEY"),
        language_hints=SONIOX_LANGUAGES,
    )

    llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY"),
        settings=OpenAILLMService.Settings(model=OPENAI_MODEL),
    )

    tts = OpenAITTSService(
        api_key=os.getenv("OPENAI_API_KEY"),
        settings=OpenAITTSService.Settings(voice=OPENAI_TTS_VOICE),
    )

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

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
        ),
    )

    call_forwarded = False
    initial_greeting_sent = False

    async def queue_initial_greeting(reason: str) -> None:
        nonlocal initial_greeting_sent
        if initial_greeting_sent:
            return
        initial_greeting_sent = True
        logger.info("Triggering initial greeting (%s)", reason)
        await task.queue_frames([context_aggregator.user().get_context_frame()])

    @transport.event_handler("on_dialin_ready")
    async def on_dialin_ready(transport_ref, cdata):
        nonlocal call_forwarded
        if call_forwarded:
            return

        call_forwarded = True
        real_sip_endpoint = extract_daily_sip_endpoint(cdata, sip_endpoint)
        logger.info("SIP endpoint ready - forwarding Twilio call %s to %s", call_sid, real_sip_endpoint)

        try:
            twilio_client.calls(call_sid).update(
                twiml=f'<Response><Dial><Sip>{real_sip_endpoint}</Sip></Dial></Response>'
            )
            logger.info("Call forwarded successfully to Daily SIP endpoint")
        except Exception as e:
            logger.error("Failed to forward call: %s", e)

    @transport.event_handler("on_participant_joined")
    async def on_participant_joined(transport_ref, participant):
        logger.info(
            "Participant joined: %s",
            participant.get("info", {}).get("userName", "unknown"),
        )
        if is_remote_participant(participant):
            await queue_initial_greeting("remote participant joined")

    @transport.event_handler("on_participant_left")
    async def on_participant_left(transport_ref, participant, reason):
        logger.info(
            "Participant left: %s (reason: %s)",
            participant.get("info", {}).get("userName", "unknown"),
            reason,
        )

    @transport.event_handler("on_dialin_error")
    async def on_dialin_error(transport_ref, data):
        logger.error("Dial-in error: %s", data)

    @transport.event_handler("on_dialin_connected")
    async def on_dialin_connected(transport_ref, data):
        logger.info("Dial-in connected: %s", data)
        await queue_initial_greeting("dial-in connected")

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport_ref, participant):
        logger.info("Client connected - bot transport is ready")

    runner = PipelineRunner()

    logger.info("Bot starting - room=%s, call_sid=%s", room_url, call_sid)
    await runner.run(task)
    logger.info("Bot finished - call ended")


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
