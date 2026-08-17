# Hero film

Drop the exported film here and the landing page picks it up on the next request — no code change:

| File | What the page does |
|---|---|
| _neither_ | Renders the static endcard (wordmark, tagline, repo URL) inside the 16:9 frame. |
| `hero-poster.jpg` | Renders the poster frame as an image. |
| `hero.mp4` | Renders `<video autoplay muted loop playsinline>`, using the poster if it is there too. |

Export it from the design handoff's `Benchpress Hero Film.dc.html` (Share → Export → Video,
22s, 1920×1080). The animation engine (`animations-v3.jsx`, `hero-video.jsx`, `support.js`) is
deliberately not shipped — the handoff marks `support.js` "reference only".

The detection lives in `benchpress/www/home.py:hero_media`.
