"""Send what was said to the page as text, so it can show captions."""

from pipecat.frames.frames import (
    Frame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    OutputTransportMessageUrgentFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from app.serializer import EVENT_KEY


def event(kind: str, text: str = "") -> OutputTransportMessageUrgentFrame:
    return OutputTransportMessageUrgentFrame(message={EVENT_KEY: 1, "type": kind, "text": text})


class UserCaptions(FrameProcessor):
    """Placed right after speech-to-text: the visitor's words."""

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame) and frame.text.strip():
            await self.push_frame(event("user-text", frame.text.strip()))
        await self.push_frame(frame, direction)


class BotCaptions(FrameProcessor):
    """Placed right after the LLM: the assistant's words as they are written."""

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMFullResponseStartFrame):
            await self.push_frame(event("bot-start"))
        elif isinstance(frame, LLMTextFrame):
            await self.push_frame(event("bot-delta", frame.text))
        elif isinstance(frame, LLMFullResponseEndFrame):
            await self.push_frame(event("bot-end"))
        elif isinstance(frame, TTSSpeakFrame):
            # The greeting: spoken without the LLM.
            await self.push_frame(event("bot-start"))
            await self.push_frame(event("bot-delta", frame.text))
            await self.push_frame(event("bot-end"))
        await self.push_frame(frame, direction)
