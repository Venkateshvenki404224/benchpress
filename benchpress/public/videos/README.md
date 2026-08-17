# Hero film

The landing page picks these up on the next request — no code change:

| File | What the page does |
|---|---|
| _neither_ | Renders the static endcard (wordmark, tagline, repo URL) inside the 16:9 frame. |
| `hero-poster.jpg` | Renders the poster frame as an image. |
| `hero.mp4` | Renders `<video autoplay muted loop playsinline>`, using the poster if it is there too. |

The detection lives in `benchpress/www/home.py:hero_media`.

## Re-rendering the film

The film is authored as code in the design handoff (`hero-film-standalone.html`), not as a video
file. The handoff suggests exporting it from the design tool (Share → Export → Video), but that
button only posts `omelette:request-video-export` to its host frame — outside the design tool it
does nothing. Render it locally instead; the animation engine exposes a frame-exact seek transport
for precisely this:

1. Serve the handoff folder (`python3 -m http.server 8899`).
2. Drive `hero-film-standalone.html` in headless Chromium at a 1920×1124 viewport — 1080 of canvas
   plus the engine's 44px playback bar, which lands its auto-fit on scale 1. Load Poppins 600 from
   Google Fonts first: the bundle embeds Inter only, and the endcard tagline asks for Poppins.
3. Per frame, dispatch `data-om-seek-to-time-frame` with `detail {time, sync: true}` on the element
   carrying `data-om-exportable-video-with-duration-secs`. The `sync` flag makes the engine commit
   through `flushSync`, so the DOM holds that exact timestamp when `dispatchEvent` returns — no
   settle wait, no dropped or duplicated frames. Screenshot clipped to that element's box.
4. Encode: `ffmpeg -framerate 30 -i f%05d.png -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p
   -g 60 -movflags +faststart -an hero.mp4`.

Current files: 22s, 1920×1080, 30fps, 660 frames, ~2.4 MB. The poster is the site-live beat at
16.2s (frame 486). The film loops on a hard cut from endcard back to terminal — that is the
design's own loop behaviour, not an artefact of the render.

The engine itself (`animations-v3.jsx`, `hero-video.jsx`, `support.js`) is deliberately not
shipped — the handoff marks `support.js` "reference only".
