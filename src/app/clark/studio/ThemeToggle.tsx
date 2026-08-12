"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { KT, KT_DEFAULT_THEME, KT_THEME_STORAGE_KEY, type KtTheme } from "./theme";

const ThemeCtx = createContext<{ theme: KtTheme; toggle: () => void }>({
  theme: KT_DEFAULT_THEME,
  toggle: () => {},
});

export const useKtTheme = () => useContext(ThemeCtx);

/**
 * Owns the Studio's light/dark state.
 *
 * Components never read this — they style from KT tokens, which resolve through
 * the CSS variables swapped by `data-kt-theme` here. The context exists only for
 * the toggle button itself and for chart libraries that need literal colors.
 */
export function StudioThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<KtTheme>(KT_DEFAULT_THEME);

  // Adopt the persisted choice after mount (the inline script below has already
  // painted the correct theme, so this only syncs React state).
  useEffect(() => {
    const stored = window.localStorage.getItem(KT_THEME_STORAGE_KEY);
    if (stored === "light" || stored === "dark") setTheme(stored);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-kt-theme", theme);
    return () => document.documentElement.removeAttribute("data-kt-theme");
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((t) => {
      const next: KtTheme = t === "dark" ? "light" : "dark";
      window.localStorage.setItem(KT_THEME_STORAGE_KEY, next);
      return next;
    });
  }, []);

  return <ThemeCtx.Provider value={{ theme, toggle }}>{children}</ThemeCtx.Provider>;
}

/**
 * Runs before paint so a light-mode user never sees a dark flash (and vice
 * versa). Must stay in sync with KT_THEME_STORAGE_KEY / KT_DEFAULT_THEME.
 */
export function ThemeNoFlashScript() {
  const js = `(function(){try{var t=localStorage.getItem(${JSON.stringify(
    KT_THEME_STORAGE_KEY,
  )});document.documentElement.setAttribute('data-kt-theme',(t==='light'||t==='dark')?t:${JSON.stringify(
    KT_DEFAULT_THEME,
  )});}catch(e){document.documentElement.setAttribute('data-kt-theme',${JSON.stringify(
    KT_DEFAULT_THEME,
  )});}})();`;
  return <script dangerouslySetInnerHTML={{ __html: js }} />;
}

export function ThemeToggle() {
  const { theme, toggle } = useKtTheme();
  const nextLabel = theme === "dark" ? "light" : "dark";
  return (
    <button
      onClick={toggle}
      className={`flex h-8 w-8 items-center justify-center ${KT.btnGhost} px-0`}
      title={`Switch to ${nextLabel} mode`}
      aria-label={`Switch to ${nextLabel} mode`}
    >
      {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
    </button>
  );
}
