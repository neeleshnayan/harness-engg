import React, { useEffect, useRef } from 'react';

interface SumsubKYCModalProps {
  accessToken: string;
  visible: boolean;
  onClose: () => void;
  applicantEmail?: string;
  applicantPhone?: string;
}

const SUMSUB_SDK_URL = 'https://static.sumsub.com/idensic/static/sns-websdk-builder.js';

const SumsubKYCModal: React.FC<SumsubKYCModalProps> = ({ 
  accessToken, 
  visible, 
  onClose, 
  applicantEmail, 
  applicantPhone 
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const sdkInstanceRef = useRef<any>(null);

  useEffect(() => {
    if (!visible || !accessToken) return;

    // Load the Sumsub WebSDK script
    const loadSDK = async () => {
      return new Promise<void>((resolve, reject) => {
        // Check if SDK is already loaded
        if ((window as any).snsWebSdk) {
          resolve();
          return;
        }

        const script = document.createElement('script');
        script.src = SUMSUB_SDK_URL;
        script.async = true;
        script.onload = () => resolve();
        script.onerror = () => reject(new Error('Failed to load Sumsub SDK'));
        document.head.appendChild(script);
      });
    };

    const initializeSDK = async () => {
      try {
        await loadSDK();
        
        if (!containerRef.current) return;

        // Initialize the WebSDK using the correct pattern from documentation
        const snsWebSdk = (window as any).snsWebSdk;
        
        sdkInstanceRef.current = snsWebSdk
          .init(accessToken, () => {
            // Token expiration handler - you might want to implement this
            console.log('Token expired, need to get new token');
            return Promise.resolve(accessToken); // For now, return the same token
          })
          .withConf({
            lang: 'en',
            email: applicantEmail,
            phone: applicantPhone,
            i18n: {
              document: {
                subTitles: {
                  IDENTITY: "Upload a document that proves your identity"
                }
              }
            },
            onMessage: (type: string, payload: any) => {
              console.log('WebSDK onMessage', type, payload);
              if (type === 'idCheck.onApproved') {
                console.log('KYC approved');
                onClose();
              } else if (type === 'idCheck.onRejected') {
                console.log('KYC rejected');
                onClose();
              } else if (type === 'idCheck.onError') {
                console.error('KYC error', payload);
                onClose();
              }
            },
            onError: (error: any) => {
              console.error('WebSDK onError', error);
              onClose();
            }
          })
          .withOptions({ 
            addViewportTag: false, 
            adaptIframeHeight: true 
          })
          .on('idCheck.onStepCompleted', (payload: any) => {
            console.log('onStepCompleted', payload);
          })
          .on('idCheck.onError', (error: any) => {
            console.log('onError', error);
          })
          .build();

        // Launch the SDK
        sdkInstanceRef.current.launch('#sumsub-kyc-container');
      } catch (error) {
        console.error('Failed to initialize Sumsub SDK:', error);
        onClose();
      }
    };

    initializeSDK();

    // Cleanup function
    return () => {
      if (sdkInstanceRef.current) {
        try {
          // Clear the container content
          if (containerRef.current) {
            containerRef.current.innerHTML = '';
          }
          
          // Try to destroy the SDK instance if it has a destroy method
          if (typeof sdkInstanceRef.current.destroy === 'function') {
            sdkInstanceRef.current.destroy();
          } else if (typeof sdkInstanceRef.current.dispose === 'function') {
            sdkInstanceRef.current.dispose();
          }
          
          // Clear the reference
          sdkInstanceRef.current = null;
        } catch (error) {
          console.error('Error cleaning up SDK:', error);
          // Even if cleanup fails, clear the reference
          sdkInstanceRef.current = null;
        }
      }
    };
  }, [accessToken, visible, applicantEmail, applicantPhone, onClose]);

  if (!visible) return null;

  return (
    <div style={{ 
      position: 'fixed', 
      top: 0, 
      left: 0, 
      width: '100vw', 
      height: '100vh', 
      background: 'rgba(0,0,0,0.8)', 
      zIndex: 1000, 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center',
      padding: '20px'
    }}>
      <div style={{ 
        background: '#fff', 
        borderRadius: 12, 
        position: 'relative',
        width: '95vw',
        height: '95vh',
        maxWidth: '1200px',
        maxHeight: '900px',
        overflow: 'hidden'
      }}>
        <button 
          onClick={onClose} 
          style={{ 
            position: 'absolute', 
            top: 16, 
            right: 16, 
            fontSize: 24, 
            background: 'rgba(0,0,0,0.1)', 
            border: 'none', 
            borderRadius: '50%',
            width: 40,
            height: 40,
            cursor: 'pointer',
            zIndex: 1001,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#666',
            transition: 'all 0.2s ease'
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.background = 'rgba(0,0,0,0.2)';
            e.currentTarget.style.color = '#333';
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.background = 'rgba(0,0,0,0.1)';
            e.currentTarget.style.color = '#666';
          }}
        >
          ×
        </button>
        <div 
          id="sumsub-kyc-container" 
          ref={containerRef} 
          style={{ 
            width: '100%', 
            height: '100%',
            overflow: 'hidden'
          }} 
        />
      </div>
    </div>
  );
};

export default SumsubKYCModal; 