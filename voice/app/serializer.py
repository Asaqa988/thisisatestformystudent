"""What travels over the browser's WebSocket.

Kept deliberately simple so the page needs no client library:

    browser -> service   binary: raw 16-bit PCM, mono, 16 kHz (microphone)
                         text:   JSON control messages (ignored for now)
    service -> browser   binary: raw 16-bit PCM, mono, 24 kHz (the assistant's voice)
                         text:   JSON events, e.g. {"type": "bot-text", "text": "..."}
"""

import json

from pipecat.frames.frames import (
    Frame,
    InputAudioRawFrame,
    InterruptionFrame,
    OutputAudioRawFrame,
    OutputTransportMessageFrame,
    OutputTransportMessageUrgentFrame,
)
from pipecat.serializers.base_serializer import FrameSerializer

IN_SAMPLE_RATE = 16000
OUT_SAMPLE_RATE = 24000
# Events our caption processor sends carry this key; other transport messages stay inside.
EVENT_KEY = "nexus"


class PCMSerializer(FrameSerializer):
    def __init__(self):
        super().__init__(FrameSerializer.InputParams(ignore_rtvi_messages=True))

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if isinstance(frame, OutputAudioRawFrame):
            return frame.audio
        if isinstance(frame, InterruptionFrame):
            # The visitor started talking: the page drops the audio it has queued.
            return json.dumps({"type": "interrupted"})
        if isinstance(frame, (OutputTransportMessageFrame, OutputTransportMessageUrgentFrame)):
            message = frame.message
            if isinstance(message, dict) and message.get(EVENT_KEY):
                return json.dumps(
                    {k: v for k, v in message.items() if k != EVENT_KEY}, ensure_ascii=False
                )
        return None

    async def deserialize(self, data: str | bytes) -> Frame | None:
        if isinstance(data, (bytes, bytearray)):
            if not data or len(data) % 2:
                return None  # 16-bit samples come in pairs of bytes
            return InputAudioRawFrame(
                audio=bytes(data), sample_rate=IN_SAMPLE_RATE, num_channels=1
            )
        return None
