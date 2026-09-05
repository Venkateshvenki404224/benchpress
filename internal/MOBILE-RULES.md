# Mobile rules for the console rebuild

The design (`pencil-welcome.pen`) is 1440 wide on every product artboard. This
file records the narrow-viewport target that issue #309 drew, so the tickets
that implement #308 have a spec rather than a guess. The canvas is not in the
repository — `*.pen` is gitignored — so this file, not the canvas, is the
record that survives.

## The boards

Seven frames were added to the canvas, on the row at `y = 9100`, plus a
`Sidebar Collapsed` component beside the other reusables and a `00e Mobile
rules` note board beside `00d Scale`.

| Board | Desktop artboard it narrows |
|---|---|
| `M1 Overview — mobile` | `01 Overview` |
| `M2 Overview first run — mobile` | `18 Overview — first run` |
| `M3 Labs — mobile` | `02 Labs` |
| `M4 Lab detail — mobile` | `03 Lab detail` |
| `M5 Templates — mobile` | `05 Templates` |
| `M6 New lab — mobile` | `08 New lab` |

Each is 390 wide — an iPhone 14 in portrait — and as tall as the page scrolls,
so the whole screen is on one board. The fold sits at 844. The rail takes 48 of
the 390, which leaves 318 of content. Every board is built from the components
and tokens the desktop artboards already use; nothing new was introduced.

Instances, Devices and the dialogs get no board. They inherit the rules below.

## Rule 0 — the shell is already mobile, so do not build a drawer

frappe-ui's `Sidebar` collapses itself below `sm`. `shouldCollapse` is
`isCollapsed || isMobile`, and `isMobile` is `breakpoints.smaller('sm')`
(`frontend/node_modules/frappe-ui/src/components/Sidebar/Sidebar.vue`). The rail
goes to `w-12` — 48px — labels and suffixes fade out, and every item keeps the
tooltip `SidebarItem` already renders. `CreditMeter` already has a collapsed
rendering behind its `is-collapsed` prop.

So the rail stays a rail. No off-canvas drawer, no hamburger, no new component.
The conditional Credits nav item, when it lands, sits in the rail in the place
it holds when the rail is expanded.

The 50px header keeps both the breadcrumb and the VPN chip at 342px; the chip is
the point of that bar and stays. A tab row that overflows scrolls sideways
rather than wrapping.

## Rule 1 — a two-column body becomes one column at `lg`

Overview, Devices and New lab already collapse at `lg` (1024px), and the stat
grids at `sm`. The rule formalises the breakpoint the SPA picked and settles the
order.

Below `lg` the body is one column. Cards are ordered by what a narrow visit is
for, not by which column they sat in: a banner first, then the card that answers
the screen, then the rest. Each board fixes its own order and that order is the
spec — see the table below.

A four-up stat row becomes two-up, never a column of four. A three-up field grid
becomes two-up.

`lg:sticky` on the New lab summary is a desktop affordance. In one column the
summary is simply the last card, after the form it summarises.

## Rule 2 — a fixed-width table becomes a stacked list at `sm`

`DataTable` wraps frappe-ui's `ListView`, which lays its grid inside a
`max-content` container — which is why every calling page declares fixed pixel
column widths. Below the card's width the table scrolls sideways inside it.

Below `sm` the table is not rendered at all. The same rows render as a stacked
list, one card row per record, and **no column is dropped**: what was a column
becomes a line. The shape is the row already drawn on Overview's environments
card — a head line carrying the mark, the name, the id and the status pill, then
the record's own lines, then a meta line ending in the timestamp.

The cost is a second rendering of each list. Every test hook must exist on both
renderings under the same name, or the end-to-end specs pass at one width and
fail at the other.

Instances inherits this rule without a board of its own.

## Rule 3 — a page head that cannot fit its actions stacks

Every page head is a single row today: title block left, actions right. At 318px
of content the three-button heads overflow.

Below `lg` the head is a column — title, sub, then a full-width action row. The
primary action fills the row. Other actions keep their place while they fit on
one line; when they do not, every action but the primary moves into the ellipsis
menu lab detail already uses.

Worked through: Overview has two, both stay. Labs has three, so New lab fills
and Build history and From template go into the ellipsis. Lab detail's two
buttons plus the ellipsis do fit, so all three stay. Templates and New lab have
one each.

## What each board fixes

| Board | Order, top to bottom |
|---|---|
| M1 Overview | greeting and actions · VPN banner · stats 2×2 · your environments · recent activity · shared infrastructure · leases expiring soon |
| M2 Overview, first run | greeting · getting started · most used templates · your environments (empty) · what it costs |
| M3 Labs | head and actions · search and count · filters · the stacked lab list |
| M4 Lab detail | lab head and actions · spec chips · tabs · reachable banner · connection details · lease · container status · apps · sites · recent runs |
| M5 Templates | head and action · seven template cards, one per row · blank lab |
| M6 New lab | head and cancel · identity · apps · resources and access · what gets built · build note |

## Smaller decisions the boards make

- A mono value that cannot wrap — a git URL, an image tag — drops its scheme and
  takes the next type step down rather than overflowing its card. `App Url` is
  11px on both boards that carry one.
- The Labs result count rides with the search field; the three filter buttons
  take the line below.
- A stat tile's note wraps under the figure instead of sitting beside it.
- An environment row puts the status pill and the health word on the row's foot,
  beside the action, so the site address gets the full width of the head.
- On lab detail and New lab an app row stacks: name and branch on one line, the
  git URL on the next.
- The lab-detail signals — bench status and container health — sit side by side
  and hug their pills, exactly as they do on the desktop board.

## One thing to resolve, not decided here

The desktop artboards say "1 credit per hour" on the first-run cost card and in
the New lab summary. The mobile boards copy that wording unchanged, because this
ticket moves layout and not copy. The hourly meter left the backend, and
`frontend/src/utils/credits.spec.js` fails the build if its vocabulary reappears
in an identifier. Whoever builds #311 and #318 has to settle what that line says.
