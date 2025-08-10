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

    // Prevent body scroll when modal is open - use a safer approach
    const originalStyle = window.getComputedStyle(document.body).overflow;
    const originalPosition = window.getComputedStyle(document.body).position;
    const originalTop = window.getComputedStyle(document.body).top;
    
    // Store current scroll position
    const scrollY = window.scrollY;
    
    document.body.style.overflow = 'hidden';
    document.body.style.position = 'fixed';
    document.body.style.top = `-${scrollY}px`;
    document.body.style.width = '100%';

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

        // Clear any existing content
        containerRef.current.innerHTML = '';

        // Initialize the WebSDK with improved configuration
        const snsWebSdk = (window as any).snsWebSdk;
        
        sdkInstanceRef.current = snsWebSdk
          .init(accessToken, () => {
            // Token expiration handler
            return Promise.resolve(accessToken);
          })
          .withConf({
            lang: 'en',
            email: applicantEmail,
            phone: applicantPhone,
            // Improved configuration for better UX
            i18n: {
              document: {
                subTitles: {
                  IDENTITY: "Upload a document that proves your identity"
                }
              }
            },
            // Better mobile support
            mobile: {
              enabled: true,
              responsive: true
            },
            // Improved accessibility
            accessibility: {
              enabled: true
            },
            // Better error handling
            onMessage: (type: string, payload: any) => {
              if (type === 'idCheck.onApproved') {
                onClose();
              } else if (type === 'idCheck.onRejected') {
                onClose();
              } else if (type === 'idCheck.onError') {
                console.error('KYC error', payload);
                onClose();
              } else if (type === 'idCheck.onStepCompleted') {
              }
            },
            onError: (error: any) => {
              console.error('WebSDK onError', error);
              onClose();
            }
          })
          .withOptions({ 
            addViewportTag: false, 
            adaptIframeHeight: true,
            // Improved options for better widget behavior
            mobileResponsive: true,
            enableDragAndDrop: true,
            enableFilePicker: true,
            // Better z-index management
            zIndex: 10000
          })
          .on('idCheck.onStepCompleted', (payload: any) => {
          })
          .on('idCheck.onError', (error: any) => {
            console.error('Step error:', error);
          })
          .build();

        // Launch the SDK with a small delay to ensure container is ready
        setTimeout(() => {
          if (sdkInstanceRef.current) {
            sdkInstanceRef.current.launch('#sumsub-kyc-container');
            
            // Add additional setup for iframe scrolling
            setTimeout(() => {
              const iframe = containerRef.current?.querySelector('iframe');
              if (iframe) {
                // Ensure iframe has proper scrolling
                iframe.style.overflow = 'auto';
                (iframe.style as any)['-webkit-overflow-scrolling'] = 'touch';
                iframe.style.height = '100%';
                
                // Try to access iframe content and fix scrolling
                try {
                  iframe.onload = () => {
                    try {
                      const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
                      if (iframeDoc) {
                        iframeDoc.body.style.overflow = 'auto';
                        (iframeDoc.body.style as any)['-webkit-overflow-scrolling'] = 'touch';
                        iframeDoc.documentElement.style.overflow = 'auto';
                        (iframeDoc.documentElement.style as any)['-webkit-overflow-scrolling'] = 'touch';
                      }
                    } catch (e) {
                      // Cross-origin restrictions, but that's okay
                    }
                  };
                } catch (e) {
                }
              }
            }, 500);
          }
        }, 100);
      } catch (error) {
        console.error('Failed to initialize Sumsub SDK:', error);
        onClose();
      }
    };

    initializeSDK();

    // Cleanup function
    return () => {
      // Restore body scroll and position
      document.body.style.overflow = originalStyle;
      document.body.style.position = originalPosition;
      document.body.style.top = originalTop;
      document.body.style.width = '';
      
      // Restore scroll position
      window.scrollTo(0, scrollY);
      
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
  }, [visible, accessToken, applicantEmail, applicantPhone, onClose]);

  if (!visible) return null;

  return (
    <div style={{ 
      position: 'fixed', 
      top: 0, 
      left: 0, 
      width: '100vw', 
      height: '100vh', 
      background: 'rgba(0,0,0,0.8)',
      zIndex: 9999, 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center',
      padding: '0',
      overflow: 'hidden',
      WebkitOverflowScrolling: 'touch'
    }}>
      <div style={{ 
        background: '#fff', 
        borderRadius: 12, 
        position: 'relative',
        width: '100%',
        height: '100%',
        maxWidth: '1200px',
        maxHeight: '100vh',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        WebkitOverflowScrolling: 'touch'
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
            zIndex: 10001,
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
            overflow: 'auto',
            position: 'relative',
            zIndex: 10000,
            minHeight: '600px',
            WebkitOverflowScrolling: 'touch',
            display: 'flex',
            flexDirection: 'column'
          }} 
        />
      </div>
    </div>
  );
};

export default SumsubKYCModal; 