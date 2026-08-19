# BenchPress Frontend

The Vue 3 SPA for BenchPress: labs, bench instances, deploy/build logs, and
device management. Built with Vue 3, Vue Router, TailwindCSS, and
[frappe-ui](https://frappeui.com). Served at `/frontend` on the bench.

See the root [README.md](../README.md) for what BenchPress is and how the
frontend fits into the app as a whole.

## Development

```bash
cd frontend
yarn install
yarn dev
```

The Vite dev server proxies API and socket.io requests to your bench
(`bench start` running on port 8000). Open the site's `/frontend` URL, e.g.
`http://your-site.localhost:8000/frontend`.

## Building

```bash
# from the frontend directory
yarn build

# or, from the bench
bench build --app benchpress
```

`yarn build` writes assets under `../benchpress/public/frontend/` and copies
the built `index.html` to `../benchpress/www/frontend.html`.

## Testing

```bash
yarn test:run
```

## Structure

- `src/pages/` -- routed pages (Labs, NewLab, LabDetail, BenchInstances, DeployLogs, BuildLogs, Devices, Settings)
- `src/components/` -- shared components
- `src/router.js` -- Vue Router routes
- `src/socket.js` -- socket.io client for real-time build/deploy logs
- `src/data/session.js` -- auth/session resource

## Resources

- [Frappe UI](https://github.com/frappe/frappe-ui)
- [Vue 3](https://vuejs.org/guide/introduction.html)
- [Vue Router](https://router.vuejs.org/guide/)
- [TailwindCSS](https://tailwindcss.com/docs/utility-first)
- [Vite](https://vitejs.dev/guide/)
