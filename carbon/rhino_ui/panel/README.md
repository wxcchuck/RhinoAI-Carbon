# WLCA panel (new interface)

Drafted by an AI agent (Claude) - review before trusting.

React + Tailwind CSS v4 + [shadcn/ui](https://ui.shadcn.com) components + [Lucide](https://lucide.dev) icons,
built with Vite into **one self-contained page**: `../web_next/index.html` (scripts, styles and the IBM Plex
Sans font inlined). Rhino loads it from the package folder over `file://`, where separate module scripts are
blocked, and the page fetches nothing at runtime. The built page is committed so packaging needs no Node.js.

```
npm install
npm run build        # writes ../web_next/index.html
npm run typecheck
```

## How it talks to Rhino

Same messages as the current page (`../web/app.js`), handled by `../wlca_web.py`:

- page → Rhino: `{type: "ready"}`, `{type: "set", path, value, kind}`, `{type: "action", name, args}`
- Rhino → page: `window.wlca.receive(model)`

The page keeps no assessment logic: Python checks every value and sends the whole model back.
See `src/lib/bridge.ts` and `src/lib/model.ts`.

## Layout

- `src/App.tsx`: sidebar of steps (collapses to icons below 760 px), header with the theme switch, Back / Next.
- `src/pages/`: one component per step (steps 3-5 share the option picker). Steps not moved yet show `PendingPage`, which opens that step in
  the current interface.
- `src/components/form.tsx`: fields wired to Rhino (text fields send on blur or Enter; Escape puts the
  saved value back).
- `src/components/ui/`: shadcn/ui components copied from the shadcn repository (MIT); see the README there.
- `src/index.css`: theme tokens (light and dark).

## Trying it in Rhino

"Try the new interface" at the bottom of the current panel's step list switches to this page; "Back to the
current interface" switches back. The choice is remembered per PC (`wlca_user.json`, key `ui`).
