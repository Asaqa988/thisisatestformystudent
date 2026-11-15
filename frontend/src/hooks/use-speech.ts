"use client";

// Speech to text with the browser's built-in recognizer (Web Speech API).
// Works in Chrome and Edge, needs no API key and costs nothing. Firefox and
// some others do not have it; the page then offers typing only.

import { useCallback, useEffect, useRef, useState } from "react";

interface RecognitionResult {
  isFinal: boolean;
  0: { transcript: string };
}

interface RecognitionEvent {
  resultIndex: number;
  results: ArrayLike<RecognitionResult>;
}

interface Recognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: RecognitionEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

type RecognitionConstructor = new () => Recognition;

function recognitionClass(): RecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: RecognitionConstructor;
    webkitSpeechRecognition?: RecognitionConstructor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

const ERRORS: Record<string, string> = {
  "not-allowed": "Microphone access was blocked. Allow it in the browser's address bar and try again.",
  "no-speech": "No speech was heard. Try again a little closer to the microphone.",
  "audio-capture": "No microphone was found.",
  network: "The browser's speech service could not be reached.",
};

export function useSpeech(language: string, onText: (text: string) => void) {
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recognition = useRef<Recognition | null>(null);
  const onTextRef = useRef(onText);

  useEffect(() => {
    onTextRef.current = onText;
  }, [onText]);

  useEffect(() => {
    // Feature detection must run in the browser, after the first render.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSupported(recognitionClass() !== null);
    return () => recognition.current?.abort();
  }, []);

  const start = useCallback(() => {
    const Klass = recognitionClass();
    if (!Klass) return;
    recognition.current?.abort();

    const r = new Klass();
    r.lang = language;
    r.continuous = true;
    r.interimResults = true;
    r.onresult = (event) => {
      let finalText = "";
      let interimText = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) finalText += result[0].transcript;
        else interimText += result[0].transcript;
      }
      if (finalText.trim()) onTextRef.current(finalText.trim());
      setInterim(interimText);
    };
    r.onerror = (event) => {
      if (event.error !== "aborted") setError(ERRORS[event.error] ?? `Speech recognition failed (${event.error}).`);
    };
    r.onend = () => {
      setListening(false);
      setInterim("");
    };

    setError(null);
    setListening(true);
    recognition.current = r;
    r.start();
  }, [language]);

  const stop = useCallback(() => recognition.current?.stop(), []);

  return { supported, listening, interim, error, start, stop };
}
