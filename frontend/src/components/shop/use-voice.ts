"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { VoiceTicket } from "@/lib/types";

/**
 * A voice conversation with the shop's assistant over one WebSocket.
 *
 *   microphone -> 16 kHz PCM (public/voice/mic-worklet.js) -> voice service
 *   voice service -> 24 kHz PCM -> played here, plus JSON caption events
 *
 * While the assistant is talking the microphone is not sent, so the assistant
 * never hears itself through the speakers. "Stop" cuts it off and gives the
 * floor back to the visitor.
 */

/** Why a session could not start or ended badly. The page turns the code into words. */
class VoiceError extends Error {
  constructor(public code: string) {
    super(code);
  }
}

export type VoiceStatus = "idle" | "connecting" | "listening" | "speaking" | "ended" | "error";

export interface Caption {
  id: number;
  role: "user" | "bot";
  text: string;
}

const OUT_RATE = 24000;
const TAIL_SECONDS = 0.3; // wait this long after the last sound before listening again

export function useVoice() {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [captions, setCaptions] = useState<Caption[]>([]);
  const [level, setLevel] = useState(0);

  const ws = useRef<WebSocket | null>(null);
  const micStream = useRef<MediaStream | null>(null);
  const micContext = useRef<AudioContext | null>(null);
  const playContext = useRef<AudioContext | null>(null);
  const sources = useRef<AudioBufferSourceNode[]>([]);
  const playUntil = useRef(0);
  const speaking = useRef(false);
  const skipReply = useRef(false); // after "Stop", ignore the rest of that reply's audio
  const failed = useRef(false); // the service reported an error: keep showing it
  const captionId = useRef(0);
  const listenTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const addCaption = useCallback((role: Caption["role"], text: string) => {
    setCaptions((list) => [...list.slice(-11), { id: ++captionId.current, role, text }]);
  }, []);

  const appendBot = useCallback((text: string) => {
    setCaptions((list) => {
      const last = list[list.length - 1];
      if (!last || last.role !== "bot") return list;
      return [...list.slice(0, -1), { ...last, text: last.text + text }];
    });
  }, []);

  const stopPlayback = useCallback(() => {
    for (const source of sources.current) {
      try {
        source.stop();
      } catch {
        // already ended
      }
    }
    sources.current = [];
    playUntil.current = 0;
    speaking.current = false;
    if (listenTimer.current) clearTimeout(listenTimer.current);
  }, []);

  const teardown = useCallback(() => {
    stopPlayback();
    ws.current?.close();
    ws.current = null;
    micStream.current?.getTracks().forEach((track) => track.stop());
    micStream.current = null;
    void micContext.current?.close();
    micContext.current = null;
    void playContext.current?.close();
    playContext.current = null;
    setLevel(0);
  }, [stopPlayback]);

  useEffect(() => teardown, [teardown]);

  const play = useCallback((data: ArrayBuffer) => {
    const context = playContext.current;
    if (!context || skipReply.current || data.byteLength < 2) return;
    const pcm = new Int16Array(data, 0, Math.floor(data.byteLength / 2));
    const buffer = context.createBuffer(1, pcm.length, OUT_RATE);
    const samples = buffer.getChannelData(0);
    for (let i = 0; i < pcm.length; i++) samples[i] = pcm[i] / 0x8000;

    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);
    const startAt = Math.max(context.currentTime + 0.02, playUntil.current);
    source.start(startAt);
    playUntil.current = startAt + buffer.duration;
    sources.current.push(source);
    source.onended = () => {
      sources.current = sources.current.filter((s) => s !== source);
    };

    speaking.current = true;
    if (!failed.current) setStatus("speaking");
    if (listenTimer.current) clearTimeout(listenTimer.current);
    const waitMs = (playUntil.current - context.currentTime + TAIL_SECONDS) * 1000;
    listenTimer.current = setTimeout(() => {
      speaking.current = false;
      if (!failed.current && ws.current?.readyState === WebSocket.OPEN) setStatus("listening");
    }, waitMs);
  }, []);

  const onEvent = useCallback(
    (event: { type: string; text?: string; code?: string }) => {
      switch (event.type) {
        case "user-text":
          if (event.text) addCaption("user", event.text);
          break;
        case "bot-start":
          skipReply.current = false;
          addCaption("bot", "");
          break;
        case "bot-delta":
          if (event.text && !skipReply.current) appendBot(event.text);
          break;
        case "interrupted":
          stopPlayback();
          setStatus("listening");
          break;
        case "error":
          failed.current = true;
          setError(event.code ?? "failed");
          setStatus("error");
          break;
      }
    },
    [addCaption, appendBot, stopPlayback],
  );

  const start = useCallback(async () => {
    if (ws.current) return;
    setError(null);
    failed.current = false;
    setCaptions([]);
    setStatus("connecting");
    try {
      // Both audio contexts are created inside the click, as mobile browsers require.
      playContext.current = new AudioContext({ sampleRate: OUT_RATE });
      micContext.current = new AudioContext();

      const ticketResponse = await fetch("/api/shop/voice-ticket", { method: "POST" });
      const ticket = (await ticketResponse.json().catch(() => ({}))) as VoiceTicket & {
        error?: { code: string };
      };
      if (!ticketResponse.ok) throw new VoiceError(ticket.error?.code ?? "unavailable");

      micStream.current = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      await micContext.current.audioWorklet.addModule("/voice/mic-worklet.js");
      const input = micContext.current.createMediaStreamSource(micStream.current);
      const mic = new AudioWorkletNode(micContext.current, "nexus-mic");
      const silent = micContext.current.createGain();
      silent.gain.value = 0; // keeps the worklet running without playing the mic back
      input.connect(mic).connect(silent).connect(micContext.current.destination);

      const socket = new WebSocket(`${ticket.ws_url}?token=${encodeURIComponent(ticket.token)}`);
      socket.binaryType = "arraybuffer";
      ws.current = socket;

      mic.port.onmessage = (message: MessageEvent<{ pcm: ArrayBuffer; level: number }>) => {
        setLevel(speaking.current ? 0 : message.data.level);
        if (!speaking.current && socket.readyState === WebSocket.OPEN) socket.send(message.data.pcm);
      };
      socket.onopen = () => setStatus("listening");
      socket.onmessage = (message) => {
        if (message.data instanceof ArrayBuffer) play(message.data);
        else {
          try {
            onEvent(JSON.parse(message.data as string));
          } catch {
            // not one of our events
          }
        }
      };
      socket.onclose = () => {
        ws.current = null;
        // Let the last words (e.g. an apology before the service hangs up) finish playing.
        const context = playContext.current;
        const left = context ? Math.max(0, playUntil.current - context.currentTime) : 0;
        setTimeout(teardown, left * 1000 + 100);
        setStatus((current) => (current === "error" ? current : "ended"));
      };
      socket.onerror = () => {
        setError("connection_lost");
        setStatus("error");
      };
    } catch (problem) {
      teardown();
      const denied = problem instanceof DOMException && problem.name === "NotAllowedError";
      setError(denied ? "mic_denied" : problem instanceof VoiceError ? problem.code : "failed");
      setStatus("error");
    }
  }, [onEvent, play, teardown]);

  const stop = useCallback(() => {
    teardown();
    setStatus("ended");
  }, [teardown]);

  /** Cut the assistant off and listen to the visitor again. */
  const interrupt = useCallback(() => {
    skipReply.current = true;
    stopPlayback();
    if (ws.current?.readyState === WebSocket.OPEN) setStatus("listening");
  }, [stopPlayback]);

  return { status, error, captions, level, start, stop, interrupt };
}
