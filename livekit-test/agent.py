"""
VoxKit Test Agent — LiveKit Agents Framework
=============================================
Uses: Soniox STT (Urdu + English) → OpenAI GPT-4o → OpenAI TTS → Phone audio
Requires: LiveKit Cloud + Twilio Elastic SIP Trunk

Run:  python agent.py dev
"""

import logging
import os

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    cli,
    room_io,
)
from livekit.agents.metrics import EOUMetrics, LLMMetrics, STTMetrics, TTSMetrics
from livekit.plugins import noise_cancellation, openai as lk_openai, soniox
from livekit.plugins.silero import VAD

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("voxkit-agent")

# ---------------------------------------------------------------------------
# Shared configuration — keep identical across both test setups
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
AGENT_NAME = os.environ.get("LIVEKIT_AGENT_NAME", "voxkit-test-agent")


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

class VoxKitAgent(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions="Greet the caller warmly. Say hello and ask how you can help them today."
        )


# ---------------------------------------------------------------------------
# Server + prewarm
# ---------------------------------------------------------------------------

server = AgentServer()


def prewarm(proc: JobProcess) -> None:
    proc.userdata["vad"] = VAD.load(
        min_silence_duration=0.3,
        min_speech_duration=0.05,
        activation_threshold=0.2,
    )
    logger.info("VAD prewarmed")


server.setup_fnc = prewarm


# ---------------------------------------------------------------------------
# Metrics logging
# ---------------------------------------------------------------------------

def on_metrics(ev: MetricsCollectedEvent) -> None:
    m = ev.metrics
    if isinstance(m, EOUMetrics):
        logger.info(
            "[EOU] end_of_utterance=%.0fms | transcription=%.0fms",
            m.end_of_utterance_delay * 1000, m.transcription_delay * 1000,
        )
    elif isinstance(m, STTMetrics):
        logger.info(
            "[STT] audio=%.0fms | processing=%.0fms | streamed=%s",
            m.audio_duration * 1000, m.duration * 1000, m.streamed,
        )
    elif isinstance(m, LLMMetrics):
        logger.info(
            "[LLM] TTFT=%.0fms | total=%.0fms | tokens=%d",
            m.ttft * 1000, m.duration * 1000, m.total_tokens,
        )
    elif isinstance(m, TTSMetrics):
        logger.info(
            "[TTS] TTFB=%.0fms | total=%.0fms | audio=%.0fms",
            m.ttfb * 1000, m.duration * 1000, m.audio_duration * 1000,
        )


# ---------------------------------------------------------------------------
# RTC session entrypoint
# ---------------------------------------------------------------------------

@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: JobContext) -> None:
    ctx.log_context_fields = {"room": ctx.room.name}
    logger.info("Session starting | room=%s", ctx.room.name)

    session = AgentSession(
        stt=soniox.STT(
            params=soniox.STTOptions(
                language_hints=SONIOX_LANGUAGES,
            ),
        ),
        llm=lk_openai.LLM(model=OPENAI_MODEL),
        tts=lk_openai.TTS(voice=OPENAI_TTS_VOICE),
        vad=ctx.proc.userdata["vad"],
    )

    session.on("metrics_collected", on_metrics)

    await session.start(
        agent=VoxKitAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    await ctx.connect()
    logger.info("Session ready | room=%s", ctx.room.name)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli.run_app(server)