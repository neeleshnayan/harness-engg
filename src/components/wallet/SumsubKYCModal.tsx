import React from 'react';
import SumsubWebSdk from '@sumsub/websdk-react';

interface SumsubKYCModalProps {
  accessToken: string;
  visible: boolean;
  onClose: () => void;
  applicantEmail?: string;
  applicantPhone?: string;
}

const SumsubKYCModal: React.FC<SumsubKYCModalProps> = ({
  accessToken,
  visible,
  onClose,
  applicantEmail,
  applicantPhone
}) => {
  if (!visible) return null;

  const accessTokenExpirationHandler = async () => {
    // Refresh the token from your backend
    return accessToken;
  };

  const config = {
    lang: 'en',
    email: applicantEmail,
    phone: applicantPhone,
    i18n: {
      document: {
        subTitles: {
          IDENTITY: 'Upload a document that proves your identity',
        },
      },
    },
    mobile: {
      enabled: true,
      responsive: true,
    },
    accessibility: {
      enabled: true,
    },
  };

  const options = {
    addViewportTag: false,
    adaptIframeHeight: false, // Changed to false to enable scrolling
    mobileResponsive: true,
    enableDragAndDrop: true,
    enableFilePicker: true,
    zIndex: 10000,
  };

  const messageHandler = (type: string, payload: any) => {
    if (type === 'idCheck.onApproved' || type === 'idCheck.onRejected') {
      onClose();
    } else if (type === 'idCheck.onError') {
      console.error('KYC error', payload);
      onClose();
    }
  };

  const errorHandler = (error: any) => {
    console.error('WebSDK onError', error);
    onClose();
  };

  // CSS styles for mobile scrolling
  const modalStyles: React.CSSProperties = {
    position: 'fixed',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    zIndex: 10000,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  };

  const containerStyles: React.CSSProperties = {
    width: '100%',
    height: '100%',
    maxWidth: '500px',
    maxHeight: '100%',
    backgroundColor: '#ffffff',
    borderRadius: '8px',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  };

  const scrollableContentStyles: React.CSSProperties = {
    flex: 1,
    overflow: 'auto',
    WebkitOverflowScrolling: 'touch', // Enable smooth scrolling on iOS
    position: 'relative',
  };

  const closeButtonStyles: React.CSSProperties = {
    position: 'absolute',
    top: '16px',
    right: '16px',
    width: '32px',
    height: '32px',
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    border: 'none',
    borderRadius: '50%',
    color: 'white',
    fontSize: '18px',
    fontWeight: 'bold',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10001,
    transition: 'background-color 0.2s ease',
  };

  const widgetContainerStyles: React.CSSProperties = {
    minHeight: '100%',
    display: 'flex',
    flexDirection: 'column',
  };

  // Media query styles for mobile
  const mobileStyles = `
    @media (max-width: 768px) {
      .sumsub-modal-container {
        margin: 0 !important;
        border-radius: 0 !important;
        max-width: 100% !important;
      }
      
      .sumsub-scrollable-content {
        -webkit-overflow-scrolling: touch !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
      }
      
      .sumsub-widget-container iframe {
        min-height: 100vh !important;
      }
    }
    
    @media (max-height: 600px) {
      .sumsub-scrollable-content {
        overflow-y: auto !important;
      }
    }
    
    .sumsub-close-button:hover {
      background-color: rgba(0, 0, 0, 0.9) !important;
    }
    
    @media (max-width: 768px) {
      .sumsub-close-button {
        top: 20px !important;
        right: 20px !important;
        width: 36px !important;
        height: 36px !important;
        font-size: 20px !important;
      }
    }
  `;

  return (
    <>
      <style>{mobileStyles}</style>
      <div style={modalStyles} onClick={onClose}>
        <div 
          style={containerStyles} 
          className="sumsub-modal-container"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Close button */}
          <button
            style={closeButtonStyles}
            className="sumsub-close-button"
            onClick={onClose}
            aria-label="Close modal"
          >
            ×
          </button>
          <div 
            style={scrollableContentStyles}
            className="sumsub-scrollable-content"
          >
            <div 
              style={widgetContainerStyles}
              className="sumsub-widget-container"
            >
              <SumsubWebSdk
                accessToken={accessToken}
                expirationHandler={accessTokenExpirationHandler}
                config={config}
                options={options}
                onMessage={messageHandler}
                onError={errorHandler}
              />
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default SumsubKYCModal;