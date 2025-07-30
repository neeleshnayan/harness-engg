import React, { useEffect, useRef } from "react";
import type { FC, MouseEvent } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";

interface CoinbaseCDPModalProps {
  visible: boolean;
  onClose: () => void;
  userDetails?: {
    walletAddress?: string;
    email?: string;
  };
}

// Coinbase CDP configuration
const COINBASE_APP_ID = process.env.NEXT_PUBLIC_COINBASE_APP_ID || "9688450d-ae6f-499c-a138-c64cc32550d3";
const COINBASE_ENVIRONMENT = process.env.NEXT_PUBLIC_COINBASE_ENVIRONMENT || "sandbox";

const CoinbaseCDPModal: FC<CoinbaseCDPModalProps> = ({ visible, onClose, userDetails }: CoinbaseCDPModalProps) => {
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

  // Handle Coinbase CDP events
  useEffect(() => {
    if (!visible) return;

    const handleMessage = (event: MessageEvent) => {
      // Handle messages from Coinbase CDP
      if (event.origin !== "https://pay.coinbase.com") return;

      const { type, data } = event.data;

      switch (type) {
        case "coinbase-pay:close":
          onClose();
          break;
        case "coinbase-pay:success":
          console.log("Payment successful:", data);
          onClose();
          break;
        case "coinbase-pay:error":
          console.error("Payment error:", data);
          break;
      }
    };

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [visible, onClose]);
  
  const handleBuyClick = async () => {
    try {
      if (!userDetails?.walletAddress) {
        console.error("No wallet address provided");
        return;
      }
  
      // Call your backend to get a Secure Init session token
      const response = await api.post("/api/v1/coinbase-session", {
        walletAddress: userDetails.walletAddress,
        email: userDetails.email,
      });
  
      if (!response.data?.success || !response.data?.sessionToken) {
        console.error("Failed to get session token:", response.data);
        return;
      }
  
      console.log("Sessions Token", response.data.sessionToken)
      const sessionToken = response.data.sessionToken;
  
      const url = new URL("https://pay.coinbase.com/buy/select-asset");
      url.searchParams.set("sessionToken", sessionToken);
      url.searchParams.set("theme", "dark");
  
      // Optional: user data for prefill (not required)
      if (userDetails.email) {
        url.searchParams.set("userData", JSON.stringify({ email: userDetails.email }));
      }
  
      console.log("Opening Coinbase Pay with Secure Init:", url.toString());
  
      window.open(url.toString(), "_blank", "width=500,height=700,scrollbars=yes,resizable=yes");
    } catch (error) {
      console.error("Error during Coinbase Pay flow:", error);
    }
  };
  

  if (!visible) return null;

  return (
    <div
      className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <Card
        className="w-full max-w-md bg-zinc-900/95 border border-zinc-800 shadow-2xl relative overflow-hidden"
        onClick={(e: MouseEvent<HTMLDivElement>) => e.stopPropagation()}
        ref={modalRef}
      >
        <CardHeader className="text-center">
          <CardTitle className="text-xl font-bold text-white">Buy USDC with Coinbase</CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <div className="text-center space-y-4">
            <div className="text-zinc-300 mb-6">
              <p className="mb-2">Purchase USDC directly to your wallet using:</p>
              <ul className="text-sm space-y-1">
                <li>• Credit/Debit Cards</li>
                <li>• Bank Transfers</li>
                <li>• Secure Coinbase Platform</li>
              </ul>
            </div>
            
            {userDetails?.walletAddress && (
              <div className="bg-zinc-800/50 p-3 rounded-lg mb-4">
                <p className="text-xs text-zinc-400 mb-1">Destination Wallet:</p>
                <p className="text-xs text-cyan-400 font-mono break-all">
                  {userDetails.walletAddress}
                </p>
              </div>
            )}

            <div className="flex flex-col space-y-3">
              <Button
                onClick={handleBuyClick}
                className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors"
              >
                Open Coinbase Pay
              </Button>
              <Button
                variant="outline"
                onClick={onClose}
                className="text-zinc-300 hover:text-white"
              >
                Cancel
              </Button>
            </div>

            <div className="text-xs text-zinc-500 mt-4">
              <p>You'll be redirected to Coinbase's secure payment platform.</p>
              <p>USDC will be sent directly to your wallet address.</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default CoinbaseCDPModal; 