import React, { useEffect, useRef } from "react";
import type { FC, MouseEvent } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface TransakWidgetModalProps {
  walletAddress?: string;
  onClose: () => void;
}

const TRANSAK_API_KEY = "d4058393-4a33-4370-bf9a-e098bf2b58a1"; // Placeholder
const TRANSAK_URL = `https://global-stg.transak.com?apiKey=${TRANSAK_API_KEY}&environment=STAGING`;

const TransakWidgetModal: FC<TransakWidgetModalProps> = ({ walletAddress, onClose }: TransakWidgetModalProps) => {
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <Card
        className="w-full max-w-2xl bg-zinc-900/95 border border-zinc-800 shadow-2xl relative overflow-hidden"
        onClick={(e: MouseEvent<HTMLDivElement>) => e.stopPropagation()}
        ref={modalRef}
      >
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-xl font-bold text-white">Buy Crypto (Transak)</CardTitle>
          <Button variant="outline" size="sm" onClick={onClose} className="ml-2">Close</Button>
        </CardHeader>
        <CardContent className="p-0">
          <iframe
            src={TRANSAK_URL}
            title="Transak Widget"
            width="100%"
            height="600px"
            allow="camera;microphone;clipboard-read;clipboard-write"
            style={{ border: "none", borderRadius: "0 0 0.5rem 0.5rem", background: "#18181b" }}
          />
        </CardContent>
      </Card>
    </div>
  );
};

export default TransakWidgetModal; 