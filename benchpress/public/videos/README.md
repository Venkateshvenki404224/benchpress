# Hero film

The landing page picks these up on the next request — no code change:

| File | What the page does |
|---|---|
| _neither_ | Renders the static endcard (wordmark, tagline, repo URL) inside the 16:9 frame. |
| `hero-poster.jpg` | Renders the poster frame as an image. |
| `hero.mp4` | Renders `<video autoplay muted loop playsinline>`, using the poster if it is there too. |

The detection lives in `benchpress/www/home.py:hero_media`.

## What the film is

Live footage of the real product, not a mockup. It is a 22 s recut of the demo film: the
Templates page, one click on Deploy, the eleven-step pipeline running at ×24, "Deploy complete —
1 m 43 s", the lab's connection card, the ERPNext desk the deploy produced, and a terminal inside
the bench. It hard-cuts from the endcard back to the first beat, so the loop has no fade.

Every screen is a capture of `staging.benchpress.cloud`. The passwords on screen are the page's
own masking; no secret is readable.

## Re-rendering the film

The source is a Remotion project at `~/benchpress_video` on the machine that captured the takes.
It is kept outside this repository because it also holds the raw captures (about 300 MB).

- `src/heroBeats.ts` is the storyboard: one entry per beat, with the take, the in-point, the
  playback rate and the framing. `src/beats.ts` is the same thing for the long demo film. Both
  feed `src/Film.tsx`, so the two cuts share one look.
- `public/clips/*.mp4` are the takes, transcoded to H.264 with a keyframe every frame so
  Remotion can seek them.

```bash
npx remotion render BenchpressHero out/hero-frames --sequence --image-format=png --concurrency=2
ffmpeg -framerate 30 -i out/hero-frames/element-%03d.png -c:v libx264 -preset slow -crf 20 \
       -pix_fmt yuv420p -g 60 -movflags +faststart -an out/hero.mp4
ffmpeg -i out/hero-frames/element-408.png -qscale:v 3 out/hero-poster.jpg
```

Current files: 22 s, 1920×1080, 30 fps, 660 frames, ~3.4 MB. The poster is frame 408, the
"working site on your private network" beat — `HERO_POSTER_FRAME` in `src/heroBeats.ts` holds
that number, so the still and the film cannot drift apart.

The film this replaced was a design-tool mockup with invented hostnames, rendered by driving
`hero-film-standalone.html` frame by frame in headless Chromium. That pipeline is gone.
