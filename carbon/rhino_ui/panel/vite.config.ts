// WLCA panel build. Drafted by an AI agent (Claude) - review before trusting.
// One self-contained index.html (scripts, styles and fonts inlined): Rhino loads it from the package
// folder over file://, where separate module scripts would be blocked, and nothing is fetched at runtime.
import { fileURLToPath } from "node:url"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { viteSingleFile } from "vite-plugin-singlefile"

export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss(), viteSingleFile()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  build: { outDir: "../web_next", emptyOutDir: true, assetsInlineLimit: 100_000_000, target: "es2020" },
})
