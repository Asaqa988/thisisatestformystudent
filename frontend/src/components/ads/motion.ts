// Motion-graphic ad renderer.
//
// drawFrame(ctx, storyboard, t) paints the ad as it looks at time t (seconds).
// It is a pure function of t, so playing, scrubbing and video export all show the
// same frames. Canvas size: 1080 x 1920 (9:16).

export const WIDTH = 1080;
export const HEIGHT = 1920;

export type SceneKind = "hook" | "feature" | "list" | "price" | "cta";

export interface AdScene {
  kind: SceneKind;
  duration: number;
  headline: string;
  subline: string;
  items: string[];
  price_amount: string;
  price_currency: string;
  price_period: string;
}

export interface AdStoryboard {
  palette: PaletteName;
  brand: string;
  scenes: AdScene[];
  facts_used: string[];
  duration: number;
}

export type PaletteName = "petrol" | "sunset" | "midnight" | "citrus" | "berry";

interface Palette {
  bg: [string, string];
  blobs: [string, string, string];
  text: string;
  muted: string;
  accent: string;
  onAccent: string;
  card: string;
}

export const PALETTES: Record<PaletteName, Palette> = {
  petrol: {
    bg: ["#0f3f4a", "#082229"],
    blobs: ["rgba(242,181,68,0.30)", "rgba(127,196,201,0.28)", "rgba(28,120,132,0.45)"],
    text: "#f7f4ee",
    muted: "rgba(247,244,238,0.72)",
    accent: "#f2b544",
    onAccent: "#13262b",
    card: "rgba(255,255,255,0.10)",
  },
  sunset: {
    bg: ["#ff7a45", "#b3134f"],
    blobs: ["rgba(255,224,102,0.45)", "rgba(255,90,140,0.40)", "rgba(120,20,90,0.40)"],
    text: "#ffffff",
    muted: "rgba(255,255,255,0.80)",
    accent: "#ffe066",
    onAccent: "#4a0d24",
    card: "rgba(255,255,255,0.16)",
  },
  midnight: {
    bg: ["#1d2045", "#07080f"],
    blobs: ["rgba(139,124,255,0.42)", "rgba(61,219,217,0.26)", "rgba(80,40,160,0.40)"],
    text: "#f2f2f7",
    muted: "rgba(242,242,247,0.70)",
    accent: "#9d8cff",
    onAccent: "#0b0c1a",
    card: "rgba(255,255,255,0.08)",
  },
  citrus: {
    bg: ["#fff36b", "#ffb238"],
    blobs: ["rgba(255,79,31,0.30)", "rgba(46,196,182,0.32)", "rgba(255,255,255,0.55)"],
    text: "#1b1a17",
    muted: "rgba(27,26,23,0.72)",
    accent: "#ff4f1f",
    onAccent: "#ffffff",
    card: "rgba(255,255,255,0.55)",
  },
  berry: {
    bg: ["#7b1fa2", "#d81b60"],
    blobs: ["rgba(0,229,195,0.32)", "rgba(255,179,230,0.40)", "rgba(60,10,90,0.45)"],
    text: "#ffffff",
    muted: "rgba(255,255,255,0.80)",
    accent: "#00e5c3",
    onAccent: "#2a0636",
    card: "rgba(255,255,255,0.14)",
  },
};

const WIPE = 0.5; // seconds the scene transition takes, centred on the cut
const MARGIN = 96;

// --- Easing -------------------------------------------------------------------------

const clamp = (v: number, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
const progress = (t: number, start: number, length: number) => clamp((t - start) / length);
const easeOutCubic = (x: number) => 1 - Math.pow(1 - x, 3);
const easeInOutCubic = (x: number) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
const easeOutBack = (x: number) => {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
};

// --- Timeline -----------------------------------------------------------------------

export function sceneAt(board: AdStoryboard, t: number) {
  let start = 0;
  for (let i = 0; i < board.scenes.length; i++) {
    const scene = board.scenes[i];
    if (t < start + scene.duration || i === board.scenes.length - 1) {
      return { index: i, scene, start, local: t - start };
    }
    start += scene.duration;
  }
  return { index: 0, scene: board.scenes[0], start: 0, local: t };
}

function cutTimes(board: AdStoryboard) {
  const cuts: number[] = [];
  let at = 0;
  for (const scene of board.scenes.slice(0, -1)) {
    at += scene.duration;
    cuts.push(at);
  }
  return cuts;
}

// --- Text ---------------------------------------------------------------------------

let fontFamily = "system-ui, sans-serif";

/** Use the page's font (Geist) once it has loaded. */
export async function prepareFonts() {
  if (typeof document === "undefined") return;
  const family = getComputedStyle(document.body).fontFamily;
  if (family) fontFamily = family;
  try {
    await Promise.all([
      document.fonts.load(`800 120px ${fontFamily}`),
      document.fonts.load(`500 48px ${fontFamily}`),
    ]);
  } catch {
    // Drawing still works with the fallback font.
  }
}

function font(weight: number, size: number) {
  return `${weight} ${Math.round(size)}px ${fontFamily}`;
}

function wrap(ctx: CanvasRenderingContext2D, text: string, maxWidth: number) {
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let line = "";
  for (const word of words) {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width > maxWidth && line) {
      lines.push(line);
      line = word;
    } else {
      line = test;
    }
  }
  if (line) lines.push(line);
  return lines;
}

/** The largest font size at which the text fits in maxLines lines. */
function fit(
  ctx: CanvasRenderingContext2D,
  text: string,
  { maxWidth, maxSize, minSize, maxLines, weight }: { maxWidth: number; maxSize: number; minSize: number; maxLines: number; weight: number },
) {
  for (let size = maxSize; size >= minSize; size -= 4) {
    ctx.font = font(weight, size);
    const lines = wrap(ctx, text, maxWidth);
    if (lines.length <= maxLines && lines.every((l) => ctx.measureText(l).width <= maxWidth)) {
      return { size, lines };
    }
  }
  ctx.font = font(weight, minSize);
  return { size: minSize, lines: wrap(ctx, text, maxWidth).slice(0, maxLines) };
}

// --- Background ---------------------------------------------------------------------

let grain: HTMLCanvasElement | null = null;

function grainPattern() {
  if (grain || typeof document === "undefined") return grain;
  grain = document.createElement("canvas");
  grain.width = grain.height = 256;
  const g = grain.getContext("2d")!;
  const image = g.createImageData(256, 256);
  let seed = 7;
  for (let i = 0; i < image.data.length; i += 4) {
    seed = (seed * 16807) % 2147483647; // deterministic noise
    const v = seed % 255;
    image.data[i] = image.data[i + 1] = image.data[i + 2] = v;
    image.data[i + 3] = 18;
  }
  g.putImageData(image, 0, 0);
  return grain;
}

function drawBackground(ctx: CanvasRenderingContext2D, p: Palette, t: number) {
  const gradient = ctx.createLinearGradient(0, 0, WIDTH * 0.4, HEIGHT);
  gradient.addColorStop(0, p.bg[0]);
  gradient.addColorStop(1, p.bg[1]);
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, WIDTH, HEIGHT);

  // Three soft light blobs drifting slowly.
  const blobs = [
    { x: 0.2 + 0.08 * Math.sin(t * 0.5), y: 0.18 + 0.05 * Math.cos(t * 0.4), r: 620, c: p.blobs[0] },
    { x: 0.85 + 0.06 * Math.cos(t * 0.35), y: 0.55 + 0.07 * Math.sin(t * 0.45), r: 700, c: p.blobs[1] },
    { x: 0.3 + 0.07 * Math.sin(t * 0.3 + 1), y: 0.92 + 0.04 * Math.cos(t * 0.5), r: 760, c: p.blobs[2] },
  ];
  for (const b of blobs) {
    const g = ctx.createRadialGradient(b.x * WIDTH, b.y * HEIGHT, 0, b.x * WIDTH, b.y * HEIGHT, b.r);
    g.addColorStop(0, b.c);
    g.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, WIDTH, HEIGHT);
  }

  const pattern = grainPattern();
  if (pattern) {
    const fill = ctx.createPattern(pattern, "repeat");
    if (fill) {
      ctx.save();
      ctx.translate((t * 37) % 256, (t * 53) % 256); // moving grain, like film
      ctx.fillStyle = fill;
      ctx.fillRect(-256, -256, WIDTH + 512, HEIGHT + 512);
      ctx.restore();
    }
  }
}

/** A tilted band near the bottom with the brand name scrolling across, like a news ticker. */
function drawTicker(ctx: CanvasRenderingContext2D, board: AdStoryboard, p: Palette, t: number) {
  const label = (board.brand || board.scenes[0]?.headline || "").toUpperCase();
  if (!label) return;
  const enter = easeOutCubic(progress(t, 0.3, 0.7));
  const y = HEIGHT * 0.86 + (1 - enter) * 300;
  ctx.save();
  ctx.translate(WIDTH / 2, y);
  ctx.rotate(-0.06);
  ctx.fillStyle = p.accent;
  ctx.fillRect(-WIDTH, -56, WIDTH * 2, 112);
  ctx.font = font(800, 52);
  ctx.textBaseline = "middle";
  ctx.textAlign = "left";
  ctx.fillStyle = p.onAccent;
  const unit = `${label}  ✦  `;
  const unitWidth = ctx.measureText(unit).width;
  const offset = (t * 140) % unitWidth;
  for (let x = -WIDTH - offset; x < WIDTH; x += unitWidth) ctx.fillText(unit, x, 4);
  ctx.restore();
}

function drawChrome(ctx: CanvasRenderingContext2D, board: AdStoryboard, p: Palette, t: number) {
  // Brand, top left.
  if (board.brand) {
    ctx.fillStyle = p.accent;
    ctx.beginPath();
    ctx.arc(MARGIN + 10, 150, 10, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = p.text;
    ctx.font = font(700, 34);
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(board.brand.toUpperCase(), MARGIN + 36, 152);
  }
  // One thin progress segment per scene.
  const gap = 12;
  const total = board.scenes.length;
  const segment = (WIDTH - MARGIN * 2 - gap * (total - 1)) / total;
  let start = 0;
  board.scenes.forEach((scene, i) => {
    const x = MARGIN + i * (segment + gap);
    ctx.fillStyle = p.card;
    roundRect(ctx, x, 84, segment, 8, 4);
    ctx.fill();
    const filled = clamp((t - start) / scene.duration);
    if (filled > 0) {
      ctx.fillStyle = p.text;
      roundRect(ctx, x, 84, segment * filled, 8, 4);
      ctx.fill();
    }
    start += scene.duration;
  });
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  const radius = Math.min(r, h / 2, w / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + w, y, x + w, y + h, radius);
  ctx.arcTo(x + w, y + h, x, y + h, radius);
  ctx.arcTo(x, y + h, x, y, radius);
  ctx.arcTo(x, y, x + w, y, radius);
  ctx.closePath();
}

// --- Scenes -------------------------------------------------------------------------

type SceneDraw = (ctx: CanvasRenderingContext2D, s: AdScene, p: Palette, u: number) => void;

/** Words pop in one after another, an accent bar grows under the line. */
const hook: SceneDraw = (ctx, s, p, u) => {
  const { size, lines } = fit(ctx, s.headline, { maxWidth: WIDTH - MARGIN * 2, maxSize: 168, minSize: 84, maxLines: 4, weight: 800 });
  const lineHeight = size * 1.05;
  const blockHeight = lines.length * lineHeight;
  const top = HEIGHT * 0.44 - blockHeight / 2;

  // A ring behind the words, breathing.
  const ring = easeOutCubic(progress(u, 0, 0.8));
  ctx.strokeStyle = p.accent;
  ctx.globalAlpha = 0.35 * ring;
  ctx.lineWidth = 6;
  ctx.beginPath();
  ctx.arc(WIDTH * 0.78, top - 40, 120 * ring + 8 * Math.sin(u * 3), 0, Math.PI * 2);
  ctx.stroke();
  ctx.globalAlpha = 1;

  ctx.font = font(800, size);
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  let wordIndex = 0;
  lines.forEach((line, row) => {
    let x = MARGIN;
    for (const word of line.split(" ")) {
      const k = easeOutBack(progress(u, 0.1 + wordIndex * 0.11, 0.45));
      const a = progress(u, 0.1 + wordIndex * 0.11, 0.25);
      const width = ctx.measureText(word + " ").width;
      ctx.save();
      ctx.globalAlpha = a;
      ctx.translate(x, top + row * lineHeight + (1 - k) * 70);
      ctx.fillStyle = p.text;
      ctx.fillText(word, 0, 0);
      ctx.restore();
      x += width;
      wordIndex++;
    }
  });

  const bar = easeInOutCubic(progress(u, 0.25 + wordIndex * 0.11, 0.5));
  ctx.fillStyle = p.accent;
  roundRect(ctx, MARGIN, top + blockHeight + 28, 340 * bar, 18, 9);
  ctx.fill();

  if (s.subline) drawSubline(ctx, s.subline, p, top + blockHeight + 90, progress(u, 0.6 + wordIndex * 0.08, 0.5));
};

/** A check mark draws itself, then the benefit rises from behind a mask. */
const feature: SceneDraw = (ctx, s, p, u) => {
  const cx = MARGIN + 110;
  const cy = HEIGHT * 0.32;
  const pop = easeOutBack(progress(u, 0, 0.5));
  ctx.fillStyle = p.accent;
  ctx.beginPath();
  ctx.arc(cx, cy, 110 * pop, 0, Math.PI * 2);
  ctx.fill();

  const draw = easeInOutCubic(progress(u, 0.3, 0.45));
  if (draw > 0) {
    ctx.strokeStyle = p.onAccent;
    ctx.lineWidth = 22;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    const points = [
      [cx - 48, cy + 2],
      [cx - 12, cy + 40],
      [cx + 52, cy - 36],
    ];
    const first = Math.min(draw / 0.4, 1);
    const second = clamp((draw - 0.4) / 0.6);
    ctx.beginPath();
    ctx.moveTo(points[0][0], points[0][1]);
    ctx.lineTo(points[0][0] + (points[1][0] - points[0][0]) * first, points[0][1] + (points[1][1] - points[0][1]) * first);
    if (second > 0) ctx.lineTo(points[1][0] + (points[2][0] - points[1][0]) * second, points[1][1] + (points[2][1] - points[1][1]) * second);
    ctx.stroke();
  }

  const { size, lines } = fit(ctx, s.headline, { maxWidth: WIDTH - MARGIN * 2, maxSize: 132, minSize: 72, maxLines: 4, weight: 800 });
  const top = cy + 210;
  drawMaskedLines(ctx, lines, size, p.text, top, progress(u, 0.35, 0.6));
  if (s.subline) drawSubline(ctx, s.subline, p, top + lines.length * size * 1.08 + 40, progress(u, 0.8, 0.5));
};

/** Headline, then up to three cards slide in from the right. */
const list: SceneDraw = (ctx, s, p, u) => {
  const { size, lines } = fit(ctx, s.headline || "", { maxWidth: WIDTH - MARGIN * 2, maxSize: 112, minSize: 64, maxLines: 3, weight: 800 });
  const top = HEIGHT * 0.22;
  drawMaskedLines(ctx, lines, size, p.text, top, progress(u, 0, 0.5));

  const cardTop = top + lines.length * size * 1.08 + 70;
  s.items.forEach((item, i) => {
    const k = easeOutCubic(progress(u, 0.35 + i * 0.22, 0.5));
    const y = cardTop + i * 200;
    const x = MARGIN + (1 - k) * 420;
    ctx.globalAlpha = k;
    ctx.fillStyle = p.card;
    roundRect(ctx, x, y, WIDTH - MARGIN * 2, 168, 40);
    ctx.fill();
    ctx.fillStyle = p.accent;
    ctx.beginPath();
    ctx.arc(x + 84, y + 84, 40, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = p.onAccent;
    ctx.lineWidth = 10;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(x + 66, y + 85);
    ctx.lineTo(x + 79, y + 98);
    ctx.lineTo(x + 103, y + 71);
    ctx.stroke();
    const itemFit = fit(ctx, item, { maxWidth: WIDTH - MARGIN * 2 - 190, maxSize: 64, minSize: 40, maxLines: 1, weight: 700 });
    ctx.font = font(700, itemFit.size);
    ctx.fillStyle = p.text;
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(itemFit.lines[0] ?? item, x + 156, y + 86);
    ctx.globalAlpha = 1;
  });

  if (s.subline) drawSubline(ctx, s.subline, p, cardTop + s.items.length * 200 + 30, progress(u, 0.9, 0.5));
};

/** The number counts up, with rays turning behind it. */
const price: SceneDraw = (ctx, s, p, u) => {
  const cx = WIDTH / 2;
  const cy = HEIGHT * 0.47;
  const appear = easeOutCubic(progress(u, 0, 0.5));

  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(u * 0.25);
  ctx.globalAlpha = 0.18 * appear;
  ctx.fillStyle = p.accent;
  for (let i = 0; i < 12; i++) {
    ctx.rotate((Math.PI * 2) / 12);
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(-60, -720);
    ctx.lineTo(60, -720);
    ctx.closePath();
    ctx.fill();
  }
  ctx.restore();
  ctx.globalAlpha = 1;

  ctx.textAlign = "center";
  ctx.textBaseline = "alphabetic";
  ctx.globalAlpha = appear;
  ctx.fillStyle = p.muted;
  ctx.font = font(600, 58);
  ctx.fillText(s.headline || "Starting at", cx, cy - 260);
  ctx.globalAlpha = 1;

  const target = parseFloat(s.price_amount.replace(",", ".")) || 0;
  const counted = target * easeOutCubic(progress(u, 0.15, 1.0));
  const shown = target >= 100 ? Math.round(counted).toLocaleString("en-US") : counted.toFixed(target % 1 ? 2 : 0);
  const pop = 1 + 0.06 * Math.sin(Math.PI * progress(u, 1.1, 0.35));
  // The amount and the currency are centred together, so the currency never leaves the frame.
  ctx.font = font(800, 72);
  const currencyWidth = s.price_currency ? ctx.measureText(s.price_currency).width + 18 : 0;
  // Size the amount for its final value so it does not grow while counting.
  const finalText = target >= 100 ? Math.round(target).toLocaleString("en-US") : target.toFixed(target % 1 ? 2 : 0);
  const amountFit = fit(ctx, finalText, { maxWidth: WIDTH - 2 * MARGIN - currencyWidth, maxSize: 320, minSize: 140, maxLines: 1, weight: 900 });
  ctx.font = font(900, amountFit.size);
  const finalWidth = ctx.measureText(finalText).width;
  const left = -(finalWidth + currencyWidth) / 2;
  ctx.save();
  ctx.translate(cx, cy + 60);
  ctx.scale(pop, pop);
  ctx.fillStyle = p.accent;
  ctx.textAlign = "right";
  ctx.fillText(shown, left + finalWidth, 0);
  if (s.price_currency) {
    ctx.font = font(800, 72);
    ctx.fillStyle = p.text;
    ctx.textAlign = "left";
    ctx.fillText(s.price_currency, left + finalWidth + 18, -amountFit.size * 0.45);
  }
  ctx.restore();

  ctx.textAlign = "center";
  ctx.globalAlpha = progress(u, 0.9, 0.4);
  ctx.fillStyle = p.text;
  ctx.font = font(700, 64);
  if (s.price_period) ctx.fillText(s.price_period, cx, cy + 170);
  ctx.globalAlpha = 1;
  if (s.subline) drawSubline(ctx, s.subline, p, cy + 260, progress(u, 1.2, 0.5), "center");
};

/** The call to action: a pulsing button with tap ripples. */
const cta: SceneDraw = (ctx, s, p, u) => {
  const cx = WIDTH / 2;
  const cy = HEIGHT * 0.5;

  if (s.subline) {
    const sub = fit(ctx, s.subline, { maxWidth: WIDTH - MARGIN * 2, maxSize: 72, minSize: 46, maxLines: 3, weight: 700 });
    ctx.font = font(700, sub.size);
    ctx.fillStyle = p.text;
    ctx.textAlign = "center";
    ctx.textBaseline = "alphabetic";
    ctx.globalAlpha = progress(u, 0, 0.4);
    sub.lines.forEach((line, i) => ctx.fillText(line, cx, cy - 260 + i * sub.size * 1.15 - (sub.lines.length - 1) * sub.size * 1.15));
    ctx.globalAlpha = 1;
  }

  const label = fit(ctx, s.headline || "Message us", { maxWidth: WIDTH - MARGIN * 2 - 160, maxSize: 76, minSize: 48, maxLines: 1, weight: 800 });
  ctx.font = font(800, label.size);
  const text = label.lines[0] ?? s.headline;
  const buttonWidth = Math.min(WIDTH - MARGIN * 2, ctx.measureText(text).width + 160);
  const buttonHeight = 170;
  const enter = easeOutBack(progress(u, 0.2, 0.55));
  const pulse = 1 + 0.035 * Math.sin(Math.max(0, u - 0.8) * 6);

  // Ripples, as if someone tapped the button.
  for (let i = 0; i < 3; i++) {
    const r = ((u - 0.9 - i * 0.45) % 1.35) / 1.35;
    if (u < 0.9 + i * 0.45 || r < 0) continue;
    ctx.strokeStyle = p.accent;
    ctx.globalAlpha = 0.5 * (1 - r);
    ctx.lineWidth = 6;
    roundRect(ctx, cx - buttonWidth / 2 - r * 60, cy - buttonHeight / 2 - r * 60, buttonWidth + r * 120, buttonHeight + r * 120, 85 + r * 60);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;

  ctx.save();
  ctx.translate(cx, cy);
  ctx.scale(enter * pulse, enter * pulse);
  ctx.fillStyle = p.accent;
  roundRect(ctx, -buttonWidth / 2, -buttonHeight / 2, buttonWidth, buttonHeight, 85);
  ctx.fill();
  ctx.fillStyle = p.onAccent;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.font = font(800, label.size);
  ctx.fillText(text, 0, 4);
  ctx.restore();

  // A small arrow pointing at the button.
  const bob = Math.sin(u * 5) * 14;
  ctx.globalAlpha = progress(u, 0.8, 0.4);
  ctx.strokeStyle = p.text;
  ctx.lineWidth = 12;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(cx, cy + 210 + bob + 90);
  ctx.lineTo(cx, cy + 210 + bob);
  ctx.moveTo(cx - 36, cy + 210 + bob + 36);
  ctx.lineTo(cx, cy + 210 + bob);
  ctx.lineTo(cx + 36, cy + 210 + bob + 36);
  ctx.stroke();
  ctx.globalAlpha = 1;
};

const SCENES: Record<SceneKind, SceneDraw> = { hook, feature, list, price, cta };

function drawMaskedLines(ctx: CanvasRenderingContext2D, lines: string[], size: number, color: string, top: number, k: number) {
  const lineHeight = size * 1.08;
  ctx.font = font(800, size);
  ctx.fillStyle = color;
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  lines.forEach((line, i) => {
    const local = easeOutCubic(clamp(k * 1.4 - i * 0.18));
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, top + i * lineHeight - 10, WIDTH, lineHeight + 10);
    ctx.clip();
    ctx.fillText(line, MARGIN, top + i * lineHeight + (1 - local) * lineHeight);
    ctx.restore();
  });
}

function drawSubline(ctx: CanvasRenderingContext2D, text: string, p: Palette, top: number, k: number, align: "left" | "center" = "left") {
  const { size, lines } = fit(ctx, text, { maxWidth: WIDTH - MARGIN * 2, maxSize: 56, minSize: 38, maxLines: 3, weight: 500 });
  const e = easeOutCubic(k);
  ctx.globalAlpha = e;
  ctx.font = font(500, size);
  ctx.fillStyle = p.muted;
  ctx.textAlign = align;
  ctx.textBaseline = "top";
  lines.forEach((line, i) => ctx.fillText(line, align === "center" ? WIDTH / 2 : MARGIN, top + i * size * 1.3 + (1 - e) * 30));
  ctx.globalAlpha = 1;
}

/** A diagonal accent panel sweeps across the screen at each cut. */
function drawWipe(ctx: CanvasRenderingContext2D, p: Palette, board: AdStoryboard, t: number) {
  for (const cut of cutTimes(board)) {
    const k = (t - (cut - WIPE / 2)) / WIPE;
    if (k <= 0 || k >= 1) continue;
    const x = -WIDTH * 1.4 + easeInOutCubic(k) * WIDTH * 2.8;
    ctx.save();
    ctx.translate(x, 0);
    ctx.transform(1, 0, -0.35, 1, 0, 0);
    ctx.fillStyle = p.accent;
    ctx.fillRect(0, -100, WIDTH * 1.2, HEIGHT + 200);
    ctx.fillStyle = p.text;
    ctx.globalAlpha = 0.25;
    ctx.fillRect(WIDTH * 1.2, -100, 60, HEIGHT + 200);
    ctx.restore();
  }
}

// --- The frame ----------------------------------------------------------------------

export function drawFrame(ctx: CanvasRenderingContext2D, board: AdStoryboard, t: number) {
  const p = PALETTES[board.palette] ?? PALETTES.petrol;
  const time = clamp(t, 0, board.duration);
  ctx.save();
  ctx.clearRect(0, 0, WIDTH, HEIGHT);
  drawBackground(ctx, p, time);

  const { scene, local } = sceneAt(board, time);
  SCENES[scene.kind]?.(ctx, scene, p, local);

  drawTicker(ctx, board, p, time);
  drawChrome(ctx, board, p, time);
  drawWipe(ctx, p, board, time);
  ctx.restore();
}
