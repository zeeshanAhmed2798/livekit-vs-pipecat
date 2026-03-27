"""
VoxKit Test Agent — LiveKit Agents Framework
=============================================
Uses: Soniox STT (Urdu + English) → OpenAI GPT-4o → OpenAI TTS → Phone audio
Requires: LiveKit Cloud + Twilio Elastic SIP Trunk

Run:  python agent.py dev
"""

import logging
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    cli,
)
from livekit.plugins import openai, soniox, silero

load_dotenv()

logger = logging.getLogger("voxkit-agent")
logger.setLevel(logging.INFO)

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

# ---------------------------------------------------------------------------
# Agent server setup
# ---------------------------------------------------------------------------

server = AgentServer()


@server.rtc_session(agent_name="voxkit-test-agent")
async def entrypoint(ctx: JobContext) -> None:
    """
    Called for every inbound SIP call that matches the dispatch rule.
    The agent_name must match the dispatch rule configured in LiveKit Cloud.
    """
    logger.info(
        "New call received — room=%s",
        ctx.room.name,
    )

    # --- Build the voice pipeline ---
    stt = soniox.STT(
        params=soniox.STTOptions(
            language_hints=SONIOX_LANGUAGES,
        ),
    )

    llm = openai.LLM(model=OPENAI_MODEL)

    tts = openai.TTS(voice=OPENAI_TTS_VOICE)

    # --- Create session & start ---
    session = AgentSession(
        stt=stt,
        llm=llm,
        tts=tts,
        vad=silero.VAD.load(),
    )

    await session.start(
        room=ctx.room,
        agent=Agent(instructions=SYSTEM_PROMPT),
    )

    # Greet the caller immediately after connecting
    await session.generate_reply(
        instructions="Greet the caller warmly. Say hello and ask how you can help them today."
    )

    logger.info("Agent session started — greeting sent")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli.run_app(server)
