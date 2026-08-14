"use client";

import React, { useCallback, useEffect, useRef } from "react";
import { ArrowUpRight, Check, Copy, ListChecks, LogOut, X } from "lucide-react";
import { useRouter } from "next/navigation";

interface HamburgerMenuProps {
  visible: boolean;
  onClose: () => void;
  onLogout: () => void;
  accountData: any;
  onCopyAddress: () => void;
  onOpenQuestionnaire?: () => void;
}

/**
 * The account menu, shared by Clark, the hedge-fund pages and the wallet.
 *
 * It used to be a fourth palette: a teal-on-teal glass card with a cyan "Menu"
 * title, white/[0.06] gradient rows and a filled red Sign Out that was the
 * loudest thing on screen — for a panel whose whole job is to show an address
 * and offer two links.
 *
 * Colours come from the Krypton tokens **with dark fallbacks**, which is what
 * lets one component serve both worlds: `--kt-*` is only defined under
 * `data-kt-theme`, which only Clark routes set, so on wallet routes every value
 * falls through to the dark literal the wallet already used. Clark follows its
 * theme; the wallet is unchanged.
 */

/** Token with a fallback, so this renders correctly outside Clark's theme scope. */
const c = {
  surface: "var(--kt-surface, #14161a)",
  inset: "var(--kt-inset, #0e1013)",
  border: "var(--kt-border, #22252b)",
  borderStrong: "var(--kt-border-strong, #343941)",
  text: "var(--kt-text, #c9ccd1)",
  textStrong: "var(--kt-text-strong, #e9e7e2)",
  textDim: "var(--kt-text-dim, #9ba0a8)",
  textMuted: "var(--kt-text-muted, #6c727a)",
  down: "var(--kt-down, #ce7681)",
  hover: "var(--kt-hover, #181b20)",
};

/**
 * `0xc2857a38f2e74ab497707ba8debe816414afb90a` → `0xc2857a38…14afb90a`.
 *
 * The full string was rendered with `break-all`, which wrapped it at whatever
 * character hit the edge and left four orphans on a second line. An address is
 * read by its ends — nobody verifies the middle — so the ends are what survive.
 * The full value is still on the element's `title` and is what Copy puts on the
 * clipboard.
 */
function truncateAddress(address?: string | null): string {
  if (!address) return "";
  return address.length <= 22
    ? address
    : `${address.slice(0, 10)}…${address.slice(-8)}`;
}

const HamburgerMenu: React.FC<HamburgerMenuProps> = ({
  visible,
  onClose,
  onLogout,
  accountData,
  onCopyAddress,
  onOpenQuestionnaire,
}) => {
  const router = useRouter();
  const panelRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = React.useState(false);

  // Escape closed nothing before: the only way out was the backdrop or a close
  // button parked at the bottom of the panel, below the destructive action.
  useEffect(() => {
    if (!visible) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [visible, onClose]);

  // Move focus into the dialog so a keyboard user is not left behind it.
  useEffect(() => {
    if (visible) panelRef.current?.focus();
  }, [visible]);

  const handleCopyClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onCopyAddress();
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    },
    [onCopyAddress],
  );

  if (!visible) return null;

  const address: string | undefined = accountData?.wallet_address;

  const row =
    "flex w-full items-center gap-3 rounded-xl px-4 py-3 text-[14px] transition-colors";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label="Account menu"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[360px] rounded-2xl border p-4 shadow-[0_24px_48px_-12px_rgb(0_0_0_/_0.45)] outline-none"
        style={{ background: c.surface, borderColor: c.border }}
      >
        {/* Close sits at the top right, where a dialog's close belongs. It was
            at the bottom centre, under Sign Out — so the quickest path out of
            the menu ran past the one button you cannot undo. */}
        <div className="mb-3 flex items-center justify-between">
          <span
            className="font-mono text-[10px] uppercase tracking-[0.18em]"
            style={{ color: c.textMuted }}
          >
            Account
          </span>
          <button
            onClick={onClose}
            aria-label="Close menu"
            className="flex h-7 w-7 items-center justify-center rounded-lg transition-colors"
            style={{ color: c.textMuted }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = c.hover;
              e.currentTarget.style.color = c.textStrong;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = c.textMuted;
            }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Wallet address */}
        {address && (
          <div
            className="mb-3 flex items-center gap-2 rounded-xl border px-3 py-2.5"
            style={{ background: c.inset, borderColor: c.border }}
          >
            <span
              title={address}
              className="min-w-0 flex-1 truncate font-mono text-[13px]"
              style={{ color: c.text }}
            >
              {truncateAddress(address)}
            </span>
            <button
              onClick={handleCopyClick}
              aria-label={copied ? "Address copied" : "Copy wallet address"}
              className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg transition-colors"
              style={{ color: copied ? c.textStrong : c.textMuted }}
              onMouseEnter={(e) => (e.currentTarget.style.background = c.hover)}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            </button>
          </div>
        )}

        {/* Links */}
        <div className="flex flex-col gap-1">
          {onOpenQuestionnaire && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onClose();
                onOpenQuestionnaire();
              }}
              className={row}
              style={{ color: c.text }}
              onMouseEnter={(e) => (e.currentTarget.style.background = c.hover)}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <ListChecks className="h-4 w-4 flex-shrink-0" style={{ color: c.textMuted }} />
              <span className="flex-1 text-left">Hedge fund questionnaire</span>
            </button>
          )}

          <button
            onClick={(e) => {
              e.stopPropagation();
              onClose();
              router.push("/clark");
            }}
            className={row}
            style={{ color: c.text }}
            onMouseEnter={(e) => (e.currentTarget.style.background = c.hover)}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            {/* Was 48px, which made a menu row taller than the address above it
                and turned a link into a banner. */}
            <img src="/Krypton Clark.svg" alt="" aria-hidden className="h-4 w-4 flex-shrink-0" />
            <span className="flex-1 text-left">Clark</span>
            <ArrowUpRight className="h-3.5 w-3.5 flex-shrink-0" style={{ color: c.textMuted }} />
          </button>
        </div>

        {/* Sign out. Set apart by a rule and carrying the only colour in the
            panel — but as text, not as a filled red block that outshouted
            everything above it. */}
        <div className="mt-3 border-t pt-3" style={{ borderColor: c.border }}>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onLogout();
            }}
            className={row}
            style={{ color: c.down }}
            onMouseEnter={(e) => (e.currentTarget.style.background = c.hover)}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            <LogOut className="h-4 w-4 flex-shrink-0" />
            <span className="flex-1 text-left">Sign out</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default HamburgerMenu;
