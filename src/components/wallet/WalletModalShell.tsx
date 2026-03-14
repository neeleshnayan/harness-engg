"use client";

import React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { cn } from "@/lib/utils";

interface WalletModalShellProps {
  open: boolean;
  onDismiss: () => void;
  children: React.ReactNode;
  screenReaderTitle?: string;
  contentClassName?: string;
  contentStyle?: React.CSSProperties;
  onContentClick?: React.MouseEventHandler<HTMLDivElement>;
}

const overlayStyle: React.CSSProperties = {
  backgroundColor: "hsl(var(--brand-bg) / 0.66)",
};

export default function WalletModalShell({
  open,
  onDismiss,
  children,
  screenReaderTitle = "Wallet modal",
  contentClassName,
  contentStyle,
  onContentClick,
}: WalletModalShellProps) {
  return (
    <DialogPrimitive.Root
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) onDismiss();
      }}
    >
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay
          className="fixed inset-0 z-50 backdrop-blur-xl data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0"
          style={overlayStyle}
        />
        <DialogPrimitive.Content
          className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto p-4 focus:outline-none focus:ring-0"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              onDismiss();
            }
          }}
        >
          <DialogPrimitive.Title className="sr-only">
            {screenReaderTitle}
          </DialogPrimitive.Title>
          <div
            className={cn("w-full", contentClassName)}
            style={contentStyle}
            onClick={onContentClick}
          >
            {children}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
