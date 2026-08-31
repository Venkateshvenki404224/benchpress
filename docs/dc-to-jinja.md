# dc-runtime to Jinja — the translation guide

Status: contract. The four public-site frontend phases build against this file.

The mockups in `handoff 2/` are Design Components. They run in a browser on `support.js`, a
React-based runtime called dc-runtime. None of that runtime ships. The pages we ship are
Frappe Jinja templates rendered on the server, one plain CSS file, and one plain JavaScript
file.

This document maps every dc-runtime idiom to what replaces it. Follow it exactly. Contributors
translate the same mockups separately. Any freedom taken here becomes several house styles
in one site.

---

## 0. Where each part of a mockup goes

A mockup file has four parts. Each part has one destination.

| Part of the mockup | Destination |
|---|---|
| `<helmet>` — stylesheet and script tags | Deleted. `brand.css` replaces all of it. |
| The page `<style>` block | Deleted. `brand.css` already carries every rule in it. |
| The markup inside `<x-dc>` | `benchpress/www/<page>.html` |
| Inline `style=""` attributes | Named classes in `benchpress/public/css/landing.css` |
| The `<script type="text/x-dc">` data arrays | Seed rows in Desk, read by `benchpress/www/<page>.py` |
| The `<script type="text/x-dc">` handlers | `benchpress/public/js/<page>.js`, or `bpSite` when it is shared |

The files a page owns:

```
benchpress/www/<page>.html          the template
benchpress/www/<page>.py            the controller — reads its Single, builds context
benchpress/public/js/<page>.js      the listeners only this page needs
benchpress/public/css/landing.css   every class the five pages use
```

The files a page uses but must not edit:

```
benchpress/public/css/brand.css              tokens, faces, keyframes, breakpoints
benchpress/templates/includes/site_head.html the shared <head>: meta, favicons, font preloads,
                                             brand.css, the chrome CSS, and site.js
benchpress/templates/includes/site_header.html  the header (also as public_header.html)
benchpress/templates/includes/site_footer.html  the footer (also as public_footer.html)
benchpress/public/js/site.js                 window.bpSite — theme, nav, form posting
```

`brand.css` is the palette of record. Do not add a token to it, do not redeclare one of its
tokens in `landing.css`, and do not hardcode a color that a token already names.

---

## 1. `<x-dc>` and `<helmet>` — both disappear

`<x-dc>` is the component boundary. dc-runtime finds it, compiles what is inside, and mounts
the result into `#dc-root`. `<helmet>` is the head fragment that the runtime hoists into the
real `<head>`.

Neither has a server-side equivalent. `<x-dc>` becomes the `page_content` block. `<helmet>`
becomes the `head_include` block, with almost every line in it deleted.

### Before

```html
<x-dc>
<helmet>
<link rel="stylesheet" href="_ds/…/tokens/fonts.css">
<link rel="stylesheet" href="_ds/…/tokens/colors.css">
<link rel="stylesheet" href="_ds/…/tokens/marketing.css">
<link rel="stylesheet" href="_ds/…/styles.css">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;800">
<script src="_ds/…/_ds_bundle.js"></script>
<script src="https://unpkg.com/lucide@0.451.0/dist/umd/lucide.min.js"></script>
<style>
:root{--m-ink:#0A1024;--m-blue:#1F5CF5; … }
.bp[data-mode="dark"]{ … }
@keyframes bp-pulse{0%,100%{opacity:1}50%{opacity:.3}}
</style>
</helmet>
<div class="bp" data-mode="{{ mode }}">
  …
</div>
</x-dc>
```

### After

```jinja
{% extends "templates/web.html" %}

{% block head_include %}
{% include "templates/includes/site_head.html" %}
<link rel="stylesheet" href="/assets/benchpress/css/landing.css?v={{ asset_version | e }}">
{% endblock %}

{% block page_content %}
<div class="bp" data-mode="{{ mode_default | e }}">
  {% include "templates/includes/site_header.html" %}
  <main id="bp-content">
    …
  </main>
  {% include "templates/includes/site_footer.html" %}
</div>
{% endblock %}
```

`site_head.html` already links `brand.css`, preloads the three Poppins cuts above the fold,
carries the chrome CSS and loads `site.js`. Include it and add only the page stylesheet. Do not
link `brand.css` a second time.

Line by line, what happened to the `<helmet>`:

1. The seven `_ds/…/tokens/*.css` links go away. `brand.css` carries the tokens the site uses.
2. The Google Fonts link goes away. Poppins is self-hosted, and `brand.css` declares the faces.
   The site sits behind Cloudflare and must work on a host with no route to Google.
3. The `_ds_bundle.js` script goes away. It defines the design-system web components. The one
   the landing page uses, `MarketingButton`, becomes a plain `<a class="bp-btn">`.
4. The lucide CDN script goes away. See §8.
5. The `<style>` block goes away. Every rule in it is already in `brand.css`.

Two things stay, and they are not optional:

- The `.bp` wrapper with `data-mode`. `brand.css` hangs the whole palette off that attribute.
- `{% extends "templates/web.html" %}`. It supplies `frappe-web.bundle.js`, which is where
  `frappe.boot`, the CSRF token and jQuery come from. `/login` cannot work without it.

Blank the framework chrome the same way on every page. These are the real block names. Three
of them come from `frappe/templates/base.html` and two from `frappe/templates/web.html`. A name
that is not on this list is a silent no-op, and the framework chrome renders anyway:

```jinja
{% block navbar %}{% endblock %}        {# base.html — Standard Navbar #}
{% block footer %}{% endblock %}        {# base.html — Standard Footer #}
{% block breadcrumbs %}{% endblock %}   {# web.html #}
{% block page_sidebar %}{% endblock %}  {# web.html — not "sidebar" #}
{% block page_footer %}{% endblock %}   {# web.html — not "footer" #}
```

The page's own script goes in `{% block script %}`, which `base.html` renders after
`frappe-web.bundle.js`. Link it as a plain file, not through `include_script`, which only
resolves built bundles. `site.js` is not linked here — `site_head.html` already loads it:

```jinja
{% block script %}
<script defer src="/assets/benchpress/js/index.js?v={{ asset_version | e }}"></script>
{% endblock %}
```

The branded header and footer go inside `page_content`. `public_header.html` and
`public_footer.html` are aliases for `site_header.html` and `site_footer.html` — both names
resolve to the same chrome, so include whichever pair the surrounding code already uses.

---

## 2. `<sc-if>` becomes `{% if %}`

dc-runtime evaluates `value` against the props object and renders the children when the result
is truthy. `hint-placeholder-val` is an editor-preview affordance. It has no runtime meaning.
Delete it.

### Before

```html
<sc-if value="{{ showAgents }}" hint-placeholder-val="{{ true }}">
<section data-r="sec" id="agents" style="background:var(--bg1);padding:96px 0">
  …
</section>
</sc-if>
```

### After

```jinja
{% if show_agents %}
<section data-r="sec" id="agents" class="bp-section bp-section--band">
  …
</section>
{% endif %}
```

Rules:

1. The name goes from `camelCase` to `snake_case`. It must be a key the page controller sets.
   `show_agents` and `show_testimonials` come from `Landing Page Settings` checks, per the spec.
2. A Frappe `Check` field is `0` or `1`. Both work with a plain `{% if %}`.
3. Frappe's Jinja environment uses `DebugUndefined`. An undefined name is falsy in `{% if %}`,
   but `{{ undefined_name }}` prints the literal text `{{ undefined_name }}` into the page.
   Set every key in the controller. Where a key can be missing, write
   `{{ settings.hero_badge_text | default("", true) | e }}`.
4. An optional section must also survive an empty child table. Guard the repeater, not only
   the section: `{% if settings.agent_points %}`.
5. The mockup's mutually exclusive states — `tabInstances` / `tabDeploy` / `tabDevices`,
   `isDark` / `isLight` — are client state, not server state. Render all branches and let CSS
   and JavaScript pick one. See §7.

---

## 3. `<sc-for>` becomes `{% for %}`

`list` is the array. `as` names the loop variable. `hint-placeholder-count` is an editor
affordance. Delete it. Inside the loop, dc-runtime also exposes `$index`.

### Before

```html
<sc-for list="{{ hostedPoints }}" as="p" hint-placeholder-count="3">
  <div style="display:flex;gap:10px;align-items:flex-start;font-size:14px;line-height:1.5">
    <i data-lucide="check" style="display:inline-flex;width:17px;height:17px;color:var(--m-blue)"></i>
    <span>{{ p.text }}</span>
  </div>
</sc-for>
```

### After

```jinja
{% for point in hosted_points %}
  <div class="bp-point">
    {{ icon.check("bp-point__icon") }}
    <span>{{ point.text | e }}</span>
  </div>
{% endfor %}
```

Rules:

1. Give the loop variable a real name. `p` becomes `point`, `c` becomes `row`, `t` becomes
   `tab`. The mockup's one-letter names came from a minifier, not from a decision.
2. `$index` becomes `loop.index0`. `loop.index` is one-based.
3. Escape every interpolated field with `| e`. Frappe's Jinja does **not** autoescape. The only
   fields that render raw are the `Text Editor` ones the spec names — `lede`, `situation_body`,
   `selfhost_note`, `login_signup_prompt`, `contact_lede`, `days_closing`, `contrast_lede`,
   `contrast_closing`, `selfhost_body`. Only a System Manager or a BenchPress Admin can write
   them. Mark each one with a comment where it renders raw.
4. A doubled list stays doubled in the template, not in the seed data. The marquee needs two
   copies for the `bp-marquee` loop to be seamless:
   `{% for card in settings.template_cards + settings.template_cards %}`.
   Do not seed twelve rows.
5. An empty child table must render as nothing, never as an empty box with a border. Wrap the
   container, not only the loop.

---

## 4. `onClick="{{ handler }}"` becomes a real listener

dc-runtime maps `onClick` to React's `onClick` and binds it to a function the logic class put
in the values object. There is no logic class on the server. Write the behavior once, in
`benchpress/public/js/<page>.js`, and reach it from the markup through a `data-bp-*`
attribute.

Never emit an inline `onclick=""`. Inline handlers are not reviewable, they cannot be tested,
and they break under a content security policy.

### Before

```html
<button type="button" onClick="{{ t.select }}"
  style="padding:10px 18px;border-radius:999px;background:{{ t.bg }};color:{{ t.fg }}">
  {{ t.label }}
</button>
```

with, in the logic class:

```js
phaseTabs: Object.keys(PHASES).map((k) => ({
  label: PHASES[k].label,
  select: () => this.setState({ phase: k }),
})),
```

### After

Markup:

```jinja
{% for phase in phases %}
<button type="button"
        class="bp-tab{% if phase.phase_key == default_phase %} is-selected{% endif %}"
        data-bp-phase="{{ phase.phase_key | e }}"
        aria-pressed="{{ 'true' if phase.phase_key == default_phase else 'false' }}">
  {{ phase.label | e }}
</button>
{% endfor %}
```

Script:

```js
// One delegated listener per group, not one per button. The rows are server-rendered, so
// the count is not known here and a per-node listener would have to be re-bound.
function bindPhaseTabs(root) {
	const tabs = root.querySelector("[data-bp-phase-tabs]");
	if (!tabs) return;

	tabs.addEventListener("click", (event) => {
		const button = event.target.closest("[data-bp-phase]");
		if (!button) return;
		selectPhase(root, button.dataset.bpPhase);
	});
}

function selectPhase(root, key) {
	for (const button of root.querySelectorAll("[data-bp-phase]")) {
		const on = button.dataset.bpPhase === key;
		button.classList.toggle("is-selected", on);
		button.setAttribute("aria-pressed", String(on));
	}
	for (const panel of root.querySelectorAll("[data-bp-phase-panel]")) {
		panel.hidden = panel.dataset.bpPhasePanel !== key;
	}
}

function start() {
	const root = document.querySelector(".bp");
	if (root) bindPhaseTabs(root);
}

// `site.js` uses this same pattern. The tag carries `defer`, so `loading` is the rare case.
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
else start();
```

Rules:

1. One delegated listener per group. Do not attach a listener to each rendered row.
2. The attribute carries data. The class carries state. Never read state back out of a class
   name that CSS also uses for looks.
3. Every control the mockup draws as a button must be a `<button type="button">`, and every
   control it draws as a link must be an `<a href>`. The mockup uses whichever element was
   convenient. A tab that is not a button cannot be reached by keyboard.
4. Add the ARIA the mockup omits — `aria-pressed` on a toggle, `aria-expanded` and
   `aria-controls` on the FAQ, `hidden` on the panel that is not showing.
5. Load the page script with `defer` and start it from one `readyState` check, the way
   `site.js` does. One entry point per file. Do not sprinkle listeners at module top level.

### The handlers that are already written

Three of the mockups' handlers are shared, so they live in `benchpress/public/js/site.js` and
are exposed as `window.bpSite`. `site_head.html` loads that file. Do not reimplement any of
them, and do not copy the mockup's version.

| Mockup handler | Use instead |
|---|---|
| `onClick="{{ toggleMode }}"` | Put `data-bp-mode-toggle` on the button. Nothing else. |
| the mode read on load | Already handled. `site.js` applies the stored mode, and an inline script in `site_head.html` applies it before first paint. |
| a form submit that posts to a method | `window.bpSite.postMethod(method, new FormData(form))` |

```js
// /signup, /contact — the whole of the submit path.
form.addEventListener("submit", async (event) => {
	event.preventDefault();
	try {
		const reply = await window.bpSite.postMethod("benchpress.contact.submit", new FormData(form));
		showSuccess(reply);
	} catch (error) {
		showError(error.message); // Already the server's own wording where it sent one.
	}
});
```

`postMethod` sends the CSRF token, unwraps the `message` key, and turns a Frappe validation
error into an `Error` carrying the server's wording. Do not call `fetch` or `frappe.call`
directly.

The mockup also calls `document.body.style.background` on every render. Delete it. The theme is
one attribute on the `.bp` wrapper, and `brand.css` does the rest.

Hook names `site.js` already owns, so do not reuse them for anything else:
`data-bp-mode-toggle`, `data-bp-header`, `data-bp-nav-toggle`, and the `bp-content` id.

---

## 5. `style-hover=""` becomes a class and a `:hover` rule

`style-hover` is a dc-runtime extension. `createPseudoSheet` in `support.js` turns each one
into a generated class such as `.scp0`, inserts `.scp0:hover{…}` into a runtime stylesheet, and
marks every declaration `!important` so it beats the inline `style` on the same element.

Inline styles cannot have a hover state. That is the whole reason the extension exists. Once
the base styles are a class, the `!important` is not needed, and you must not carry it over.

### Before

```html
<a href="#start"
   style="display:inline-flex;align-items:center;gap:7px;height:36px;padding:0 16px;
          border-radius:999px;background:var(--m-blue);color:#fff;font-size:13.5px;font-weight:600"
   style-hover="background:var(--accent);color:#fff">Start free</a>
```

### After

Markup:

```jinja
<a class="bp-btn bp-btn--primary" href="{{ signup_route | e }}">Start free</a>
```

`landing.css`:

```css
.bp-btn {
	display: inline-flex;
	align-items: center;
	gap: 7px;
	height: 36px;
	padding: 0 16px;
	border-radius: 999px;
	font-size: 13.5px;
	font-weight: 600;
	transition: var(--transition-control);
}

.bp-btn--primary {
	background: var(--m-blue);
	color: var(--onbrand);
}

.bp-btn--primary:hover {
	background: var(--accent);
}

/* The mockup has no focus state. A keyboard user needs one, and it is not optional. */
.bp-btn:focus-visible {
	outline: 2px solid var(--accent);
	outline-offset: 2px;
}
```

Rules:

1. Drop the `!important`. If a hover rule needs it, the base rule is in the wrong place.
2. Replace a literal `#fff` in a hover value with the token that means it — `--onbrand` on a
   brand fill, `--fg` on a card fill. The mockup writes `#fff` because it had no token to hand.
3. Add `:focus-visible` beside every `:hover` you write. The mockup has no focus states at all.
4. `transition: var(--transition-control)` covers background, border-color and color. Use it
   instead of writing a transition list.

---

## 6. Inline `style=""` becomes a named class

Every element in the mockups carries its full styling inline, because a Design Component has no
stylesheet. On the server this is unreadable, uncacheable and impossible to theme.

Move all of it into `landing.css` under a named class. Shipped markup carries no `style`
attribute, with one carve-out described below.

### Before

```html
<a href="#paths"
   style="display:inline-flex;align-items:center;gap:9px;height:50px;padding:0 22px;
          border-radius:999px;background:var(--card);border:1px solid var(--cardb);
          color:var(--fg);font-size:15px;font-weight:500"
   style-hover="background:var(--cardb);color:var(--fg)">
  <i data-lucide="github" style="display:inline-flex;width:16px;height:16px"></i>
  Self-host it instead
</a>
```

### After

```jinja
<a class="bp-btn bp-btn--lg bp-btn--ghost" href="{{ settings.hero_cta_secondary_url | e }}">
  {{ icon.github("bp-btn__icon") }}
  {{ settings.hero_cta_secondary_label | e }}
</a>
```

```css
.bp-btn--lg {
	height: 50px;
	padding: 0 22px;
	gap: 9px;
	font-size: 15px;
	font-weight: 500;
}

.bp-btn--ghost {
	background: var(--card);
	border: 1px solid var(--cardb);
	color: var(--fg);
}

.bp-btn--ghost:hover {
	background: var(--cardb);
}

.bp-btn__icon {
	width: 16px;
	height: 16px;
	flex: none;
}
```

### Naming

Every class starts with `bp-`. This is not decoration. On `/login` the page also loads
`login.bundle.css`, which owns generic names such as `.card`, `.section`, `.btn` and
`.form-group`. An unprefixed class will collide with one of them.

```
.bp-<block>               a section or a component      .bp-hero, .bp-btn, .bp-tab
.bp-<block>__<element>    a part of it                  .bp-hero__terminal, .bp-btn__icon
.bp-<block>--<modifier>   a variant of it               .bp-btn--primary, .bp-card--wide
.is-<state>               a state JavaScript toggles    .is-selected, .is-open, .is-active
```

`data-r` stays on the element that had it. `brand.css` keys both breakpoints on those hooks
(`pad`, `sec`, `hero`, `nav`, `split`, `bento`, `quote`, `tabs`, `tabs2`, `float`). Removing one
silently breaks the mobile layout.

### The one place an inline style is still correct

A value computed per row that cannot be a class — a staggered animation delay, a marquee
duration derived from the row count. Pass it as a custom property, never as a real declaration.

```jinja
{% for line in hero_log %}
<div class="bp-term__line" style="--bp-delay: {{ loop.index0 * 0.35 }}s">…</div>
{% endfor %}
```

```css
.bp-term__line {
	animation: bp-line 0.5s var(--ease-out) both;
	animation-delay: var(--bp-delay, 0s);
}
```

The hero terminal is `[TEMPLATE]` content, so the delays are hard-coded and safe. Never
interpolate a database value into a `style` attribute. A `Data` field the operator controls
would land inside a CSS declaration, where `| e` does not protect you.

### Box model

`brand.css` sets `box-sizing: border-box` on `.bp` and inherits it down. The mockup's inline
styles were content-box. Check every ported width and padding against the rendered mockup, not
against the number in the attribute.

---

## 7. `{{ s.bg }}` and `{{ s.fg }}` become classes toggled by state

The mockups compute colors in JavaScript and interpolate them into the `style` attribute. The
color and the state are the same thing, written twice.

### Before

```html
<button type="button" onClick="{{ t.select }}"
  style="border:1px solid {{ t.border }};background:{{ t.bg }};color:{{ t.fg }}">
  {{ t.label }}
</button>
```

```js
consoleTabs: [["instances", "Instances"], ["deploy", "Deploy history"]].map(([k, label]) => {
  const sel = k === tab;
  return {
    label,
    border: sel ? "var(--m-blue)" : "var(--m-line-strong)",
    bg: sel ? "var(--m-blue)" : "#fff",
    fg: sel ? "#fff" : "var(--m-ink)",
  };
}),
```

### After

```jinja
<button type="button" class="bp-console-tab{% if loop.first %} is-selected{% endif %}"
        data-bp-console-tab="{{ tab.key | e }}">
  {{ tab.label | e }}
</button>
```

```css
.bp-console-tab {
	border: 1px solid var(--m-line-strong);
	background: #fff;
	color: var(--m-ink);
	transition: var(--transition-control);
}

.bp-console-tab.is-selected {
	border-color: var(--m-blue);
	background: var(--m-blue);
	color: #fff;
}
```

The JavaScript now toggles `is-selected` and nothing else. It never writes a color.

### The status pills

`support.js` holds a `PILL` map from a state name to three Espresso tokens. Turn the map into
five modifier classes. The token values are already in `brand.css`.

```css
.bp-pill { /* shared geometry */ }
.bp-pill--ok   { background: var(--green-1); color: var(--green-ink); }
.bp-pill--warn { background: var(--amber-1); color: var(--amber-ink); }
.bp-pill--err  { background: var(--red-1);   color: var(--red-ink); }
.bp-pill--idle { background: var(--gray-2);  color: var(--ink-6); }
/* `info` hardcodes these two literals in the mockup rather than using the Espresso blue
 * ramp. Reproduce them. Do not substitute --blue-1 / --blue-3. */
.bp-pill--info { background: #edf1ff; color: #1b2cc1; }

.bp-pill__dot { background: currentColor; }
.bp-pill--ok   .bp-pill__dot { background: var(--green-3); }
.bp-pill--warn .bp-pill__dot { background: var(--amber-2); }
.bp-pill--err  .bp-pill__dot { background: var(--red-4); }
.bp-pill--idle .bp-pill__dot { background: var(--gray-5); }
```

The console block is a picture of the product. It keeps the Espresso palette and nothing else.
The page around it keeps Cobalt. The two do not mix.

### The pipeline diagram nodes

`node(n)` in the mockup returns `border`, `bg` and `opacity` per phase. The state is "this node
is part of the selected phase". One class:

```css
.bp-node {
	border: 1px solid var(--cardb);
	background: var(--card);
	opacity: 0.5;
	transition: opacity var(--duration-base) var(--ease-out),
		border-color var(--duration-base) var(--ease-out);
}

.bp-node.is-on {
	border-color: var(--accent);
	background: var(--cardb);
	opacity: 1;
}
```

Each phase row lists its own nodes and chips, so the server can render the default phase's
state and the script only has to move it.

### Zebra striping

The mockup computes `zebra: i % 2 === 1 ? "#FCFCFC" : "transparent"`. Use `:nth-child(even)`.
Do not emit a class per row.

---

## 8. lucide icons become inline SVG

The mockups load `lucide@0.451.0` from unpkg and call `lucide.createIcons()` after every
render. Every `<i data-lucide="name">` is replaced in the browser.

We do not load it. The site sits behind Cloudflare with no third-party origins, an air-gapped
or VPN-only install has no route to unpkg, and a CDN icon set that arrives after paint makes
every button jump. Inline the SVG.

### Before

```html
<i data-lucide="arrow-right" style="display:inline-flex;width:16px;height:16px"></i>
```

### After

One macro file, `benchpress/templates/icons.html`, imported by each page:

```jinja
{% import "templates/icons.html" as icon %}
…
{{ icon.arrow_right("bp-btn__icon") }}
```

```jinja
{%- macro _svg(body, klass) -%}
<svg class="{{ klass | e }}" viewBox="0 0 24 24" fill="none" stroke="currentColor"
     stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
     aria-hidden="true" focusable="false">{{ body }}</svg>
{%- endmacro -%}

{%- macro arrow_right(klass="") -%}
{{ _svg('<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>', klass) }}
{%- endmacro -%}
```

Rules:

1. Copy the path data from lucide 0.451.0 unchanged. Keep `viewBox="0 0 24 24"`,
   `fill="none"`, `stroke="currentColor"`, `stroke-width="2"` and both round joins. Changing
   any of those makes one icon look unlike the rest.
2. Size the icon in CSS, not with `width` and `height` attributes. The mockup sizes inline
   because it had no stylesheet.
3. `stroke="currentColor"` means the icon follows the text color. Never set `stroke` to a
   literal. Set `color` on the wrapper.
4. A decorative icon carries `aria-hidden="true"` and `focusable="false"`. An icon that is the
   entire content of a control needs an `aria-label` on the control.

### Icons whose name comes from the database

Several child tables store an icon name — `Landing Feature Card.icon`,
`Landing Console Callout.icon`, `Landing Agent Point.icon`, `Contact Channel.icon`,
`About Principle.icon`, `Signup Pending Link.icon`. In the mockup these render as
`<i data-lucide="{{ c.icon }}">`.

A macro cannot be called by a name held in a variable, so add one dispatch macro that maps the
stored string to a macro and falls back safely:

```jinja
{%- macro by_name(name, klass="") -%}
{%- if name == "shield" -%}{{ shield(klass) }}
{%- elif name == "terminal" -%}{{ terminal(klass) }}
{%- elif name == "credit-card" -%}{{ credit_card(klass) }}
{%- else -%}{{ circle(klass) }}
{%- endif -%}
{%- endmacro -%}
```

An unknown name must render the neutral fallback. It must never render nothing, and it must
never render the raw string.

### The set to inline

Hard-coded in the markup: `arrow-right`, `check`, `clock`, `copy`, `cpu`, `credit-card`,
`eye-off`, `github`, `hammer`, `laptop`, `layout-template`, `lock`, `mail-check`, `plus`,
`send`, `server`, `shield`, `shield-alert`, `terminal`, `trash-2`, `triangle-alert`,
`user-check`, `x`, plus the `sun` and `moon` pair the theme toggle already carries inline.

Reachable from seed data, so `by_name` must know them: `bot`, `book-open`, `calendar`, `eye`,
`file-text`, `list`, `mail`, `monitor`, `timer`, `users`, and the overlapping names above.

App icons in the template marquee are not lucide. They are the SVG files copied to
`benchpress/public/images/app-icons/`, referenced by URL.

---

## 9. Things the mockup does that we do not copy

1. **`document.body.style.background`.** The mockup paints the body from JavaScript on every
   render. `brand.css` paints it from `--bg0`. Delete the call.
2. **The `.scp0` generated classes.** They are runtime output, not source. They never appear in
   our CSS.
3. **`hint-placeholder-count`, `hint-placeholder-val`, `hint-size`, `sc-name`, `data-dc-tpl`.**
   All editor affordances. Delete every one.
4. **`<x-import component-from-global-scope="…MarketingButton">`.** A design-system web
   component. It becomes `<a class="bp-btn bp-btn--lg bp-btn--primary">`.
5. **No animation at all when the visitor asks for none.** `brand.css` redefines all eight
   keyframes under `prefers-reduced-motion: reduce`. Do not add a ninth animation without
   adding its reduced-motion form there. The mockup does not handle this. We do.
6. **`REQ-26-118`.** A static string in the signup mockup. The real reference is
   `REQ-XXXX-XXXX`, derived per the spec, and it arrives in the endpoint response.

---

## 10. Checklist before the pull request

1. No `style=""` in the template, except a `--bp-*` custom property on a `[TEMPLATE]` element.
2. No `onclick=""`, and no inline `<script>` other than the theme-mode read in `head_include`.
3. No `data-lucide`, no `unpkg.com`, no `fonts.googleapis.com`, no `_ds/` path.
4. No color literal in `landing.css` that a token in `brand.css` already names. The only
   allowed literals are the `info` pill's `#edf1ff` and `#1b2cc1`, and the `#fff` the console
   mock uses as a product surface.
5. Every interpolation has `| e`, except the `Text Editor` fields the spec names.
6. Every `:hover` has a matching `:focus-visible`.
7. Every `data-r` hook from the mockup is still on its element.
8. The page renders with an empty Single and empty child tables. No traceback, no empty box
   with a border, no `{{ undefined_name }}` printed into the page.
9. Flipping `data-mode` on the `.bp` wrapper in devtools re-themes the whole page, and nothing
   else has to change.
10. `uvx pre-commit@4.3.0 run --all-files` passes. Never run `yarn lint`.
