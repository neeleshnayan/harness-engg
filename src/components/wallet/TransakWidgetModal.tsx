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

  // Helper function to validate Ethereum wallet address
  const validateWalletAddress = (address: string): boolean => {
    return /^0x[a-fA-F0-9]{40}$/.test(address);
  };

  // Helper function to build Transak URL
  // This ensures Transak uses the same blockchain (ETH-SEPOLIA) as the Circle wallet
  const buildTransakUrl = () => {
    const apiKey = process.env.NEXT_PUBLIC_TRANSAK_API_KEY || 'f4c10825-55fd-4ccc-bd3f-40fc021468e5';
    const environment = process.env.NEXT_PUBLIC_TRANSAK_ENVIRONMENT || 'STAGING';
    
    const transakUrl = new URL('https://global-stg.transak.com');
    transakUrl.searchParams.set('apiKey', apiKey);
    transakUrl.searchParams.set('environment', environment);
    
    // Environment-specific KYC settings
    if (environment === 'STAGING') {
      transakUrl.searchParams.set('testMode', 'true');
      transakUrl.searchParams.set('kycTestMode', 'true');
      // Additional test parameters for KYC bypass
      if (userDetails?.kycStatus === 'approved') {
        transakUrl.searchParams.set('testKYC', 'false');
        transakUrl.searchParams.set('testKYCLevel', '0');
      }
    }
    transakUrl.searchParams.set('defaultCryptoCurrency', 'USDC');
    transakUrl.searchParams.set('cryptoCurrencyList', 'USDC');
    transakUrl.searchParams.set('walletAddress', userDetails?.walletAddress || '');
    
    // Configure blockchain network to match Circle wallet (ETH-SEPOLIA)
    transakUrl.searchParams.set('defaultNetwork', 'ethereum');
    transakUrl.searchParams.set('networks', 'ethereum');
    transakUrl.searchParams.set('network', 'ethereum');
    transakUrl.searchParams.set('blockchain', 'ethereum');
    
    // For testnet (Sepolia) configuration to match Circle wallet
    if (environment === 'STAGING') {
      transakUrl.searchParams.set('testnet', 'true');
      transakUrl.searchParams.set('networkType', 'testnet');
      transakUrl.searchParams.set('defaultNetwork', 'ethereum-sepolia');
      transakUrl.searchParams.set('networks', 'ethereum-sepolia');
      transakUrl.searchParams.set('network', 'ethereum-sepolia');
      transakUrl.searchParams.set('blockchain', 'ethereum-sepolia');
      
      // Configure USDC for Sepolia testnet (same as Circle wallet)
      transakUrl.searchParams.set('tokenAddress', '0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238'); // USDC on Sepolia
      transakUrl.searchParams.set('tokenContractAddress', '0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238'); // USDC on Sepolia
    }
    
    // Force direct purchase flow for verified users
    if (userDetails?.kycStatus === 'approved') {
      transakUrl.searchParams.set('directPurchase', 'true');
      transakUrl.searchParams.set('skipVerification', 'true');
      transakUrl.searchParams.set('bypassKYC', 'true');
    }
    transakUrl.searchParams.set('themeColor', '#3B82F6');
    transakUrl.searchParams.set('redirectURL', window.location.origin + '/customer');
    transakUrl.searchParams.set('hideMenu', 'false');
    transakUrl.searchParams.set('isDisableCrypto', 'false');
    transakUrl.searchParams.set('isDisableMatic', 'true');
    transakUrl.searchParams.set('exchangeScreenTitle', 'Buy USDC');
    transakUrl.searchParams.set('partnerOrderId', `order_${Date.now()}`);
    transakUrl.searchParams.set('partnerCustomerId', userDetails?.email || 'anonymous');
    
    // KYC Configuration - Try to completely disable KYC for verified users
    if (userDetails?.kycStatus === 'approved') {
      transakUrl.searchParams.set('kycMode', 'DISABLED');
      transakUrl.searchParams.set('skipKYC', 'true');
      transakUrl.searchParams.set('kycSkipIfVerified', 'true');
      transakUrl.searchParams.set('useExistingKYC', 'true');
      transakUrl.searchParams.set('kycRequired', 'false');
      transakUrl.searchParams.set('disableKYC', 'true');
      transakUrl.searchParams.set('kycLevel', '0');
      transakUrl.searchParams.set('noKYC', 'true');
    } else {
      // For unverified users, use minimal KYC
      transakUrl.searchParams.set('kycLevel', '1');
      transakUrl.searchParams.set('kycMode', 'BASIC');
      transakUrl.searchParams.set('disableKYC', 'false');
      transakUrl.searchParams.set('kycRequired', 'false');
    }
    
    // Sumsub Integration Parameters
    transakUrl.searchParams.set('kycProvider', 'sumsub');
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
      kycLevel: userDetails?.kycStatus === 'approved' ? '0' : '1',
      kycStatusUrl: `${process.env.NEXT_PUBLIC_API_URL || 'https://api.kryptonfund.com'}/api/v1/kyc/status/${userDetails?.email}`,
      // Additional KYC info
      kycVerified: userDetails?.kycStatus === 'approved',
      kycLevel1: userDetails?.kycStatus !== 'approved',
      skipDocumentUpload: userDetails?.kycStatus === 'approved',
      // Force skip KYC for verified users
      kycDisabled: userDetails?.kycStatus === 'approved',
      kycNotRequired: userDetails?.kycStatus === 'approved',
      existingKYC: userDetails?.kycStatus === 'approved'
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
          <div className="text-sm text-zinc-400 mt-2">
            Network: Ethereum Sepolia (Testnet) - Same as your Circle wallet
          </div>
        </CardHeader>
        <CardContent className="p-6">
          <div className="text-center space-y-4">
            
            
            {userDetails?.walletAddress && (
              <div className="bg-zinc-800/50 p-3 rounded-lg mb-4">
                <p className="text-xs text-zinc-400 mb-1">Destination Wallet:</p>
                <p className="text-xs text-cyan-400 font-mono break-all">
                  {userDetails.walletAddress}
                </p>
                {validateWalletAddress(userDetails.walletAddress) ? (
                  <p className="text-xs text-green-400 mt-1">
                    ✓ Valid Ethereum address for Sepolia network
                  </p>
                ) : (
                  <p className="text-xs text-red-400 mt-1">
                    ⚠ Invalid wallet address format
                  </p>
                )}
              </div>
            )}

            {/* {userDetails?.kycStatus === 'approved' && (
              <div className="bg-green-800/20 border border-green-600/30 p-3 rounded-lg mb-4">
                <p className="text-sm text-green-400">
                  ✓ KYC Verified - You can proceed with your purchase
                </p>
              </div>
            )} */}

            {/* {userDetails?.kycStatus !== 'approved' && (
              <div className="bg-yellow-800/20 border border-yellow-600/30 p-3 rounded-lg mb-4">
                <p className="text-sm text-yellow-400">
                  ⚠ KYC Required - You'll need to complete verification during purchase
                </p>
              </div>
            )} */}

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

                    // Cleanup interval after 5 minutes to prevent memory leaks
                    setTimeout(() => {
                      clearInterval(checkClosed);
                    }, 300000);

                  } catch (error) {
                    console.error('Failed to open Transak widget:', error);
                    setSdkLoadError('Failed to open Transak widget. Please try again later.');
                  }
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
              <p>USDC will be sent directly to your wallet on Ethereum Sepolia (same network as your Circle wallet).</p>
              <p>Please allow popups if the window doesn't open.</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default TransakWidgetModal; 