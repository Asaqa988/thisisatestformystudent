"""One voice conversation: microphone -> OpenAI speech-to-text -> Claude -> OpenAI speech."""

from fastapi import WebSocket
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import EndFrame, OutputTransportMessageFrame, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.services.openai.tts import OpenAITTSService
from pipecat.transcriptions.language import Language
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport
from pipecat.workers.runner import WorkerRunner

from app.captions import BotCaptions, UserCaptions
from app.config import Settings
from app.prompt import TTS_INSTRUCTIONS, VoiceContext, greeting, system_prompt, transcription_hint
from app.serializer import EVENT_KEY, IN_SAMPLE_RATE, OUT_SAMPLE_RATE, PCMSerializer

APOLOGY = "عذرًا، في مشكلة تقنية هلأ وما بقدر أجاوب. جرّب كمان شوي."


def build_services(settings: Settings, context: VoiceContext):
    stt_settings = OpenAISTTService.Settings(
        language=Language.AR, prompt=transcription_hint(context) or None
    )
    if settings.openai_stt_model:
        stt_settings.model = settings.openai_stt_model
    stt = OpenAISTTService(api_key=settings.openai_api_key, settings=stt_settings)

    llm = AnthropicLLMService(
        api_key=settings.anthropic_api_key,
        settings=AnthropicLLMService.Settings(
            model=settings.voice_ai_model,
            system_instruction=system_prompt(context),
            max_tokens=settings.voice_max_tokens,
            effort=settings.voice_ai_effort,
            enable_prompt_caching=True,
        ),
    )

    tts = OpenAITTSService(
        api_key=settings.openai_api_key,
        sample_rate=OUT_SAMPLE_RATE,
        settings=OpenAITTSService.Settings(
            model=settings.openai_tts_model,
            voice=settings.openai_tts_voice,
            instructions=TTS_INSTRUCTIONS,
        ),
    )
    return stt, llm, tts


async def run_session(websocket: WebSocket, settings: Settings, context: VoiceContext) -> None:
    """Runs until the visitor hangs up, the session time runs out, or something fails."""
    transport = FastAPIWebsocketTransport(
        websocket,
        FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_in_sample_rate=IN_SAMPLE_RATE,
            audio_out_enabled=True,
            audio_out_sample_rate=OUT_SAMPLE_RATE,
            serializer=PCMSerializer(),
            session_timeout=settings.voice_max_session_seconds,
            allowed_origins=[],  # checked in main.py before the socket is accepted
        ),
    )

    stt, llm, tts = build_services(settings, context)
    llm_context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        llm_context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            UserCaptions(),
            user_aggregator,
            llm,
            BotCaptions(),
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=IN_SAMPLE_RATE, audio_out_sample_rate=OUT_SAMPLE_RATE
        ),
        enable_rtvi=False,  # the page uses our own small event format (serializer.py)
    )

    failed = False

    @worker.event_handler("on_pipeline_error")
    async def on_pipeline_error(worker, frame):
        # A service that can no longer work (e.g. a rejected API key) would leave the
        # visitor talking to silence. Apologise out loud, tell the page, and end.
        nonlocal failed
        processor = getattr(frame, "processor", None)
        if failed or processor is None or getattr(processor, "is_usable", True):
            return
        failed = True
        logger.error(f"Voice session ending: {processor} failed: {frame.error}")
        await worker.queue_frames(
            [
                TTSSpeakFrame(APOLOGY),
                OutputTransportMessageFrame(
                    message={EVENT_KEY: 1, "type": "error", "code": "assistant_failed"}
                ),
                EndFrame(),
            ]
        )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        await worker.queue_frames([TTSSpeakFrame(greeting(context))])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await worker.cancel()

    @transport.event_handler("on_session_timeout")
    async def on_session_timeout(transport, client):
        logger.info("Voice session reached its time limit")
        await worker.cancel()

    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    await runner.run()
