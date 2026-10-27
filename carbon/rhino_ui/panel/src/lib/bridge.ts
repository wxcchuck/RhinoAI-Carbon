// Bridge to Rhino. Drafted by an AI agent (Claude) - review before trusting.
//   page -> Rhino : postMessage(JSON) {type:"ready"} | {type:"set", path, value, kind} | {type:"action", name, args}
//   Rhino -> page : window.wlca.receive(model)   (wlca_web.py WLCAWindow.model)
// Same messages as the current panel (rhino_ui/web/app.js), so the Python side serves both.
// All checks and calculations happen in Python / Excel; the page only draws and forwards.
import { useSyncExternalStore } from "react"
import type { Model } from "./model"

type Host = { postMessage: (s: string) => void }
const w = window as unknown as {
  chrome?: { webview?: Host }
  eto?: Host
  wlca?: { receive: (m: Model) => void }
}
export const host: Host | null = w.chrome?.webview ?? w.eto ?? null

export type Kind = "text" | "int" | "num" | "num0" | "pct" | "bool"
export type Path = (string | number)[]

type Store = { model: Model | null; busy: string; jumpToResults: boolean }
let store: Store = { model: null, busy: "", jumpToResults: false }
const listeners = new Set<() => void>()
function update(patch: Partial<Store>) {
  store = { ...store, ...patch }
  listeners.forEach((l) => l())
}

export function send(msg: unknown) {
  if (host) host.postMessage(JSON.stringify(msg))
  else console.log("[wlca] no host:", msg)
}

/** Write one value into the saved settings; Rhino checks it and sends the model back. */
export function setValue(path: Path, value: unknown, kind: Kind = "text") {
  send({ type: "set", path, value, kind })
}

const BUSY: Record<string, string> = {
  run_takeoff: "Running the take-off in Rhino…",
  create_workbook: "Building the workbook…",
  read_plan: "Reading the plan…",
}

/** Ask Rhino to do something; the panel shows the busy line until the next model arrives. */
export function act(name: string, args: Record<string, unknown> = {}, label?: string) {
  update({
    busy: label ?? BUSY[name] ?? "Working…",
    jumpToResults: store.jumpToResults || name === "create_workbook" || name === "calculate",
  })
  send({ type: "action", name, args })
}

/** Change the model locally before Rhino answers (UI-only state that Rhino also saves). */
export function patchModel(fn: (m: Model) => Model) {
  if (store.model) update({ model: fn(store.model) })
}

export function consumeJump(): boolean {
  if (!store.jumpToResults) return false
  store = { ...store, jumpToResults: false }
  return true
}

w.wlca = {
  receive(model: Model) {
    update({ model, busy: "" })
  },
}

export function useBridge(): Store {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l)
      return () => listeners.delete(l)
    },
    () => store,
  )
}

export function ready() {
  send({ type: "ready" })
}
