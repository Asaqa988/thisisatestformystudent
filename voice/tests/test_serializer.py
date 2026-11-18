"""The WebSocket format the shop page speaks."""

import asyncio
import json

from pipecat.frames.frames import (
    InputAudioRawFrame,
    InterruptionFrame,
    OutputAudioRawFrame,
    OutputTransportMessageUrgentFrame,
    TextFrame,
)

from app.captions import event
from app.serializer import IN_SAMPLE_RATE, PCMSerializer


def run(coro):
    return asyncio.run(coro)


def test_microphone_bytes_become_input_audio():
    frame = run(PCMSerializer().deserialize(b"\x01\x00\x02\x00"))

    assert isinstance(frame, InputAudioRawFrame)
    assert frame.sample_rate == IN_SAMPLE_RATE
    assert frame.num_channels == 1
    assert frame.audio == b"\x01\x00\x02\x00"


def test_odd_or_empty_audio_and_text_are_ignored():
    serializer = PCMSerializer()
    assert run(serializer.deserialize(b"")) is None
    assert run(serializer.deserialize(b"\x01")) is None
    assert run(serializer.deserialize('{"type": "ping"}')) is None


def test_assistant_audio_is_sent_as_raw_bytes():
    frame = OutputAudioRawFrame(audio=b"\x00\x01", sample_rate=24000, num_channels=1)
    assert run(PCMSerializer().serialize(frame)) == b"\x00\x01"


def test_interruption_tells_the_page_to_stop_playing():
    assert json.loads(run(PCMSerializer().serialize(InterruptionFrame()))) == {
        "type": "interrupted"
    }


def test_caption_events_are_sent_as_json_with_arabic_kept():
    text = run(PCMSerializer().serialize(event("user-text", "كم سعر الباقة؟")))

    assert json.loads(text) == {"type": "user-text", "text": "كم سعر الباقة؟"}
    assert "كم" in text  # not escaped as \\u sequences


def test_other_frames_and_foreign_messages_stay_inside():
    serializer = PCMSerializer()
    assert run(serializer.serialize(TextFrame(text="hi"))) is None
    foreign = OutputTransportMessageUrgentFrame(message={"label": "rtvi-ai", "type": "x"})
    assert run(serializer.serialize(foreign)) is None
