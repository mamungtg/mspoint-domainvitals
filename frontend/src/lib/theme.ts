import { useEffect, useState } from "react";
import { load, save } from "./storage";

export type Theme = "light" | "dark";
const KEY = "dv.theme";

export function initialTheme(): Theme {
  const stored = load(KEY);
  if (stored === "light" || stored === "dark") return stored;
  try { return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; } catch { return "light"; }
}

export function applyTheme(t: Theme) {
  document.documentElement.dataset.theme = t;
}

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => (document.documentElement.dataset.theme as Theme) || initialTheme());
  useEffect(() => { applyTheme(theme); }, [theme]);
  const toggle = () => setTheme((t) => { const n = t === "dark" ? "light" : "dark"; save(KEY, n); return n; });
  return [theme, toggle];
}
