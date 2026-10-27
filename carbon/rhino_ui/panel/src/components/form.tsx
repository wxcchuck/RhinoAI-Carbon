// Form controls wired to Rhino. Drafted by an AI agent (Claude) - review before trusting.
// A text field keeps what is typed until it loses focus or Enter is pressed, then sends it; Rhino parses
// and checks it (kind = text | int | num | num0 | pct) and sends the model back, which redraws the field.
import { useEffect, useRef, useState, type ReactNode } from "react"
import { FolderOpen } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { act, setValue, type Kind, type Path } from "@/lib/bridge"
import { cn } from "@/lib/utils"

const idOf = (path: Path) => "f-" + path.join("-")

export function TextInput({ path, value, kind = "text", className, numeric, placeholder, ...rest }: {
  path: Path
  value: string | number | null | undefined
  kind?: Kind
  className?: string
  numeric?: boolean
  placeholder?: string
  "aria-label"?: string
}) {
  const shown = value == null ? "" : String(value)
  const [draft, setDraft] = useState(shown)
  const focused = useRef(false)
  const cancelled = useRef(false)
  useEffect(() => {
    if (!focused.current) setDraft(shown)
  }, [shown])
  const commit = (typed: string) => {        // the field's own value: a blur straight after typing can beat the state update
    if (typed !== shown) setValue(path, typed, kind)
  }
  return (
    <Input
      id={idOf(path)}
      value={draft}
      placeholder={placeholder}
      onChange={(e) => setDraft(e.target.value)}
      onFocus={() => (focused.current = true)}
      onBlur={(e) => {
        focused.current = false
        if (cancelled.current) cancelled.current = false
        else commit(e.currentTarget.value)
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur()
        if (e.key === "Escape") {          // put the saved value back
          cancelled.current = true
          setDraft(shown)
          ;(e.target as HTMLInputElement).blur()
        }
      }}
      className={cn("h-8 bg-card dark:bg-input/30", numeric && "num", className)}
      {...rest}
    />
  )
}

const NONE = "__none__"   // Radix Select items cannot have an empty value

export type ChoiceOption = string | [string, string]
export function Choice({ value, options, onChange, placeholder = "Choose…", className, ...rest }: {
  value: string | number | null | undefined
  options: ChoiceOption[]
  onChange: (v: string) => void
  placeholder?: string
  className?: string
  disabled?: boolean
  "aria-label"?: string
  id?: string
}) {
  const opts = options.map((o) => (Array.isArray(o) ? o : [o, o])) as [string, string][]
  const cur = value == null ? "" : String(value)
  const known = opts.some(([v]) => v === cur)
  return (
    <Select value={known ? cur || NONE : undefined} onValueChange={(v) => onChange(v === NONE ? "" : v)} disabled={rest.disabled}>
      <SelectTrigger size="sm" className={cn("w-full min-w-0 bg-card", className)} aria-label={rest["aria-label"]} id={rest.id}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent position="popper" className="max-h-80">
        {opts.map(([v, l]) => (
          <SelectItem key={v || NONE} value={v || NONE}>
            {l}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

/** A Choice that writes into the saved settings. */
export function ChoiceInput({ path, kind = "text", ...p }: Omit<Parameters<typeof Choice>[0], "onChange"> & { path: Path; kind?: Kind }) {
  return <Choice {...p} id={idOf(path)} onChange={(v) => setValue(path, v, kind)} />
}

export function CheckInput({ path, checked, label }: { path: Path; checked: boolean; label?: string }) {
  return (
    <Checkbox
      id={idOf(path)}
      checked={checked}
      aria-label={label}
      onCheckedChange={(v) => setValue(path, v === true, "bool")}
    />
  )
}

/** Label above the control; `required` adds the marker the checks refer to. */
export function FormField({ label, htmlFor, required, hint, className, children }: {
  label: string
  htmlFor?: string
  required?: boolean
  hint?: ReactNode
  className?: string
  children: ReactNode
}) {
  return (
    <Field className={cn("gap-1.5", className)}>
      <FieldLabel htmlFor={htmlFor} className="text-sm font-medium">
        {label}
        {required && <span className="text-destructive" aria-label="required">*</span>}
      </FieldLabel>
      {children}
      {hint && <FieldDescription className="text-xs">{hint}</FieldDescription>}
    </Field>
  )
}

/** A file path with a Browse button (Rhino opens the dialog). */
export function PathInput({ path, value, action, args, placeholder, buttonLabel = "Browse…" }: {
  path: Path
  value: string
  action: string
  args?: Record<string, unknown>
  placeholder?: string
  buttonLabel?: string
}) {
  return (
    <div className="flex min-w-0 gap-2">
      <TextInput path={path} value={value} placeholder={placeholder} className="min-w-0 flex-1" />
      <Button type="button" variant="outline" size="sm" className="h-8 shrink-0" onClick={() => act(action, args)}>
        <FolderOpen />
        {buttonLabel}
      </Button>
    </div>
  )
}

export { idOf }
