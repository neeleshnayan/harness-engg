import type { ReactNode } from "react";
import { KT_BODY_BG } from "./theme";

/**
 * Studio is a DARK-ONLY surface (the "Your Position" design system).
 *
 * The rest of KryptonPay (wallet, customer, business) is light, so we cannot set
 * `dark` on <html> globally. Instead we scope it here:
 *  - `dark` makes the shared CSS variables in globals.css resolve to their dark
 *    values for anything rendered inside Studio.
 *  - the inline body rule kills the white seam: globals.css defaults
 *    `--background` to white at :root and body does `@apply bg-background`, so
 *    without this, overscroll / short pages flash white behind the Studio ground.
 *
 * There is no light/dark toggle by design — do not reintroduce `theme` props.
 */
export default function StudioLayout({ children }: { children: ReactNode }) {
  return (
    <div className="dark" style={{ backgroundColor: KT_BODY_BG, minHeight: "100vh" }}>
      <style>{`body { background-color: ${KT_BODY_BG}; }`}</style>
      {children}
    </div>
  );
}
