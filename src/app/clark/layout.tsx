import type { ReactNode } from "react";
import "./studio/studio-theme.css";
import { StudioThemeProvider, ThemeNoFlashScript } from "./studio/ThemeToggle";

/**
 * Clark shell — the same design system as the Studio it sits beside.
 *
 * The Studio scopes its theme deliberately, because the wallet and customer
 * surfaces have their own look and should not inherit it. Clark was left
 * outside that scope and grew a third language: a hardcoded #001C1B teal, a
 * neon glow under the logo, and greys built from white/80, white/10, white/5
 * rather than tokens.
 *
 * That is one product too many. Clark and the Studio are the same tool — you
 * move between them mid-thought — and two palettes across one workflow reads
 * as two half-finished things rather than one considered one.
 *
 * Nesting is intentional and harmless: /clark/studio has its own copy of this
 * shell, and applying the same attribute twice is idempotent.
 */
export default function ClarkLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <ThemeNoFlashScript />
      <StudioThemeProvider>{children}</StudioThemeProvider>
    </>
  );
}
