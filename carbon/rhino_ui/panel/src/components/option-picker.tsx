// The option a per-option step (3 to 5) shows. Drafted by an AI agent (Claude) - review before trusting.
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { Choice } from "@/components/form"
import type { Model } from "@/lib/model"

export function OptionPicker({ m, sel, setSel }: { m: Model; sel: number; setSel: (i: number) => void }) {
  const opts = m.state.options
  if (opts.length < 2) return null
  return (
    <div className="mb-6 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border bg-card px-3 py-2.5">
      <span className="text-sm font-medium">Design option</span>
      {opts.length <= 5 ? (
        <ToggleGroup type="single" variant="outline" size="sm" value={String(sel)}
          onValueChange={(v) => v !== "" && setSel(Number(v))} aria-label="Design option">
          {opts.map((o, i) => (
            <ToggleGroupItem key={i} value={String(i)} className="min-w-12 px-3 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground">
              {o.name || `Option ${i + 1}`}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      ) : (
        <div className="w-64">
          <Choice value={String(sel)} options={opts.map((o, i) => [String(i), o.name || `Option ${i + 1}`] as [string, string])}
            onChange={(v) => setSel(Number(v))} aria-label="Design option" />
        </div>
      )}
      <span className="text-xs text-muted-foreground">Settings on this step apply to the option chosen here.</span>
    </div>
  )
}
