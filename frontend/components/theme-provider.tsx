"use client";

import { createContext, useContext, useEffect, useMemo, useSyncExternalStore } from "react";

export type Theme = "light" | "dark";

type ThemeContextValue = {
  theme: Theme;
  setTheme: (theme: Theme) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const theme = useSyncExternalStore<Theme>(subscribe, getThemeSnapshot, () => "light");

  function setTheme(nextTheme: Theme) {
    window.localStorage.setItem("medprice-theme", nextTheme);
    window.dispatchEvent(new Event("medprice-theme-change"));
  }

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  const value = useMemo(() => ({ theme, setTheme }), [theme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener("medprice-theme-change", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("medprice-theme-change", callback);
  };
}

function getThemeSnapshot(): Theme {
  return window.localStorage.getItem("medprice-theme") === "dark" ? "dark" : "light";
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }
  return context;
}
