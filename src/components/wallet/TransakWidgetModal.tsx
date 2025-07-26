import React, { useEffect, useRef } from "react";
import type { FC, MouseEvent } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface TransakWidgetModalProps {
  visible: boolean;
  onClose: () => void;
  userDetails?: {
    walletAddress?: string;
    email?: string;
  };
}

const TRANSAK_API_KEY = "f4c10825-55fd-4ccc-bd3f-40fc021468e5"; // Placeholder

function buildTransakUrl(userDetails?: {
  walletAddress?: string;
  email?: string;
}) {
  let url = `https://global-stg.transak.com?apiKey=${TRANSAK_API_KEY}&environment=STAGING`;
  if (userDetails) {
    if (userDetails.walletAddress) {
      url += `&walletAddress=${encodeURIComponent(userDetails.walletAddress)}`;
    }
    if (userDetails.email) {
      url += `&userData.email=${encodeURIComponent(userDetails.email)}`;
    }
  }
  console.log(userDetails?.walletAddress);
  console.log(userDetails?.email);
  console.log(url);
  return url;
}

const TransakWidgetModal: FC<TransakWidgetModalProps> = ({ visible, onClose, userDetails }: TransakWidgetModalProps) => {
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (visible) {
      document.addEventListener("keydown", handleKeyDown);
    } else {
      document.removeEventListener("keydown", handleKeyDown);
    }
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [visible, onClose]);

  if (!visible) return null;
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
            src={buildTransakUrl(userDetails)}
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