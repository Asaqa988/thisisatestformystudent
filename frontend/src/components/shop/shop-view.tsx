"use client";

import { Loader2, Mic, MicOff, Package, PhoneOff, Square } from "lucide-react";
import { useEffect, useRef } from "react";
import useSWR from "swr";

import { Skeleton } from "@/components/ui/skeleton";
import type { Product, ShopData } from "@/lib/types";
import { cn } from "@/lib/utils";

import { type Caption, useVoice, type VoiceStatus } from "./use-voice";

async function getShop(): Promise<ShopData> {
  const response = await fetch("/api/shop/shop");
  if (!response.ok) throw new Error("shop unavailable");
  return response.json();
}

const STATUS_TEXT: Record<VoiceStatus, string> = {
  idle: "اضغط على المايك واسألني عن أي منتج",
  connecting: "عم نتصل بالمساعد…",
  listening: "عم بسمعك… احكي",
  speaking: "المساعد عم يحكي",
  ended: "انتهت المحادثة. اضغط على المايك لتبدأ من جديد",
  error: "",
};

const ERROR_TEXT: Record<string, string> = {
  mic_denied: "اسمح للمتصفح باستخدام المايك حتى تقدر تحكي مع المساعد.",
  not_configured: "المساعد الصوتي غير متاح حاليًا.",
  integration_not_configured: "المساعد الصوتي غير متاح حاليًا.",
  busy: "المساعد مشغول هلأ. جرّب بعد دقيقة.",
  too_many: "وصلت للحد المسموح حاليًا. جرّب لاحقًا.",
  expired: "انتهت صلاحية الجلسة. اضغط مرة ثانية.",
  bad_ticket: "ما قدرنا نبدأ الجلسة. اضغط مرة ثانية.",
  ticket_used: "ما قدرنا نبدأ الجلسة. اضغط مرة ثانية.",
  unavailable: "المساعد ما قدر يوصل للمتجر هلأ. جرّب بعد شوي.",
  connection_lost: "انقطع الاتصال بالمساعد.",
  assistant_failed: "المساعد ما قدر يجاوب بسبب مشكلة تقنية. جرّب بعد شوي.",
  failed: "صار خطأ وما قدر المساعد يبدأ. جرّب مرة ثانية.",
};

export function priceLabel(product: Pick<Product, "price" | "currency">) {
  if (product.price === null) return null;
  const amount = Number(product.price);
  const currency = product.currency === "JOD" ? "دينار" : product.currency;
  return `${amount.toLocaleString("ar-JO", { maximumFractionDigits: 2 })} ${currency}`;
}

export function ShopView() {
  const shop = useSWR<ShopData>("shop", getShop, { revalidateOnFocus: false });
  const voice = useVoice();
  const name = shop.data?.business_name?.trim() || "متجرنا";
  const voiceEnabled = shop.data?.voice_enabled ?? false;

  return (
    <div className="min-h-dvh pb-48">
      <header className="border-b bg-card/60">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 sm:px-6 md:flex-row md:items-center md:justify-between md:py-14">
          <div className="max-w-xl">
            <p className="text-sm font-medium text-brand">{name}</p>
            <h1 className="mt-2 text-3xl font-bold leading-tight sm:text-4xl">
              اسأل عن أي منتج… بصوتك
            </h1>
            <p className="mt-3 text-base leading-relaxed text-muted-foreground">
              تصفّح منتجاتنا، واضغط على المايك واسأل مساعدنا الصوتي عن الأسعار والمواصفات. بيجاوبك فورًا
              بالعربي.
            </p>
          </div>
          {voiceEnabled && (
            <button
              type="button"
              onClick={() => void voice.start()}
              disabled={voice.status === "connecting" || voice.status === "listening" || voice.status === "speaking"}
              className="flex items-center gap-3 self-start rounded-full bg-brand px-6 py-3.5 text-base font-semibold text-white shadow-lg transition hover:opacity-90 disabled:opacity-60 md:self-center"
            >
              <Mic className="size-5" />
              احكي مع المساعد
            </button>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        {shop.error ? (
          <p className="rounded-xl border bg-card p-6 text-center text-muted-foreground">
            المتجر غير متاح حاليًا. جرّب بعد شوي.
          </p>
        ) : shop.isLoading ? (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-80 w-full rounded-2xl" />
            ))}
          </div>
        ) : (shop.data?.products.length ?? 0) === 0 ? (
          <p className="rounded-xl border bg-card p-10 text-center text-muted-foreground">
            ما في منتجات معروضة حاليًا.
          </p>
        ) : (
          <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {shop.data!.products.map((product) => (
              <ProductCard key={product.id} product={product} />
            ))}
          </ul>
        )}
      </main>

      {voiceEnabled && <VoiceDock voice={voice} />}
    </div>
  );
}

function ProductCard({ product }: { product: Product }) {
  const price = priceLabel(product);
  return (
    <li className="flex flex-col overflow-hidden rounded-2xl border bg-card shadow-sm">
      <div className="flex aspect-[4/3] items-center justify-center bg-muted">
        {product.image_path ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={product.image_path.replace("/api/v1/public/", "/api/shop/")}
            alt={product.name}
            loading="lazy"
            className="size-full object-cover"
          />
        ) : (
          <Package className="size-10 text-muted-foreground" strokeWidth={1.25} />
        )}
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        {product.category && <p className="text-xs font-medium text-brand">{product.category}</p>}
        <h2 dir="auto" className="text-lg font-semibold leading-snug">
          {product.name}
        </h2>
        {product.description && (
          <p dir="auto" className="line-clamp-3 text-sm leading-relaxed text-muted-foreground">
            {product.description}
          </p>
        )}
        {price && <p className="mt-auto pt-2 text-lg font-bold text-foreground">{price}</p>}
      </div>
    </li>
  );
}

function VoiceDock({ voice }: { voice: ReturnType<typeof useVoice> }) {
  const live = voice.status === "listening" || voice.status === "speaking" || voice.status === "connecting";
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [voice.captions]);

  const message =
    voice.status === "error" ? (ERROR_TEXT[voice.error ?? "failed"] ?? ERROR_TEXT.failed) : STATUS_TEXT[voice.status];

  return (
    <div className="fixed inset-x-0 bottom-0 z-20 px-3 pb-3 sm:px-6 sm:pb-6">
      <section
        aria-label="المساعد الصوتي"
        className="mx-auto max-w-2xl overflow-hidden rounded-3xl border bg-card/95 shadow-2xl backdrop-blur"
      >
        {voice.captions.length > 0 && (
          <div ref={scroller} className="scroll-quiet max-h-44 space-y-2 overflow-y-auto border-b px-4 py-3">
            {voice.captions.map((caption) => (
              <CaptionLine key={caption.id} caption={caption} />
            ))}
          </div>
        )}
        <div className="flex items-center gap-3 p-3">
          <MicButton status={voice.status} level={voice.level} onStart={() => void voice.start()} />
          <p
            role="status"
            aria-live="polite"
            className={cn("min-w-0 flex-1 text-sm", voice.status === "error" ? "text-destructive" : "text-muted-foreground")}
          >
            {message}
          </p>
          {voice.status === "speaking" && (
            <button
              type="button"
              onClick={voice.interrupt}
              className="flex items-center gap-1.5 rounded-full border px-3 py-2 text-sm font-medium hover:bg-muted"
            >
              <Square className="size-3.5" />
              وقّف
            </button>
          )}
          {live && (
            <button
              type="button"
              onClick={voice.stop}
              aria-label="إنهاء المحادثة"
              className="flex size-10 items-center justify-center rounded-full bg-destructive/10 text-destructive hover:bg-destructive/15"
            >
              <PhoneOff className="size-4" />
            </button>
          )}
        </div>
      </section>
    </div>
  );
}

function MicButton({ status, level, onStart }: { status: VoiceStatus; level: number; onStart: () => void }) {
  const idle = status === "idle" || status === "ended" || status === "error";
  const ring = status === "listening" ? Math.min(1, level * 8) : 0;
  return (
    <button
      type="button"
      onClick={idle ? onStart : undefined}
      aria-label={idle ? "ابدأ المحادثة" : "المايك شغّال"}
      disabled={!idle}
      className={cn(
        "relative flex size-12 shrink-0 items-center justify-center rounded-full text-white transition",
        status === "speaking" ? "bg-foreground/80" : "bg-brand",
        idle && "hover:opacity-90",
      )}
      style={{ boxShadow: ring ? `0 0 0 ${4 + ring * 10}px color-mix(in oklch, var(--brand) 25%, transparent)` : undefined }}
    >
      {status === "connecting" ? (
        <Loader2 className="size-5 animate-spin" />
      ) : status === "speaking" ? (
        <MicOff className="size-5" />
      ) : (
        <Mic className="size-5" />
      )}
    </button>
  );
}

function CaptionLine({ caption }: { caption: Caption }) {
  if (!caption.text.trim()) return null;
  return (
    <p
      dir="auto"
      className={cn(
        "w-fit max-w-[90%] rounded-2xl px-3 py-1.5 text-sm leading-relaxed",
        caption.role === "user" ? "ms-auto bg-muted" : "bg-brand-soft text-foreground",
      )}
    >
      {caption.text}
    </p>
  );
}
