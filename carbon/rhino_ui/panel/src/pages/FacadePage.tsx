// Step 5: façade types and their shares, per option. Drafted by an AI agent (Claude) - review before trusting.
import { CircleCheck, Plus, Trash, TriangleAlert } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Note, Section } from "@/components/blocks"
import { Choice, TextInput } from "@/components/form"
import { OptionPicker } from "@/components/option-picker"
import { act } from "@/lib/bridge"
import { pct, type PageProps } from "@/lib/model"
import { cn } from "@/lib/utils"

type FacadeRow = { build_up: string; kind: string; share: number | null; wwr: number | null }
type FacadeType = { id: string; code: string; label: string; kind: string }
const MAX_TYPES = 3
const COLS = "grid-cols-[minmax(0,1fr)_2rem] @2xl/main:grid-cols-[minmax(0,1fr)_7rem_8.5rem_2.25rem]"

export function FacadePage({ m, sel, setSel }: PageProps) {
  const i = Math.min(sel, m.state.options.length - 1)
  const rows = m.state.options[i].facade as FacadeRow[]
  const cat = (m.lists.facade_types as FacadeType[]) || []
  const punched = rows.some((f) => f.kind !== "unitised")
  const total = rows.reduce((a, f) => a + (Number(f.share) || 0), 0)
  const ok = Math.abs(total - 1) < 0.005
  return (
    <div className="space-y-8">
      <OptionPicker m={m} sel={i} setSel={setSel} />
      <Section title="Façade types and their share" code="2.5, 2.6"
        lead="Up to three types. Shares are of the whole net façade and must add up to 100%. Curtain-wall types carry their glazing in the system; other types take a glazing ratio.">
        <div className="overflow-hidden rounded-lg border bg-card">
          <div className={cn("hidden gap-3 border-b bg-muted/60 px-3 py-2 text-xs font-medium text-muted-foreground @2xl/main:grid", COLS)}>
            <span>Type, from the office library<span className="text-destructive">*</span></span>
            <span>Share<span className="text-destructive">*</span></span>
            <span>Glazing ratio{punched && <span className="text-destructive">*</span>}</span>
            <span />
          </div>
          <ul className="divide-y">
            {rows.map((f, j) => (
              <li key={j} className={cn("grid items-center gap-x-3 gap-y-2 px-3 py-2.5", COLS)}>
                <Choice value={f.build_up} aria-label="Façade type"
                  options={cat.map((c) => [c.id, `${c.label} (${c.code})`] as [string, string])}
                  onChange={(v) => act("facade_type", { i, j, id: v })} />
                <Button type="button" variant="ghost" size="icon" className="size-8 text-muted-foreground @2xl/main:order-last"
                  disabled={rows.length < 2} aria-label="Remove this type" title="Remove this type"
                  onClick={() => act("remove_facade", { i, j })}>
                  <Trash />
                </Button>
                <div className="col-span-2 grid grid-cols-2 gap-3 @2xl/main:contents">
                  <label className="grid gap-1 text-xs text-muted-foreground @2xl/main:block">
                    <span className="@2xl/main:sr-only">Share</span>
                    <TextInput path={["options", i, "facade", j, "share"]} value={pct(f.share)} kind="pct" numeric aria-label="Share" />
                  </label>
                  <label className="grid gap-1 text-xs text-muted-foreground @2xl/main:block">
                    <span className="@2xl/main:sr-only">Glazing ratio</span>
                    {f.kind === "unitised"
                      ? <span className="flex h-8 items-center text-sm text-muted-foreground">In the system</span>
                      : <TextInput path={["options", i, "facade", j, "wwr"]} value={pct(f.wwr)} kind="pct" numeric aria-label="Glazing ratio" />}
                  </label>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button type="button" variant="outline" size="sm" disabled={rows.length >= MAX_TYPES} onClick={() => act("add_facade", { i })}>
            <Plus />Add a type
          </Button>
          <span role="status" className={cn("num inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-sm",
            ok ? "bg-good-soft text-good" : "bg-error-soft text-destructive")}>
            {ok ? <CircleCheck className="size-4" /> : <TriangleAlert className="size-4" />}
            Shares add up to {Math.round(total * 100)}%
          </span>
        </div>
        <Note>The list shows the façade types in the office library. A new type is added to the library once and then appears here for every project.</Note>
      </Section>
    </div>
  )
}
