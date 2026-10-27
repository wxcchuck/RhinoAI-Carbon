// Page building blocks. Drafted by an AI agent (Claude) - review before trusting.
import type { ReactNode } from "react"
import { CircleCheck, CircleX, Info, TriangleAlert } from "lucide-react"
import { cn } from "@/lib/utils"

/** A titled part of a step: the title says what is set here, the lead line why it matters. */
export function Section({ title, code, lead, children, className, aside }: {
  title: string
  code?: string            // RICS element code(s) the section feeds, e.g. "1.2.3"
  lead?: ReactNode
  children?: ReactNode
  className?: string
  aside?: ReactNode
}) {
  return (
    <section className={cn("border-t border-border pt-5 first:border-t-0 first:pt-0", className)}>
      <div className="mb-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h2 className="text-lg font-semibold tracking-[-0.005em]">
          {title}
          {code && <span className="num ml-2 text-sm font-normal text-muted-foreground" title="RICS element code">{code}</span>}
        </h2>
        {aside && <div className="ml-auto">{aside}</div>}
      </div>
      {lead && <p className="mb-4 max-w-[72ch] text-sm leading-relaxed text-muted-foreground">{lead}</p>}
      {children}
    </section>
  )
}

export function Note({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cn("mt-3 max-w-[72ch] text-xs leading-relaxed text-muted-foreground", className)}>{children}</p>
}

const TONE = {
  note: { icon: Info, cls: "bg-muted text-foreground [&>svg]:text-muted-foreground" },
  good: { icon: CircleCheck, cls: "bg-good-soft text-foreground [&>svg]:text-good" },
  warn: { icon: TriangleAlert, cls: "bg-warn-soft text-foreground [&>svg]:text-warn" },
  error: { icon: CircleX, cls: "bg-error-soft text-foreground [&>svg]:text-destructive" },
} as const

/** A status line: what was read, what is missing, what to fix. */
export function Notice({ tone = "note", children, className, action }: {
  tone?: keyof typeof TONE
  children: ReactNode
  className?: string
  action?: ReactNode
}) {
  const T = TONE[tone]
  const Icon = T.icon
  return (
    <div role={tone === "error" || tone === "warn" ? "alert" : "status"}
      className={cn("mt-3 flex items-start gap-2.5 rounded-md px-3 py-2.5 text-sm leading-relaxed", T.cls, className)}>
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1 break-words whitespace-pre-line">{children}</div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

/** Fields in a responsive grid: one column when docked narrow, up to three when wide. */
export function FieldGrid({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("grid grid-cols-1 gap-x-5 gap-y-4 @md/main:grid-cols-2 @3xl/main:grid-cols-3", className)}>{children}</div>
}
