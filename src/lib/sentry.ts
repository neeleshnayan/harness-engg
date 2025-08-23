import * as Sentry from '@sentry/nextjs';

// Initialize Sentry with custom configuration
export const initSentry = () => {
  if (typeof window !== 'undefined') {
    // Client-side configuration
    Sentry.init({
      dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
      
      // Performance monitoring
      tracesSampleRate: process.env.NODE_ENV === 'production' ? 0.1 : 1.0,
      
      // Session replay
      replaysSessionSampleRate: process.env.NODE_ENV === 'production' ? 0.1 : 1.0,
      replaysOnErrorSampleRate: 1.0,
      
      // Logs
      enableLogs: true,
      
      // Environment
      environment: process.env.NODE_ENV || 'development',
      
      // Release tracking
      release: process.env.NEXT_PUBLIC_APP_VERSION || '1.0.0',
      
      // Debug mode
      debug: process.env.NODE_ENV === 'development',
      
      // Integrations
      integrations: [
        Sentry.replayIntegration({
          // Privacy settings for session replay
          maskAllText: false,
          blockAllMedia: false,
        }),
        Sentry.browserTracingIntegration(),
      ],
      
      // Before send hook to filter sensitive data
      beforeSend(event, hint) {
        // Filter out sensitive information
        if (event.request?.headers) {
          delete event.request.headers['authorization'];
          delete event.request.headers['cookie'];
        }
        
        // Filter out specific error types if needed
        if (event.exception) {
          const error = hint.originalException as Error;
          if (error?.message?.includes('ResizeObserver loop limit exceeded')) {
            return null; // Filter out common browser errors
          }
        }
        
        return event;
      },
      
      // Before send transaction hook for performance data
      beforeSendTransaction(event) {
        // Filter out health check or monitoring endpoints
        if (event.transaction === '/api/health' || event.transaction === '/monitoring') {
          return null;
        }
        return event;
      },
    });
  }
};

// Set user context for better error tracking
export const setUserContext = (userData: any) => {
  if (userData) {
    Sentry.setUser({
      id: userData.user_id || userData.id,
      username: userData.username,
      email: userData.email,
      wallet_address: userData.wallet_address,
      kyc_status: userData.kyc_status,
    });
    
    // Set additional context
    Sentry.setContext('wallet', {
      wallet_id: userData.wallet_id,
      blockchain: userData.blockchain,
      balance: userData.balance,
    });
    
    Sentry.setContext('kyc', {
      status: userData.kyc_status,
      applicant_id: userData.applicant_id,
    });
  }
};

// Clear user context on logout
export const clearUserContext = () => {
  Sentry.setUser(null);
  Sentry.setContext('wallet', {});
  Sentry.setContext('kyc', {});
};

// Capture specific errors with context
export const captureError = (error: Error, context?: Record<string, any>) => {
  if (context) {
    Sentry.setContext('error_context', context);
  }
  Sentry.captureException(error);
};

// Capture performance metrics
export const captureTransaction = (name: string, operation: string, fn: () => Promise<any>) => {
  return Sentry.startSpan(
    {
      name,
      op: operation,
    },
    fn
  );
};

// Capture API errors with additional context
export const captureAPIError = (error: any, endpoint: string, requestData?: any) => {
  Sentry.setContext('api_error', {
    endpoint,
    method: 'POST', // or GET, PUT, etc.
    request_data: requestData,
    response_status: error.response?.status,
    response_data: error.response?.data,
  });
  
  Sentry.captureException(error);
};

// Capture WebSocket errors
export const captureWebSocketError = (error: any, connectionInfo: any) => {
  Sentry.setContext('websocket_error', {
    connection_status: connectionInfo.status,
    url: connectionInfo.url,
    error_type: error.type,
    error_target: error.target,
  });
  
  Sentry.captureException(error);
};

// Capture wallet transaction errors
export const captureWalletError = (error: any, transactionType: string, amount?: string, recipient?: string) => {
  Sentry.setContext('wallet_error', {
    transaction_type: transactionType,
    amount,
    recipient,
  });
  
  Sentry.captureException(error);
};

// Capture KYC process errors
export const captureKYCError = (error: any, step: string, userId: string) => {
  Sentry.setContext('kyc_error', {
    step,
    user_id: userId,
    timestamp: new Date().toISOString(),
  });
  
  Sentry.captureException(error);
};

// Add breadcrumbs for better debugging
export const addBreadcrumb = (message: string, category: string, data?: Record<string, any>) => {
  Sentry.addBreadcrumb({
    message,
    category,
    data,
    level: 'info',
  });
};

// Performance monitoring helpers
export const startPerformanceSpan = (name: string, operation: string) => {
  return Sentry.startSpan({
    name,
    op: operation,
  }, () => {});
};

// Export Sentry instance for direct use
export { Sentry };
