// WLCA panel: the steps down the side, the step's page, Back / Next. Drafted by an AI agent (Claude) - review before trusting.
import { useEffect, useRef, useState, type ComponentType } from "react"
import {
  ArrowDownToLine, Building, ChartColumnBig, ChevronLeft, ChevronRight, ClipboardList, Columns3, LoaderCircle,
  Monitor, Moon, Play, Sheet, Sun, Target, Undo2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarHeader, SidebarInset, SidebarMenu, SidebarMenuButton,
  SidebarMenuItem, SidebarProvider, SidebarSeparator, SidebarTrigger,
} from "@/components/ui/sidebar"
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuLabel, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { act, consumeJump, ready, useBridge } from "@/lib/bridge"
import { stepFlags, type Model, type PageProps } from "@/lib/model"
import { useTheme, type ThemeChoice } from "@/lib/theme"
import { cn } from "@/lib/utils"
import { ProjectPage } from "@/pages/ProjectPage"
import { DrawingsPage } from "@/pages/DrawingsPage"
import { SubstructurePage } from "@/pages/SubstructurePage"
import { StructurePage } from "@/pages/StructurePage"
import { FacadePage } from "@/pages/FacadePage"
import { TargetsPage } from "@/pages/TargetsPage"
import { RunPage } from "@/pages/RunPage"
import { PendingPage } from "@/pages/PendingPage"

const ICONS: ComponentType<{ className?: string }>[] = [ClipboardList, Sheet, ArrowDownToLine, Columns3, Building, Target, Play, ChartColumnBig]
const PAGES: (ComponentType<PageProps> | null)[] = [ProjectPage, DrawingsPage, SubstructurePage, StructurePage, FacadePage, TargetsPage, RunPage, null]
const REQUIRED = new Set([0, 2, 4, 5])      // steps with fields marked * (the line explaining the marker shows there)
const WIDE = 760          // below this panel width the step list starts collapsed to icons

function initialStep(): number {
  const hit = /step=(\d)/.exec(window.location.hash)
  return hit ? Number(hit[1]) : 0
}

export default function App() {
  const { model: m, busy } = useBridge()
  const [step, setStep] = useState(initialStep)
  const [sel, setSel] = useState(0)          // option shown on steps 3 to 5, kept while moving between them
  const [open, setOpen] = useState(() => window.innerWidth >= WIDE)
  const [theme, setTheme] = useTheme()
  const main = useRef<HTMLDivElement>(null)

  useEffect(() => ready(), [])
  useEffect(() => {            // Rhino opens a step with #step=N (switching from the current interface)
    const onHash = () => setStep(initialStep())
    window.addEventListener("hashchange", onHash)
    return () => window.removeEventListener("hashchange", onHash)
  }, [])
  useEffect(() => {            // follow the panel width across the threshold; a manual toggle holds until the next crossing
    let wide = window.innerWidth >= WIDE
    const onResize = () => {
      const now = window.innerWidth >= WIDE
      if (now !== wide) setOpen(now)
      wide = now
    }
    window.addEventListener("resize", onResize)
    return () => window.removeEventListener("resize", onResize)
  }, [])
  const last = m ? m.steps.length - 1 : 7
  useEffect(() => {
    if (m?.calc?.status === "done" && consumeJump()) setStep(last)
  }, [m, last])
  useEffect(() => {
    if (m) document.title = m.title
  }, [m])

  const go = (i: number) => {
    setStep(Math.max(0, Math.min(last, i)))
    main.current?.scrollTo({ top: 0 })
  }

  if (!m) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">
        {busy || "Open this panel from Rhino with the WLCA command."}
      </div>
    )
  }

  const flags = stepFlags(m)
  const Page = PAGES[step]
  const running = m.calc?.status === "running"
  const status = busy || (running ? "Excel is calculating…" : "")

  return (
    <SidebarProvider open={open} onOpenChange={setOpen} className="h-full min-h-0">
      <Sidebar collapsible="icon">
        <SidebarHeader className="gap-0 px-3 pt-3 pb-2 group-data-[collapsible=icon]:px-2">
          <div className="flex items-center gap-2.5">
            <div className="grid size-8 shrink-0 place-items-center rounded-md bg-sidebar-primary text-[0.8rem] font-semibold tracking-tight text-sidebar-primary-foreground">
              WL
            </div>
            <div className="min-w-0 group-data-[collapsible=icon]:hidden">
              <div className="truncate text-sm font-semibold leading-tight">{m.state.project.name || "Untitled project"}</div>
              <div className="truncate text-xs text-muted-foreground">
                {optionCount(m)}
              </div>
            </div>
          </div>
        </SidebarHeader>
        <SidebarContent>
          <SidebarGroup className="py-1">
            <nav aria-label="Steps">
              <SidebarMenu className="relative gap-0.5">
                {m.steps.map((title, i) => {
                  const Icon = ICONS[i] ?? ClipboardList
                  const isResults = i === last
                  return (
                    <SidebarMenuItem key={i} className={cn(isResults && "mt-2")}>
                      {isResults && <SidebarSeparator className="mx-0 mb-2" />}
                      <SidebarMenuButton isActive={i === step} tooltip={isResults ? title : `${i + 1}. ${title}`}
                        onClick={() => go(i)} className="h-9 data-[active=true]:bg-sidebar-primary data-[active=true]:text-sidebar-primary-foreground">
                        <Icon />
                        <span className="flex min-w-0 flex-1 items-baseline gap-1.5">
                          {!isResults && <span className="num w-3.5 shrink-0 text-xs opacity-60">{i + 1}</span>}
                          <span className="truncate">{title}</span>
                        </span>
                        {flags.has(i) && (
                          <span className="ml-auto size-2 shrink-0 rounded-full bg-destructive group-data-[collapsible=icon]:absolute group-data-[collapsible=icon]:top-1 group-data-[collapsible=icon]:right-1"
                            title="Something to fix on this step" />
                        )}
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  )
                })}
              </SidebarMenu>
            </nav>
          </SidebarGroup>
        </SidebarContent>
        <SidebarFooter className="px-2 pb-3">
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton tooltip="Back to the current interface" className="text-muted-foreground"
                onClick={() => act("switch_ui", { ui: "classic", step }, "Opening the current interface…")}>
                <Undo2 />
                <span>Back to the current interface</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
      </Sidebar>

      <SidebarInset className="flex h-full min-h-0 min-w-0 flex-col">
        <header className="flex h-12 shrink-0 items-center gap-2 border-b bg-background px-3">
          <SidebarTrigger className="-ml-1" />
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-base font-semibold">
              {step < last && <span className="num mr-1 font-normal text-muted-foreground">{step + 1} of {last}{" "}</span>}
              {m.steps[step]}
            </h1>
          </div>
          <ThemeMenu theme={theme} setTheme={setTheme} />
        </header>

        <div ref={main} className="@container/main min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-5xl px-4 py-5 @2xl/main:px-6">
            {Page && REQUIRED.has(step) && (
              <p className="mb-5 text-xs text-muted-foreground"><span className="text-destructive">*</span> Needed to run the assessment; everything else has a default or is optional.</p>
            )}
            {/* while Rhino works on an action, every control on the page waits (a disabled fieldset disables them all) */}
            <fieldset disabled={!!busy} className="m-0 min-w-0 border-0 p-0">
              {Page ? <Page m={m} sel={sel} setSel={setSel} goTo={go} /> : <PendingPage step={step} title={m.steps[step]} />}
            </fieldset>
          </div>
        </div>

        <footer className="flex h-12 shrink-0 items-center gap-2 border-t bg-background px-3">
          <div className="flex min-w-0 flex-1 items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
            {status && <LoaderCircle className="size-4 shrink-0 animate-spin text-primary" aria-hidden />}
            <span className="truncate">{status}</span>
          </div>
          <Button type="button" variant="outline" size="sm" disabled={step === 0 || !!busy} onClick={() => go(step - 1)}>
            <ChevronLeft />Back
          </Button>
          <Button type="button" size="sm" disabled={step === last || !!busy} onClick={() => go(step + 1)}>
            Next<ChevronRight />
          </Button>
        </footer>
      </SidebarInset>
    </SidebarProvider>
  )
}

function optionCount(m: Model) {
  const n = m.state.options.filter((o) => o.include).length
  return n === 1 ? "1 design option" : `${n} design options`
}

function ThemeMenu({ theme, setTheme }: { theme: ThemeChoice; setTheme: (t: ThemeChoice) => void }) {
  const Icon = theme === "dark" ? Moon : theme === "light" ? Sun : Monitor
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button type="button" variant="ghost" size="icon" className="size-8" aria-label="Theme" title="Theme">
          <Icon />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44">
        <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">Theme</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={theme} onValueChange={(v) => setTheme(v as ThemeChoice)}>
          <DropdownMenuRadioItem value="light"><Sun />Light</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="dark"><Moon />Dark</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="system"><Monitor />Follow Windows</DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
