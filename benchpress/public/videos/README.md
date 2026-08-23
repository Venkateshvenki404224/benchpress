# Hero film

The landing page picks these up on the next request — no code change:

| File | What the page does |
|---|---|
| _neither_ | Renders the static endcard (wordmark, tagline, repo URL) inside the 16:9 frame. |
| `hero-poster.jpg` | Renders the poster frame as an image. |
| `hero.mp4` | Renders `<video autoplay muted loop playsinline controls>`, using the poster if it is there too. |

The detection lives in `benchpress/www/home.py:hero_media`. Both URLs carry the page's
`?v=` cache-busting token, because a recut keeps the filename and only the token tells the CDN
that the bytes changed.

## What the film is

Live footage of the real product, not a mockup. The current cut is the one-minute Frappe film:
the Templates page with one template of a Frappe version and seven apps, one click on Deploy,
the eleven-step pipeline, "Deploy complete — 4 m 4 s", the connection card that separates the
public URL from the VPN-only addresses, the site itself, and the installed-app list with a
version against each app.

The film carries a narration track. The hero starts it muted, so the visitor must unmute it
through the controls.

Every screen is a capture of `staging.benchpress.cloud`. The passwords on screen are the page's
own masking. No secret is readable.

## Re-rendering the film

The source is a Remotion project at `~/benchpress_video` on the machine that captured the takes.
It is kept outside this repository because it also holds the raw captures (about 300 MB).

- `src/frappeBeats.ts` is the storyboard for this cut: one entry per beat, with the take, the
  in-point, the playback rate, the framing and the narration file. `src/beats.ts` and
  `src/heroBeats.ts` are the same thing for the long demo film and the old 22 s silent loop. All
  three feed `src/Film.tsx`, so the cuts share one look.
- `public/clips/*.mp4` are the takes, transcoded to H.264 with a keyframe every frame so
  Remotion can seek them.

```bash
npx remotion render BenchpressFrappe out/benchpress-frappe.mp4 --concurrency=2
ffmpeg -ss 20 -i out/benchpress-frappe.mp4 -frames:v 1 -qscale:v 3 out/hero-poster.jpg
```

Copy both results into this directory as `hero.mp4` and `hero-poster.jpg`.

Current files: 60 s, 1920×1080, 30 fps, H.264 video with AAC audio, about 13.7 MB. The mp4 must
keep its `moov` atom in front (`-movflags +faststart`), or the browser downloads the whole file
before the first frame appears.
