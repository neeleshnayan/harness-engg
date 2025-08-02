import React, { useEffect, useRef, useState } from "react";
import type { FC, MouseEvent } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";

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
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [sdkLoadError, setSdkLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

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
    
    // Embedded widget specific parameters
    transakUrl.searchParams.set('isEmbed', 'true');
    transakUrl.searchParams.set('widgetHeight', '100%');
    transakUrl.searchParams.set('widgetWidth', '100%');
    transakUrl.searchParams.set('disableWalletAddressForm', 'true');
    transakUrl.searchParams.set('hideExchangeScreenHeader', 'false');
    
    // Payment method configuration
    transakUrl.searchParams.set('isDisableCard', 'false');
    transakUrl.searchParams.set('isDisableBank', 'false');
    transakUrl.searchParams.set('isDisableApplePay', 'false');
    transakUrl.searchParams.set('isDisableGooglePay', 'false');
    transakUrl.searchParams.set('partnerOrderId', `order_${Date.now()}`);
    transakUrl.searchParams.set('partnerCustomerId', "foodlai.foodlabs@gmail.com");
    
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
    
    // Hard-coded card details for testing/development
    // ⚠️ WARNING: Only use test card details, never real card details in production
    const hardcodedCardDetails = {
      paymentMethod: 'card',
      cardNumber: '4024764449971519', // Test Visa card number
      cardExpiry: '10/33', // MM/YY format
      cardCvv: '123', // 3-digit CVV
    };
    
    // Set default payment method to card
    transakUrl.searchParams.set('defaultPaymentMethod', hardcodedCardDetails.paymentMethod);
    transakUrl.searchParams.set('paymentMethod', hardcodedCardDetails.paymentMethod);
    
    // Configure payment method settings - enable only card payments
    transakUrl.searchParams.set('isDisableCard', 'false');
    transakUrl.searchParams.set('isDisableBank', 'true');
    transakUrl.searchParams.set('isDisableApplePay', 'true');
    transakUrl.searchParams.set('isDisableGooglePay', 'true');
    
    // Pre-fill hard-coded card details
    transakUrl.searchParams.set('cardNumber', hardcodedCardDetails.cardNumber);
    transakUrl.searchParams.set('cardExpiry', hardcodedCardDetails.cardExpiry);
    transakUrl.searchParams.set('cardCvv', hardcodedCardDetails.cardCvv);
    
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
    return finalUrl;
  };

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (visible) {
      document.addEventListener("keydown", handleKeyDown);
      setIsLoading(true);
    } else {
      document.removeEventListener("keydown", handleKeyDown);
      setIsLoading(false);
    }
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [visible, onClose]);

  // Handle iframe load
  const handleIframeLoad = () => {
    setIsLoading(false);
  };

  // Handle iframe messages from Transak
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      // Handle messages from Transak iframe
      if (event.origin.includes('transak.com')) {
        
        // Handle completion/close events
        if (event.data?.event_id === 'TRANSAK_WIDGET_CLOSE' || 
            event.data?.event_id === 'TRANSAK_ORDER_SUCCESSFUL') {
          onClose();
        }
      }
    };

    if (visible) {
      window.addEventListener('message', handleMessage);
    }

    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, [visible, onClose]);



  if (!visible) return null;

  return (
    <div
      className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <Card
        className="w-full max-w-6xl h-[90vh] bg-zinc-900/95 border border-zinc-800 shadow-2xl relative overflow-hidden flex flex-col"
        onClick={(e: MouseEvent<HTMLDivElement>) => e.stopPropagation()}
        ref={modalRef}
      >
        
        <CardContent className="flex-1 p-0 relative">

          {sdkLoadError && (
            <div className="bg-red-800/20 border border-red-600/30 p-3 mx-6 mb-4 rounded-lg">
              <p className="text-sm text-red-400">
                {sdkLoadError}
              </p>
            </div>
          )}

          {/* Loading state */}
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-zinc-900/50 z-10">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
                <p className="text-white">Loading Transak widget...</p>
              </div>
            </div>
          )}

          {/* Transak iframe */}
          <iframe
            ref={iframeRef}
            src={buildTransakUrl()}
            className="w-full h-full border-0"
            title="Transak Widget"
            onLoad={handleIframeLoad}
            allow="camera; microphone; payment"
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox"
          />
        </CardContent>
      </Card>
    </div>
  );
};

export default TransakWidgetModal; 