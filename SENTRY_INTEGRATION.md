# Sentry Integration for Krypton Wallet

This document explains how to use the Sentry observability integration that has been added to your Krypton Wallet application.

## What is Sentry?

[Sentry](https://sentry.io/welcome/) is a comprehensive application monitoring platform that provides:

- **Error Monitoring**: Real-time error tracking and alerting
- **Performance Monitoring**: Track API response times and user experience
- **Session Replay**: See exactly what users were doing when errors occurred
- **Logs**: Centralized logging with context
- **Release Tracking**: Monitor the health of each deployment

## Features Implemented

### 1. Error Tracking
- Automatic capture of JavaScript errors and exceptions
- API error tracking with request/response context
- WebSocket connection error monitoring
- Wallet transaction error tracking
- KYC process error monitoring

### 2. Performance Monitoring
- API call performance tracking
- User action performance monitoring
- Automatic transaction spans for key operations

### 3. User Context
- Automatic user identification and tracking
- Wallet and KYC status context
- Transaction history context

### 4. Breadcrumbs
- User action tracking for better debugging
- API call logging
- WebSocket connection status

### 5. Session Replay
- Privacy-focused session recording
- Error reproduction capabilities
- User experience insights

## Configuration

### Environment Variables

Create a `.env.local` file in your frontend directory with:

```bash
# Sentry DSN (Data Source Name)
NEXT_PUBLIC_SENTRY_DSN=https://your-public-key@o0.ingest.sentry.io/your-project-id

# App version for release tracking
NEXT_PUBLIC_APP_VERSION=1.0.0
```

### Sentry Project Setup

1. Go to [sentry.io](https://sentry.io) and create an account
2. Create a new project for your Next.js application
3. Copy the DSN from your project settings
4. Update your `.env.local` file with the DSN

## Usage Examples

### Basic Error Tracking

```typescript
import { captureError } from '@/lib/sentry';

try {
  // Your code here
} catch (error) {
  captureError(error, { context: 'user_action', action: 'send_usdc' });
}
```

### API Error Tracking

```typescript
import { captureAPIError } from '@/lib/sentry';

try {
  const response = await api.post('/api/v1/send_usdc', data);
} catch (error) {
  captureAPIError(error, '/api/v1/send_usdc', data);
}
```

### Adding Breadcrumbs

```typescript
import { addBreadcrumb } from '@/lib/sentry';

addBreadcrumb('User action', 'wallet', { 
  action: 'copy_address', 
  address: '0x...' 
});
```

### Performance Monitoring

```typescript
import { startPerformanceSpan } from '@/lib/sentry';

const span = startPerformanceSpan('API Call', 'http');
// Your API call here
span.finish();
```

## Monitoring Dashboard

Once configured, you can view your application's health in the Sentry dashboard:

1. **Issues**: View and triage errors by impact and frequency
2. **Performance**: Monitor API response times and user experience
3. **Releases**: Track the health of each deployment
4. **Users**: See error impact on specific users
5. **Sessions**: Analyze user behavior and error reproduction

## Key Metrics Tracked

### Wallet Operations
- USDC send/receive operations
- Balance fetching
- Transaction history loading
- Address copying

### KYC Process
- Modal opening/closing
- Status checking
- Verification completion
- Error handling

### WebSocket Operations
- Connection status
- Message handling
- Error tracking
- Reconnection attempts

### User Actions
- Login/logout
- Username setting
- Profile updates
- Navigation

## Privacy and Security

- Sensitive data (passwords, tokens) is automatically filtered
- User privacy is maintained in session replays
- GDPR-compliant data handling
- Configurable data sampling rates

## Troubleshooting

### Common Issues

1. **Errors not appearing in Sentry**
   - Check your DSN configuration
   - Verify network connectivity to Sentry
   - Check browser console for Sentry errors

2. **Performance data missing**
   - Ensure `tracesSampleRate` is configured
   - Check that performance spans are properly closed

3. **Session replay not working**
   - Verify `replaysSessionSampleRate` configuration
   - Check browser compatibility

### Debug Mode

Enable debug mode in development by setting:

```typescript
debug: process.env.NODE_ENV === 'development'
```

This will show Sentry initialization logs in the console.

## Best Practices

1. **Error Context**: Always provide relevant context when capturing errors
2. **Breadcrumbs**: Add breadcrumbs for important user actions
3. **Performance**: Use performance spans for slow operations
4. **User Context**: Set user context early in the user session
5. **Cleanup**: Clear user context on logout

## Support

- [Sentry Documentation](https://docs.sentry.io/)
- [Next.js Integration Guide](https://docs.sentry.io/platforms/javascript/guides/nextjs/)
- [Community Forum](https://forum.sentry.io/)

## Example Test Page

Visit `/sentry-example-page` in your application to test the Sentry integration and see how errors are captured and displayed.
