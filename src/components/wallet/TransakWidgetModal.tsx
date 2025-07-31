import React, { useEffect, useRef, useState } from "react";
import type { FC, MouseEvent } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface TransakWidgetModalProps {
  visible: boolean;
  onClose: () => void;
  userDetails?: {
    walletAddress?: string;
    email?: string;
    kycStatus?: string;
  };
}

const TransakWidgetModal: FC<TransakWidgetModalProps> = ({ 
  visible, 
  onClose, 
  userDetails 
}: TransakWidgetModalProps) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const [sdkLoadError, setSdkLoadError] = useState<string | null>(null);

  // Helper function to build Transak URL
  const buildTransakUrl = () => {
    const apiKey = process.env.NEXT_PUBLIC_TRANSAK_API_KEY || 'f4c10825-55fd-4ccc-bd3f-40fc021468e5';
    const environment = process.env.NEXT_PUBLIC_TRANSAK_ENVIRONMENT || 'STAGING';
    
    const transakUrl = new URL('https://global-stg.transak.com');
    transakUrl.searchParams.set('apiKey', apiKey);
    transakUrl.searchParams.set('environment', environment);
    transakUrl.searchParams.set('defaultCryptoCurrency', 'USDC');
    transakUrl.searchParams.set('cryptoCurrencyList', 'USDC');
    transakUrl.searchParams.set('walletAddress', userDetails?.walletAddress || '');
    transakUrl.searchParams.set('themeColor', '#3B82F6');
    transakUrl.searchParams.set('redirectURL', window.location.origin + '/wallet');
    transakUrl.searchParams.set('hideMenu', 'false');
    transakUrl.searchParams.set('isDisableCrypto', 'false');
    transakUrl.searchParams.set('isDisableMatic', 'true');
    transakUrl.searchParams.set('exchangeScreenTitle', 'Buy USDC');
    transakUrl.searchParams.set('partnerOrderId', `order_${Date.now()}`);
    transakUrl.searchParams.set('partnerCustomerId', userDetails?.email || 'anonymous');
    
    // KYC Configuration - Skip KYC if already verified
    if (userDetails?.kycStatus === 'approved') {
      transakUrl.searchParams.set('kycMode', 'SKIP');
      transakUrl.searchParams.set('skipKYC', 'true');
    } else {
      transakUrl.searchParams.set('kycMode', 'REQUIRED');
    }
    
    // Sumsub Integration Parameters
    transakUrl.searchParams.set('kycProvider', 'sumsub');
    transakUrl.searchParams.set('useExistingKYC', 'true');
    transakUrl.searchParams.set('skipIfApproved', 'true');
    transakUrl.searchParams.set('kycSkipIfVerified', 'true');
    transakUrl.searchParams.set('sumsubIntegration', 'true');
    
    if (userDetails?.email) {
      transakUrl.searchParams.set('email', userDetails.email);
    }
    
    // Additional user data for KYC recognition
    const userData = {
      email: userDetails?.email,
      kycStatus: userDetails?.kycStatus,
      kycProvider: 'sumsub',
      walletAddress: userDetails?.walletAddress,
      kycStatusUrl: `${process.env.NEXT_PUBLIC_API_URL || 'https://api.kryptonfund.com'}/api/v1/kyc/status/${userDetails?.email}`
    };
    
    transakUrl.searchParams.set('userData', JSON.stringify(userData));

    const finalUrl = transakUrl.toString();
    console.log('Transak URL with KYC params:', finalUrl);
    return finalUrl;
  };

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

  useEffect(() => {
    if (!visible || !userDetails?.walletAddress) return;

    // Use Transak's popup approach
    const openTransakWidget = () => {
      try {
        // Open Transak in a new window
        const transakWindow = window.open(
          buildTransakUrl(),
          'Transak',
          'width=500,height=700,scrollbars=yes,resizable=yes'
        );

        // Handle window close
        const checkClosed = setInterval(() => {
          if (transakWindow?.closed) {
            clearInterval(checkClosed);
            onClose();
          }
        }, 1000);

        // Cleanup interval on component unmount
        return () => {
          clearInterval(checkClosed);
          if (transakWindow && !transakWindow.closed) {
            transakWindow.close();
          }
        };

      } catch (error) {
        console.error('Failed to open Transak widget:', error);
        setSdkLoadError('Failed to open Transak widget. Please try again later.');
      }
    };

    // Open the widget when modal becomes visible
    const cleanup = openTransakWidget();

    // Cleanup function
    return () => {
      if (cleanup) cleanup();
    };
  }, [visible, userDetails, onClose]);

  if (!visible) return null;

  return (
    <div
      className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <Card
        className="w-full max-w-4xl bg-zinc-900/95 border border-zinc-800 shadow-2xl relative overflow-hidden"
        onClick={(e: MouseEvent<HTMLDivElement>) => e.stopPropagation()}
        ref={modalRef}
      >
        <CardHeader className="text-center">
          <CardTitle className="text-xl font-bold text-white">Buy USDC with Transak</CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <div className="text-center space-y-4">
            <div className="text-zinc-300 mb-6">
              <p className="mb-2">Purchase USDC directly to your wallet using:</p>
              <ul className="text-sm space-y-1">
                <li>• Credit/Debit Cards</li>
                <li>• Bank Transfers</li>
                <li>• Apple Pay / Google Pay</li>
                <li>• Secure Transak Platform</li>
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

            {userDetails?.kycStatus === 'approved' && (
              <div className="bg-green-800/20 border border-green-600/30 p-3 rounded-lg mb-4">
                <p className="text-sm text-green-400">
                  ✓ KYC Verified - You can proceed with your purchase
                </p>
              </div>
            )}

            {userDetails?.kycStatus !== 'approved' && (
              <div className="bg-yellow-800/20 border border-yellow-600/30 p-3 rounded-lg mb-4">
                <p className="text-sm text-yellow-400">
                  ⚠ KYC Required - You'll need to complete verification during purchase
                </p>
              </div>
            )}

            {sdkLoadError && (
              <div className="bg-red-800/20 border border-red-600/30 p-3 rounded-lg mb-4">
                <p className="text-sm text-red-400">
                  {sdkLoadError}
                </p>
              </div>
            )}

            <div className="flex flex-col space-y-3">
              <Button
                onClick={() => {
                  window.open(
                    buildTransakUrl(),
                    'Transak',
                    'width=500,height=700,scrollbars=yes,resizable=yes'
                  );
                }}
                className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors"
              >
                Open Transak
              </Button>
              <Button
                variant="outline"
                onClick={onClose}
                className="text-zinc-300 hover:text-white"
              >
                Close
              </Button>
            </div>

            <div className="text-xs text-zinc-500 mt-4">
              <p>Transak will open in a new window.</p>
              <p>USDC will be sent directly to your wallet address.</p>
              <p>Please allow popups if the window doesn't open automatically.</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default TransakWidgetModal; 