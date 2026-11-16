"use client";

import { Download, Pause, Play, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";

import { type AdStoryboard, drawFrame, HEIGHT, prepareFonts, WIDTH } from "./motion";

const FPS = 30;

/**
 * Renders the ad to an MP4 frame by frame with WebCodecs. Each frame is drawn at
 * its exact time, so the file is right even if the tab is in the background.
 * Returns null when this browser cannot encode H.264.
 */
async function encodeMp4(
  canvas: HTMLCanvasElement,
  paint: (t: number) => void,
  duration: number,
  onProgress: (t: number) => void,
) {
  const { BufferTarget, CanvasSource, canEncodeVideo, Mp4OutputFormat, Output, QUALITY_HIGH } =
    await import("mediabunny");
  if (typeof VideoEncoder === "undefined") return null;
  if (!(await canEncodeVideo("avc", { width: WIDTH, height: HEIGHT, quality: QUALITY_HIGH }))) return null;

  const output = new Output({ format: new Mp4OutputFormat({ fastStart: "in-memory" }), target: new BufferTarget() });
  const source = new CanvasSource(canvas, { codec: "avc", quality: QUALITY_HIGH, keyFrameInterval: 2 });
  output.addVideoTrack(source, { frameRate: FPS });
  await output.start();
  const frames = Math.round(duration * FPS);
  for (let i = 0; i < frames; i++) {
    const t = i / FPS;
    paint(t);
    await source.add(t, 1 / FPS);
    if (i % 6 === 0) onProgress(t);
  }
  await output.finalize();
  return new Blob([output.target.buffer!], { type: "video/mp4" });
}

/** Fallback for browsers without WebCodecs: record the canvas in real time. */
async function recordRealtime(
  canvas: HTMLCanvasElement,
  paint: (t: number) => void,
  duration: number,
  onProgress: (t: number) => void,
) {
  if (typeof MediaRecorder === "undefined") return null;
  const type = ["video/mp4", "video/webm;codecs=vp9", "video/webm"].find((t) => MediaRecorder.isTypeSupported(t));
  if (!type) return null;
  const stream = canvas.captureStream(FPS);
  const recorder = new MediaRecorder(stream, { mimeType: type, videoBitsPerSecond: 10_000_000 });
  const chunks: Blob[] = [];
  recorder.ondataavailable = (event) => {
    if (event.data.size) chunks.push(event.data);
  };
  const stopped = new Promise<void>((resolve) => (recorder.onstop = () => resolve()));
  paint(0);
  recorder.start(250);
  const begin = performance.now();
  await new Promise<void>((resolve) => {
    const tick = () => {
      const t = (performance.now() - begin) / 1000;
      paint(Math.min(t, duration));
      onProgress(Math.min(t, duration));
      if (t >= duration + 0.2) return resolve();
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
  recorder.stop();
  await stopped;
  stream.getTracks().forEach((track) => track.stop());
  return new Blob(chunks, { type: type.split(";")[0] });
}

/** Plays a storyboard on a canvas, lets you scrub it, and records it as a video file. */
export function AdPlayer({ storyboard, filename }: { storyboard: AdStoryboard; filename: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const frame = useRef<number | null>(null);
  const startedAt = useRef(0);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [recording, setRecording] = useState(false);
  const [ready, setReady] = useState(false);
  const duration = storyboard.duration;

  const paint = useCallback(
    (t: number) => {
      const ctx = canvas.current?.getContext("2d");
      if (ctx) drawFrame(ctx, storyboard, t);
    },
    [storyboard],
  );

  useEffect(() => {
    let cancelled = false;
    void prepareFonts().then(() => {
      if (cancelled) return;
      setReady(true);
      setPlaying(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // Draw the current frame whenever time or the storyboard changes while paused.
  useEffect(() => {
    if (ready && !playing) paint(time);
  }, [ready, playing, time, paint]);

  const stop = useCallback(() => {
    if (frame.current !== null) cancelAnimationFrame(frame.current);
    frame.current = null;
  }, []);

  useEffect(() => {
    if (!ready || !playing) return;
    startedAt.current = performance.now() - time * 1000;
    const tick = () => {
      const t = (performance.now() - startedAt.current) / 1000;
      if (t >= duration) {
        paint(duration);
        setTime(duration);
        setPlaying(false);
        return;
      }
      paint(t);
      setTime(t);
      frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return stop;
    // `time` is read once when playback starts; leaving it out is deliberate.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, playing, duration, paint, stop]);

  async function download() {
    const element = canvas.current;
    if (!element) return;
    stop();
    setPlaying(false);
    setRecording(true);
    try {
      const blob =
        (await encodeMp4(element, paint, duration, setTime)) ??
        (await recordRealtime(element, paint, duration, setTime));
      if (!blob) {
        toast.error("This browser cannot save video. Use Chrome, Edge or Safari.");
        return;
      }
      const extension = blob.type === "video/mp4" ? "mp4" : "webm";
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${filename}.${extension}`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
      toast.success(`Saved ${filename}.${extension}`);
    } catch {
      toast.error("Could not save the video. Try again.");
    } finally {
      setTime(duration);
      paint(duration);
      setRecording(false);
    }
  }

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative overflow-hidden rounded-2xl bg-black shadow-lg ring-1 ring-border">
        <canvas
          ref={canvas}
          width={WIDTH}
          height={HEIGHT}
          aria-label="Ad preview"
          className="block h-[min(70vh,640px)] w-auto"
          style={{ aspectRatio: `${WIDTH} / ${HEIGHT}` }}
        />
        {recording && (
          <span className="absolute left-3 top-3 flex items-center gap-1.5 rounded-full bg-black/70 px-2.5 py-1 text-[12px] font-medium text-white">
            <span className="size-2 animate-pulse rounded-full bg-red-500" />
            Saving video {Math.round((time / duration) * 100)}%
          </span>
        )}
      </div>

      <div className="flex w-full max-w-[360px] items-center gap-2">
        <Button
          size="icon-sm"
          variant="outline"
          aria-label={playing ? "Pause" : "Play"}
          disabled={recording || !ready}
          onClick={() => {
            if (!playing && time >= duration) setTime(0);
            setPlaying((value) => !value);
          }}
        >
          {playing ? <Pause /> : <Play />}
        </Button>
        <input
          type="range"
          aria-label="Position in the ad"
          min={0}
          max={duration}
          step={0.01}
          value={time}
          disabled={recording}
          onChange={(event) => {
            stop();
            setPlaying(false);
            setTime(Number(event.target.value));
          }}
          className="h-1.5 flex-1 accent-[var(--brand)]"
        />
        <span className="w-16 text-right text-[12px] tabular-nums text-muted-foreground">
          {time.toFixed(1)} / {duration.toFixed(1)}s
        </span>
      </div>

      <div className="flex gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={recording || !ready}
          onClick={() => {
            stop();
            setTime(0);
            setPlaying(true);
          }}
        >
          <RotateCcw />
          Replay
        </Button>
        <Button size="sm" onClick={download} disabled={recording || !ready}>
          <Download />
          {recording ? "Saving…" : "Download video"}
        </Button>
      </div>
    </div>
  );
}
