"""End-to-end check of the voice assistant without a microphone. Costs a few US cents.

It plays the part of a visitor: OpenAI speaks an Arabic question, the audio is sent to the
voice service like a microphone would, and the assistant's captions and voice are recorded.

    docker compose exec voice python -m scripts.e2e_check "كم سعر الساعة الذكية؟"

Needs OPENAI_API_KEY and ANTHROPIC_API_KEY in the voice service, and VOICE_SESSION_SECRET
on both backend and voice. Writes the assistant's answer to /tmp/answer.wav.
"""

import asyncio
import json
import sys
import time
import wave

import httpx
import numpy as np
import websockets
from openai import OpenAI

from app.config import get_settings

BACKEND = "http://backend:8000"
VOICE_WS = "ws://localhost:8000/ws"
CHUNK = 640  # 40 ms at 16 kHz


def spoken_question(text: str) -> bytes:
    """16 kHz 16-bit mono PCM of `text`, spoken by OpenAI."""
    settings = get_settings()
    audio = OpenAI(api_key=settings.openai_api_key).audio.speech.create(
        model=settings.openai_tts_model, voice="cedar", input=text, response_format="pcm"
    )
    pcm24 = np.frombuffer(audio.read(), dtype=np.int16).astype(np.float32)
    positions = np.arange(0, len(pcm24) - 1, 24000 / 16000)
    pcm16 = np.interp(positions, np.arange(len(pcm24)), pcm24)
    return pcm16.astype(np.int16).tobytes()


async def main(question: str) -> None:
    ticket = httpx.post(f"{BACKEND}/api/v1/public/voice-ticket").json()
    origin = get_settings().allowed_origins[0]
    question_pcm = spoken_question(question)
    answer = bytearray()
    events: list[dict] = []
    started = time.monotonic()
    first_audio_after_question = None

    async with websockets.connect(f"{VOICE_WS}?token={ticket['token']}", origin=origin) as ws:

        async def receive():
            nonlocal first_audio_after_question
            async for message in ws:
                if isinstance(message, bytes):
                    if question_sent.is_set():
                        if first_audio_after_question is None:
                            first_audio_after_question = time.monotonic()
                        answer.extend(message)
                else:
                    event = json.loads(message)
                    events.append(event)
                    if event["type"] == "error":
                        print("ERROR:", event)
                        return

        question_sent = asyncio.Event()
        receiver = asyncio.create_task(receive())
        await asyncio.sleep(6)  # let the greeting play
        silence = b"\x00\x00" * CHUNK
        for i in range(0, len(question_pcm), CHUNK * 2):
            await ws.send(question_pcm[i : i + CHUNK * 2].ljust(CHUNK * 2, b"\x00"))
            await asyncio.sleep(0.04)
        sent_at = time.monotonic()
        question_sent.set()
        for _ in range(50):  # 2 s of silence ends the visitor's turn
            await ws.send(silence)
            await asyncio.sleep(0.04)
        await asyncio.sleep(14)
        receiver.cancel()

    print(f"Session: {time.monotonic() - started:.1f} s")
    bot_text = ""
    for event in events:
        if event["type"] == "user-text":
            print("VISITOR:", event["text"])
        elif event["type"] == "bot-start":
            bot_text = ""
        elif event["type"] == "bot-delta":
            bot_text += event["text"]
        elif event["type"] == "bot-end":
            print("ASSISTANT:", bot_text)
    if first_audio_after_question:
        delay = first_audio_after_question - sent_at
        print(f"First answer audio {delay:.1f} s after the question ended")
    print(f"Answer audio: {len(answer) / 2 / 24000:.1f} s -> /tmp/answer.wav")
    with wave.open("/tmp/answer.wav", "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(24000)
        out.writeframes(bytes(answer))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "كم سعر الساعة الذكية؟"))
