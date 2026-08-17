# Screenshot Update Checklist

Every screenshot in `docs/images/` was recaptured against the redesigned SPA in phase 6 of the UI
redesign. Recapture them again whenever a screen changes shape — a guide illustrated with the
previous design is worse than one with no picture at all.

## How to capture

1. Bring the app up and log in as an admin with realistic data on the site.
2. Open `http://<host>/frontend`.
3. Light theme, viewport **1280×800**, no browser chrome in the frame.
4. Save as PNG into `docs/images/` under the name the guide already references.

The suite in this repo was captured with the `agent-browser` CLI, which frames the viewport
without chrome:

```bash
npx agent-browser@0.21.4 --session docs open http://localhost:8080/frontend/labs
npx agent-browser@0.21.4 --session docs set viewport 1280 800
npx agent-browser@0.21.4 --session docs screenshot docs/images/labs-list.png
```

---

## Current screenshots

| File | Page | What it shows |
|------|------|--------------|
| `labs-list.png` | `/frontend/labs` | The Labs table — status badges, apps, "Deployed as", last run |
| `new-lab.png` | `/frontend/labs/new` | The empty New lab form and its summary rail |
| `new-lab-filled.png` | `/frontend/labs/new` | The same form filled in, with two apps and a live summary |
| `lab-detail.png` | `/frontend/labs/:id` | Lab detail — both status axes, connection details, sites |
| `connection-info.png` | Lab detail > Dashboard | The connection card with its masked secrets |
| `deploy-log-tab.png` | Lab detail > Deploy log | The eleven-step stepper on a failed run, with the error banner |
| `build-log-tab.png` | Lab detail > Build log | A stored image build |
| `bench-instances.png` | `/frontend/bench-instances` | The instances table |
| `deploy-logs.png` | `/frontend/deploy-logs` | Deploy history — result, last step, duration, retention note |
| `build-logs.png` | `/frontend/build-logs` | Build history, reached from Labs (admin only) |
| `devices.png` | `/frontend/devices` | Devices — tunnel state, registered devices, connection test |
| `settings.png` | `/frontend/settings` | Settings as a page: three grouped cards and the save bar |

## Not captured

| File | Why |
|------|-----|
| `labs-list-empty.png` | No guide references it, and the empty state needs a site with zero labs |
| `deploy-confirm.png` | The deploy dialog follows a live run; a real deploy is needed to frame it |
| `new-site-dialog.png` | Not referenced by a guide |
| `device-config-dialog.png`, `add-device-dialog.png` | Not referenced by a guide; both contain a real key |

A screenshot of a dialog carrying a WireGuard config or a password must never be committed —
regenerate the device against a throwaway peer, or crop the secret out.

## Tips

- Light theme; the docs are read on white.
- Realistic sample data — never `test123`.
- Consistent 1280px viewport so the pictures line up with each other.
