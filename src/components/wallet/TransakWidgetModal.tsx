import React, { useEffect, useRef, useState } from "react";
import type { FC, MouseEvent } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { X } from "lucide-react";
import api from "@/lib/api";

interface TransakWidgetModalProps {
  visible: boolean;
  onClose: () => void;
  userDetails?: {
    walletAddress?: string;
    email?: string;
    kycStatus?: string;
    firstName?: string;
    lastName?: string;
    mobileNumber?: string;
    dateOfBirth?: string;
    defaultFiatAmount?: number;
    defaultCryptoAmount?: number;
    userId?: string; // Add userId to fetch KYC share token
    address?: {
      addressLine1?: string;
      addressLine2?: string;
      city?: string;
      state?: string;
      postCode?: string;
      countryCode?: string;
    };
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
  const [transakUrl, setTransakUrl] = useState<string>('');

  // Helper function to validate Ethereum wallet address
  const validateWalletAddress = (address: string): boolean => {
    return /^0x[a-fA-F0-9]{40}$/.test(address);
  };

  // Helper function to build Transak URL
  // This ensures Transak uses the same blockchain (ETH-SEPOLIA) as the Circle wallet
  const buildTransakUrl = async () => {
    const apiKey = process.env.NEXT_PUBLIC_TRANSAK_API_KEY || 'f4c10825-55fd-4ccc-bd3f-40fc021468e5';
    const environment = process.env.NEXT_PUBLIC_TRANSAK_ENVIRONMENT || 'STAGING';
    
    const transakUrl = new URL('https://global-stg.transak.com');
    transakUrl.searchParams.set('apiKey', apiKey);
    transakUrl.searchParams.set('environment', environment);
    
    // Environment-specific KYC settings
    if (environment === 'STAGING') {
      transakUrl.searchParams.set('testMode', 'true');
      transakUrl.searchParams.set('kycTestMode', 'true');
    }
    
    // Basic configuration
    transakUrl.searchParams.set('defaultCryptoCurrency', 'USDC');
    transakUrl.searchParams.set('cryptoCurrencyList', 'USDC');
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
    transakUrl.searchParams.set('hideExchangeScreenHeader', 'false');
    
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
    
    // Wallet address configuration
    if (userDetails?.walletAddress) {
      transakUrl.searchParams.set('walletAddress', userDetails.walletAddress);
      transakUrl.searchParams.set('disableWalletAddressForm', 'true'); // Prevent editing wallet address
    }
    
    // KYC Share Token Configuration - Skip KYC using Sumsub
    if (userDetails?.userId && userDetails?.kycStatus === 'approved') {
      try {
        const response = await api.post(`/api/v1/kyc/share-token/${userDetails.userId}`);
        
        if (response.status === 200) {
          const data = response.data;
          
          if (data.success && data.kycShareToken) {
            // Set KYC reliance parameters according to Transak documentation
            transakUrl.searchParams.set('kycShareTokenProvider', 'SUMSUB');
            transakUrl.searchParams.set('kycShareToken', data.kycShareToken);
            transakUrl.searchParams.set('kycSkipIfVerified', 'true');
            transakUrl.searchParams.set('useExistingKYC', 'true');
            
          } else {
            console.warn('KYC share token response missing token:', data);
          }
        } else {
          console.warn('Failed to get KYC share token, status:', response.status);
          console.warn('Response data:', response.data);
        }
              } catch (error: any) {
          console.error('Error fetching KYC share token:', error);
          if (error.response) {
            console.error('Error response status:', error.response.status);
            console.error('Error response data:', error.response.data);
          }
        }
    } else {
    }
    
    // User Data Configuration - Pass information to skip screens
    if (userDetails?.email) {
      // Pass email to skip email entry screen
      transakUrl.searchParams.set('email', userDetails.email);
      
      // Pass default amounts to skip amount selection screen
      if (userDetails.defaultFiatAmount) {
        transakUrl.searchParams.set('defaultFiatAmount', userDetails.defaultFiatAmount.toString());
      }
      if (userDetails.defaultCryptoAmount) {
        transakUrl.searchParams.set('defaultCryptoAmount', userDetails.defaultCryptoAmount.toString());
      }
      
      // Pass complete user data to skip personal details screens
      const userData = {
        firstName: userDetails.firstName || "John", // You can make this dynamic based on user data
        lastName: userDetails.lastName || "Doe",   // You can make this dynamic based on user data
        email: userDetails.email,
        mobileNumber: userDetails.mobileNumber || "+918076127416", // You can make this dynamic based on user data
        dob: userDetails.dateOfBirth || "1990-01-01", // You can make this dynamic based on user data
        address: userDetails.address || {
          addressLine1: "123 Main St",
          addressLine2: "Apt 1",
          city: "New York",
          state: "NY",
          postCode: "110070",
          countryCode: "IN"
        }
      };
      
      // Stringify the userData object for URL parameter
      transakUrl.searchParams.set('userData', JSON.stringify(userData));
      
      // Set isAutoFillUserData to false to skip screens completely
      transakUrl.searchParams.set('isAutoFillUserData', 'false');
    }
    
    // Payment method configuration
    transakUrl.searchParams.set('isDisableCard', 'false');
    transakUrl.searchParams.set('isDisableBank', 'false');
    transakUrl.searchParams.set('isDisableApplePay', 'false');
    transakUrl.searchParams.set('isDisableGooglePay', 'false');
    transakUrl.searchParams.set('partnerOrderId', `order_${Date.now()}`);
    transakUrl.searchParams.set('partnerCustomerId', userDetails?.email || 'anonymous');
    
    // KYC Configuration - Use existing KYC if available
    if (userDetails?.kycStatus === 'approved') {
      transakUrl.searchParams.set('kycSkipIfVerified', 'true');
      transakUrl.searchParams.set('useExistingKYC', 'true');
    }
    
    // Sumsub Integration Parameters
    transakUrl.searchParams.set('kycProvider', 'sumsub');
    transakUrl.searchParams.set('sumsubIntegration', 'true');
    
    // Additional KYC parameters for better integration
    transakUrl.searchParams.set('kycMode', 'reliance');
    transakUrl.searchParams.set('kycReliance', 'true');
    
    // Debug parameters for troubleshooting
    transakUrl.searchParams.set('debugMode', 'true');
    transakUrl.searchParams.set('enableLogging', 'true');

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
      
      // Build Transak URL when modal becomes visible
      buildTransakUrl().then(url => {
        setTransakUrl(url);
        setIsLoading(false);
      }).catch(error => {
        console.error('Error building Transak URL:', error);
        setSdkLoadError('Failed to initialize Transak widget');
        setIsLoading(false);
      });
    } else {
      document.removeEventListener("keydown", handleKeyDown);
      setIsLoading(false);
      setTransakUrl('');
    }
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [visible, onClose, userDetails]);

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
          {transakUrl && (
            <iframe
              ref={iframeRef}
              src={transakUrl}
              className="w-full h-full border-0"
              title="Transak Widget"
              onLoad={handleIframeLoad}
              allow="camera; microphone; payment"
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox"
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default TransakWidgetModal; 