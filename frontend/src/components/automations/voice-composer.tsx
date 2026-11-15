"use client";

import { Mic, Sparkles, Square } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useSpeech } from "@/hooks/use-speech";
import { cn } from "@/lib/utils";

const LANGUAGES = [
  { code: "ar-JO", label: "العربية" },
  { code: "en-US", label: "English" },
];

const EXAMPLES = [
  "Convert all customers to an Excel sheet",
  "صدّر كل محادثات الواتساب المفتوحة على ملف إكسل",
  "Send customers who wrote this week a thank-you message",
  "Close all conversations with no reply for 30 days",
];

/** Say or type what you want automated. */
export function VoiceComposer({
  busy,
  onSubmit,
}: {
  busy: boolean;
  onSubmit: (request: string, language: string) => Promise<void>;
}) {
  const [language, setLanguage] = useState(LANGUAGES[0].code);
  const [text, setText] = useState("");
  const speech = useSpeech(language, (heard) => setText((current) => (current ? `${current} ${heard}` : heard)));

  const canSubmit = text.trim().length >= 3 && !busy;

  async function submit() {
    if (!canSubmit) return;
    speech.stop();
    await onSubmit(text.trim(), language);
    setText("");
  }

  return (
    <section className="rounded-2xl border bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">What should be automated?</h2>
          <p className="text-[12px] text-muted-foreground">
            Say it or type it. An AI crew builds the automation; actions wait for your approval.
          </p>
        </div>
        <div role="radiogroup" aria-label="Speech language" className="flex gap-1 rounded-lg bg-muted p-0.5">
          {LANGUAGES.map((option) => (
            <button
              key={option.code}
              type="button"
              role="radio"
              aria-checked={language === option.code}
              onClick={() => setLanguage(option.code)}
              disabled={speech.listening}
              className={cn(
                "h-6 rounded-md px-2.5 text-[12px] font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
                language === option.code ? "bg-background text-foreground shadow-xs" : "text-muted-foreground",
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 flex items-start gap-3">
        {speech.supported && (
          <button
            type="button"
            onClick={speech.listening ? speech.stop : speech.start}
            aria-pressed={speech.listening}
            aria-label={speech.listening ? "Stop listening" : "Start speaking"}
            className={cn(
              "relative flex size-12 shrink-0 items-center justify-center rounded-full outline-none transition-colors focus-visible:ring-3 focus-visible:ring-ring/50",
              speech.listening
                ? "bg-destructive text-white"
                : "bg-primary text-primary-foreground hover:bg-primary/85",
            )}
          >
            {speech.listening && (
              <span aria-hidden className="absolute inset-0 animate-ping rounded-full bg-destructive/40" />
            )}
            {speech.listening ? <Square className="relative size-4" /> : <Mic className="size-5" />}
          </button>
        )}

        <div className="min-w-0 flex-1">
          <label htmlFor="automation-request" className="sr-only">
            Automation request
          </label>
          <textarea
            id="automation-request"
            dir="auto"
            rows={3}
            value={text}
            onChange={(event) => setText(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                event.preventDefault();
                void submit();
              }
            }}
            placeholder={
              speech.supported
                ? "Press the microphone and speak, or type here…"
                : "Type your request… (voice needs Chrome or Edge)"
            }
            className="block w-full resize-none rounded-xl border bg-background px-3.5 py-2.5 text-sm leading-relaxed outline-none placeholder:text-muted-foreground/70 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40"
          />
          {speech.listening && (
            <p dir="auto" className="mt-1.5 min-h-5 text-[13px] text-muted-foreground">
              {speech.interim || "Listening…"}
            </p>
          )}
          {speech.error && <p className="mt-1.5 text-[12px] text-destructive">{speech.error}</p>}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              dir="auto"
              onClick={() => setText(example)}
              className="rounded-full border px-2.5 py-1 text-[12px] text-muted-foreground outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
            >
              {example}
            </button>
          ))}
        </div>
        <Button onClick={submit} disabled={!canSubmit}>
          <Sparkles />
          {busy ? "Sending to the crew" : "Build automation"}
        </Button>
      </div>
    </section>
  );
}
