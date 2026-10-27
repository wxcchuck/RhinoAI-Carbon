// Light / dark / follow Windows. Drafted by an AI agent (Claude) - review before trusting.
// The choice is a per-PC convenience kept in the WebView's local storage; without it the panel follows Windows.
import { useEffect, useState } from "react"

export type ThemeChoice = "light" | "dark" | "system"
const KEY = "wlca.theme"

function stored(): ThemeChoice {
  try {
    const v = window.localStorage.getItem(KEY)
    return v === "light" || v === "dark" ? v : "system"
  } catch {
    return "system"
  }
}

export function useTheme(): [ThemeChoice, (t: ThemeChoice) => void] {
  const [choice, setChoice] = useState<ThemeChoice>(stored)
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)")
    const apply = () => {
      const dark = choice === "dark" || (choice === "system" && mq.matches)
      document.documentElement.classList.toggle("dark", dark)
      document.documentElement.style.colorScheme = dark ? "dark" : "light"
    }
    apply()
    mq.addEventListener("change", apply)
    return () => mq.removeEventListener("change", apply)
  }, [choice])
  const set = (t: ThemeChoice) => {
    setChoice(t)
    try {
      if (t === "system") window.localStorage.removeItem(KEY)
      else window.localStorage.setItem(KEY, t)
    } catch {
      /* storage unavailable: the choice lasts until the panel reloads */
    }
  }
  return [choice, set]
}
