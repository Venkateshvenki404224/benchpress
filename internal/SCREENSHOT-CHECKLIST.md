# Screenshot checklist

Recapture a screenshot whenever the screen it shows changes shape. A guide
illustrated with a previous design is worse than one with no picture at all.

## Where images live

Every new screenshot goes under the page that uses it:

```text
docs/images/<track>/<page-slug>/NN-name.png
```

`<track>` is `user`, `operator` or `reference`. `<page-slug>` matches the `.mdx`
file that shows the image. `NN` is the order the images appear on that page.
The quick tour's first frame is
`docs/images/user/quick-tour/01-overview.png`.

The flat files still directly in `docs/images/` belong to the older Markdown
guides. Each one is deleted when the page that replaces its guide lands.

## Rules

- Light theme. The docs are read on white.
- Viewport 1280×800, and no browser chrome in the frame.
- PNG, under 1.5 MB. A 1280×800 frame that does not fit has not been optimized.
- Realistic sample data. Never `test123`.
- Animations are rationed to three for the whole documentation set, capped at
  15 seconds and 3 MB each. Use one only where the change over time is the
  content. Everything else is a PNG.

## Alt text is not optional

Half the audience reads the flattened Markdown and never sees the image. So:

- Write alt text as a full sentence. Name what is on the screen and what to
  notice. `![screenshot]` is not alt text.
- State every value visible in the frame in prose or a table nearby. Strip the
  images and the page must still be complete.

Lint does not catch lazy alt text. `geo:image-alt` fires only when alt text is
missing, so `![screenshot]` passes it. Read your own page with the images off.

## Capturing

Log in first. Opening the app lands on `/login`, so an unauthenticated capture
frames the login form on every shot.

```bash
export AGENT_BROWSER_SESSION="$(agent-browser session id --prefix docs)"
agent-browser open https://<host>/frontend --args "--no-sandbox"
agent-browser set viewport 1280 800
agent-browser screenshot docs/images/user/quick-tour/01-overview.png
agent-browser close
```

Two logins are needed to photograph the whole app. `NewLab`, `LabTemplates`,
`Settings` and `BuildLogs` are admin-only, and `Credits` renders only while
credits are switched on. A user-track page captured as an admin shows controls
the reader will never have.

Record an animation as WebM, then convert it:

```bash
agent-browser record start /tmp/cap.webm
# drive the flow
agent-browser record stop
ffmpeg -i /tmp/cap.webm -vf "fps=10,scale=900:-1:flags=lanczos,palettegen" /tmp/pal.png
ffmpeg -i /tmp/cap.webm -i /tmp/pal.png \
  -lavfi "fps=10,scale=900:-1:flags=lanczos [x]; [x][1:v] paletteuse" out.gif
```

## Secrets

Never commit an image that shows a live SSH password, admin password or
WireGuard key belonging to a record that still exists. A screenshot is
published.

Reveal a secret on a demo record when the shape of it is the point — a masked QR
code teaches nothing — then destroy that record before the image is committed.
