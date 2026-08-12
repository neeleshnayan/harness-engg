import type { ReactNode } from "react";
import "./studio-theme.css";
import { StudioThemeProvider, ThemeNoFlashScript } from "./ThemeToggle";

/**
 * Studio shell.
 *
 * The rest of KryptonPay (wallet, customer, business) has its own look, so the
 * Studio theme is scoped here rather than set globally on <html> by the root
 * layout. `data-kt-theme` drives every KT token via CSS variables; the no-flash
 * script applies the stored choice before first paint.
 */
export default function StudioLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <ThemeNoFlashScript />
      <StudioThemeProvider>
        <div className="min-h-screen bg-[var(--kt-bg)] text-[var(--kt-text)]">
          {children}
        </div>
      </StudioThemeProvider>
    </>
  );
}
