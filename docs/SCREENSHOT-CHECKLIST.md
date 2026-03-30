# Screenshot Update Checklist

The existing screenshots in `docs/images/` are from the old UI and need to be replaced. Take each screenshot from the Vue 3 SPA at `/frontend`.

## How to capture

1. Start bench: `bench start`
2. Open `http://your-site.localhost:8000/frontend`
3. Log in as Administrator
4. Use browser DevTools or a screenshot tool (1280x800 recommended)
5. Save as PNG to `docs/images/`

---

## README screenshots (replace existing)

| File | Page | What to show |
|------|------|-------------|
| `labs-list.png` | `/frontend/labs` | Labs list with 2-3 labs in different statuses (Draft, Ready, Error), search bar visible, filters visible |
| `new-lab.png` | `/frontend/labs/new` | New Lab form filled out with Lab ID, Title, Frappe Version selected, 2 apps added |
| `lab-detail.png` | `/frontend/labs/:id` | Lab Detail Dashboard tab with Connection Info panel, Container Status card showing CPU/Memory bars |
| `bench-instances.png` | `/frontend/bench-instances` | Bench Instances table with 2-3 benches in different statuses, IP addresses, CPU/Memory columns |
| `deploy-logs.png` | `/frontend/deploy-logs` | Deploy Logs page with 2-3 entries, one expanded showing deployment steps |
| `build-logs.png` | `/frontend/build-logs` | Build Logs page with 2-3 entries, one expanded showing Docker build output |
| `devices.png` | `/frontend/devices` | Devices page with 2-3 device cards showing types, IPs, and status badges |
| `settings.png` | `/frontend/settings` | Settings dialog showing Docker, WireGuard, and Resource Limits sections |

## New screenshots for docs/ guides

| File | Page/State | What to show | Used in |
|------|-----------|-------------|---------|
| `labs-list-empty.png` | `/frontend/labs` (no labs) | Empty state with "No labs found" message | creating-labs.md |
| `new-lab-filled.png` | `/frontend/labs/new` (filled) | Completed form before clicking Create | creating-labs.md |
| `build-log-tab.png` | Lab Detail > Build Log tab | Build in progress with collapsible steps | creating-labs.md, logs-and-monitoring.md |
| `deploy-log-tab.png` | Lab Detail > Deploy Log tab | Deploy in progress with step indicators | creating-labs.md, logs-and-monitoring.md |
| `deploy-confirm.png` | Lab Detail > Deploy dialog | Confirmation dialog before deploying | creating-labs.md |
| `connection-info.png` | Lab Detail > Dashboard | Connection Info panel with all fields and copy buttons | connecting-to-benches.md |
| `container-status.png` | Lab Detail > Dashboard | Container Status card with CPU/Memory progress bars | logs-and-monitoring.md |
| `new-site-dialog.png` | Lab Detail > Sites tab > New Site | New Site dialog with app checkboxes | creating-labs.md |
| `devices-empty.png` | `/frontend/devices` (no devices) | Empty state with "No devices registered" | device-management.md |
| `add-device-dialog.png` | Devices > Add Device | Add Device dialog with fields filled | device-management.md |
| `device-config-dialog.png` | Devices > Show Configuration | WireGuard config text + QR code side by side | device-management.md |
| `device-cards.png` | `/frontend/devices` (with devices) | 2-3 device cards with status and stats | device-management.md |

## Tips

- Use dark mode OFF for screenshots (better readability in docs)
- Ensure sample data looks realistic (not "test123" etc.)
- Crop browser chrome — show only the app content
- Consistent viewport width (1280px)
