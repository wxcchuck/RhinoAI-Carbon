// Steps not yet moved to the new panel. Drafted by an AI agent (Claude) - review before trusting.
import { Undo2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Section } from "@/components/blocks"
import { act } from "@/lib/bridge"

export function PendingPage({ step, title }: { step: number; title: string }) {
  return (
    <Section title={title}
      lead="This step is still being moved to the new interface. Its settings are saved with the model as before, so you can set them in the current interface and come back.">
      <Button type="button" variant="outline" size="sm" onClick={() => act("switch_ui", { ui: "classic", step }, "Opening the current interface…")}>
        <Undo2 />Open this step in the current interface
      </Button>
    </Section>
  )
}
