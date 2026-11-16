# Ad videos (Campaigns page)

NEXUS makes 15-second, 9:16 motion-graphic video ads from the Knowledge Base.

## How it works

1. On **Campaigns**, the user optionally says what the ad should focus on and presses **Create ad video**.
2. `POST /api/v1/ad-videos` saves the ad as `building` and starts a background task
   (`app/services/ad_videos.py`).
3. One Claude call (`ANTHROPIC_API_KEY`, `AI_MODEL`) reads the Knowledge Base and returns a
   structured storyboard (JSON schema output): a title, a colour palette, the brand name, 4 to 6
   scenes and the Knowledge Base facts it used. The prompt forbids facts that are not in the
   Knowledge Base.
4. `tidy()` makes the storyboard safe to animate: at most 6 scenes, each 1.8 to 4.5 s, the whole ad
   between 9 and 15 s, short text, prices as digits only.
5. The browser draws the ad on a 1080 x 1920 canvas (`frontend/src/components/ads/motion.ts`).
   `drawFrame(ctx, storyboard, t)` is a pure function of time, so playback, scrubbing and export show
   the same frames.
6. **Download video** encodes the frames one by one to H.264 MP4 with WebCodecs
   ([mediabunny](https://mediabunny.dev)), so the file is exact even when the tab is in the background.
   Browsers without WebCodecs fall back to recording the canvas in real time.

No video is stored on the server: only the storyboard (a few KB of JSON in `ad_videos.storyboard`).

## Scenes

| Kind      | What it shows                                                        |
|-----------|----------------------------------------------------------------------|
| `hook`    | The headline pops in word by word, an accent bar grows under it      |
| `feature` | A check mark draws itself, the benefit rises from behind a mask      |
| `list`    | Two or three cards slide in with ticks                               |
| `price`   | The price counts up over turning rays, the currency beside it        |
| `cta`     | A pulsing button with tap ripples and an arrow                       |

Between scenes a diagonal accent panel wipes across. A brand ticker scrolls along the bottom and a
progress bar per scene runs along the top. Palettes: `petrol`, `sunset`, `midnight`, `citrus`, `berry`.

## API

| Method | Path                      | Notes                                                    |
|--------|---------------------------|----------------------------------------------------------|
| POST   | `/api/v1/ad-videos`       | `{ "brief": "optional focus" }` → 202, status `building`  |
| GET    | `/api/v1/ad-videos`       | Newest first                                             |
| GET    | `/api/v1/ad-videos/{id}`  | Poll until `status` is `ready` or `failed`               |
| DELETE | `/api/v1/ad-videos/{id}`  | 204                                                      |

A failed ad keeps a readable `error`: no API key, empty Knowledge Base, rate limit, refusal.

## Cost

One Claude call per ad: the Knowledge Base as input (cached) and about 1 to 2 thousand output
tokens. With a small Knowledge Base that is a few US cents per ad. Playing and downloading cost
nothing.
