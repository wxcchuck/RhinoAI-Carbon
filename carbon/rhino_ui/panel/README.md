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
- `src/pages/`: one component per step (steps 3-5 share the option picker). `PendingPage` is a fallback for a step without a page (none at present); it opens
  that step in the classic interface.
- `src/pages/ResultsPage.tsx` and `src/pages/results/`: headline tiles, against targets, basis, element groups, modules,
  whole life by stage, the trajectory (option and compare). The bar charts and the doughnut are shadcn/ui charts
  (Recharts, `src/components/charts.tsx`, with tooltips); against targets, whole life by stage and the trajectory are still SVG strings from `src/lib/charts.ts`, ported from
  `../web/charts.js` with the same geometry; text, grid and halo colours follow the theme, data colours the office
  branding (lines and coloured labels are lightened on the dark theme).
- `src/components/form.tsx`: fields wired to Rhino (text fields send on blur or Enter; Escape puts the
  saved value back).
- `src/components/ui/`: shadcn/ui components copied from the shadcn repository (MIT); see the README there.
- `src/index.css`: theme tokens (light and dark).

## In Rhino

This page is the default interface. "Use the classic interface" at the bottom of the step list switches to
`../web/` (the plain HTML / JavaScript panel), and "Try the new interface" there switches back. Only a choice of
the classic interface is stored, per PC (`wlca_user.json`, key `ui`).
