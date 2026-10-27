// Chart frames, legends and verdict badges for the Results page. Drafted by an AI agent (Claude) - review before trusting.
import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

/** An SVG chart string from lib/charts.ts (built from numbers and escaped labels only). */
export function Svg({ html, className }: { html: string; className?: string }) {
  return <div className={cn("min-w-0 [&>svg]:block [&>svg]:h-auto", className)} dangerouslySetInnerHTML={{ __html: html }} />
}

/** A results card: title, optional controls on the right, the chart, a note underneath. */
export function ChartCard({ title, children, note, aside, wide, className }: {
  title: string
  children: ReactNode
  note?: ReactNode
  aside?: ReactNode
  wide?: boolean
  className?: string
}) {
  return (
    <section className={cn("min-w-0 rounded-lg border bg-card p-4", wide && "@3xl/main:col-span-2", className)}>
      <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        <h2 className="text-base font-semibold">{title}</h2>
        {aside && <div className="ml-auto flex flex-wrap gap-2">{aside}</div>}
      </div>
      {children}
      {note && <p className="mt-3 max-w-[80ch] text-xs leading-relaxed text-muted-foreground">{note}</p>}
    </section>
  )
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  const seen = new Set<string>()
  return (
    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
      {items.filter((it) => !seen.has(it.label) && seen.add(it.label)).map((it) => (
        <li key={it.label} className="inline-flex items-center gap-1.5">
          <span className="size-2.5 shrink-0 rounded-[3px]" style={{ background: it.color }} aria-hidden />
          {it.label}
        </li>
      ))}
    </ul>
  )
}

export function LineLegend({ items }: { items: { label: string; color: string; dash?: boolean; dot?: boolean }[] }) {
  return (
    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
      {items.map((it) => (
        <li key={it.label} className="inline-flex items-center gap-1.5">
          <svg width="26" height="10" aria-hidden>
            <line x1="1" x2="25" y1="5" y2="5" stroke={it.color} strokeWidth="2.4"
              strokeDasharray={it.dot ? "1.5 3.5" : it.dash ? "6 3" : undefined} strokeLinecap={it.dot ? "round" : undefined} />
          </svg>
          {it.label}
        </li>
      ))}
    </ul>
  )
}

const VERDICT: Record<string, string> = {
  Meets: "bg-good-soft text-good",
  "Meets before contingency only": "bg-warn-soft text-warn",
  Above: "bg-error-soft text-destructive",
}
export function Verdict({ v }: { v: string }) {
  return <span className={cn("inline-flex rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap", VERDICT[v] || "bg-muted text-muted-foreground")}>{v}</span>
}
export function VerdictDot({ v }: { v: string }) {
  const c = v === "Meets" ? "bg-good" : v === "Above" ? "bg-destructive" : v.startsWith("Meets before") ? "bg-warn" : "bg-muted-foreground/40"
  return <span className={cn("inline-block size-2 shrink-0 rounded-full", c)} aria-label={v} />
}

/** A headline figure. */
export function Tile({ title, value, unit, sub }: { title: string; value: string; unit: string; sub?: string }) {
  return (
    <div className="min-w-0 rounded-lg border bg-card px-4 py-3">
      <div className="text-xs text-muted-foreground">{title}</div>
      <div className="num mt-1 text-2xl font-semibold tracking-tight">{value}</div>
      <div className="mt-0.5 text-xs text-muted-foreground">{unit}{sub && <span className="block">{sub}</span>}</div>
    </div>
  )
}
