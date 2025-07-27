# Coinbase CDP On-Ramp Setup

This guide explains how to set up Coinbase CDP (Coinbase Developer Platform) on-ramp to replace Transak for USDC purchases.

## Prerequisites

1. A Coinbase Developer account
2. Access to Coinbase CDP dashboard
3. Your application's wallet addresses (for destination configuration)

## Setup Steps

### 1. Create a Coinbase CDP Application

1. Go to [Coinbase Developer Platform](https://developer.coinbase.com/)
2. Sign in with your Coinbase account
3. Create a new application
4. Navigate to your project's **API Keys** tab
5. Select the **Secret API Keys** section
6. Click **Create API key** to create a Secret API Key
7. Configure your key settings (IP allowlist recommended)
8. Download and securely store your Secret API Key

### 2. Configure Environment Variables

#### Frontend Configuration
Create a `.env.local` file in the frontend directory with the following variables:

```env
# Coinbase CDP Configuration
NEXT_PUBLIC_COINBASE_APP_ID=your-coinbase-app-id-here
NEXT_PUBLIC_COINBASE_ENVIRONMENT=sandbox

# API Configuration
NEXT_PUBLIC_API_URL=https://kryptonpaybackend-production.up.railway.app
```

#### Backend Configuration
Add the following environment variable to your backend:

```env
# Coinbase CDP Configuration (Secure Init)
COINBASE_SECRET_API_KEY=your-coinbase-secret-api-key-here
```

**Important**: 
- Replace `your-coinbase-secret-api-key-here` with your actual Coinbase CDP Secret API Key
- This is required for the new Secure Init authentication system
- You'll need to create a Secret API Key in the CDP Portal (not a Client API Key)

### 3. Configure Your Application in Coinbase CDP Dashboard

1. In your Coinbase CDP dashboard, configure the following settings:
   - **Allowed Origins**: Add your frontend domain (e.g., `https://yourdomain.com`)
   - **Redirect URLs**: Add your success/error redirect URLs (e.g., `https://yourdomain.com/wallet`)
   - **Supported Assets**: Ensure USDC is enabled
   - **Supported Networks**: Enable Ethereum Sepolia (for testnet)
   - **Integration Type**: Set to "Redirect" or "Popup" (not iframe)
   - **Payment Methods**: Enable credit/debit cards and bank transfers

### 4. Test the Integration

1. Start your frontend application
2. Navigate to the wallet page
3. Click the "Buy" button to open the Coinbase CDP modal
4. Test the purchase flow with a small amount

## Configuration Details

### Integration Method
- **Secure Init**: Uses Coinbase's new Secure Init authentication system
- **Session Tokens**: Generates secure session tokens server-side
- **Popup Window**: Opens Coinbase Pay in a new popup window
- **No iframe**: Avoids Content Security Policy (CSP) issues
- **Secure**: Uses Coinbase's official payment platform

### Supported Payment Methods
- Credit/Debit Cards
- Bank Transfers

### Supported Networks
- Ethereum Sepolia (testnet)
- Can be extended to mainnet when ready

### User Data Integration
The integration automatically passes:
- User's wallet address (destination)
- User's email (if available)

## Troubleshooting

### Common Issues

1. **"App ID not found" error**
   - Verify your `NEXT_PUBLIC_COINBASE_APP_ID` is correct
   - Ensure your app is properly configured in Coinbase CDP dashboard
   - Make sure you've replaced the placeholder with your actual App ID

2. **"Origin not allowed" error**
   - Add your domain to the allowed origins in Coinbase CDP dashboard
   - For local development, add `http://localhost:3000`
   - Ensure your app is configured for "Redirect" or "Popup" integration (not iframe)

3. **Payment methods not showing**
   - Verify your Coinbase CDP account is properly verified
   - Check that the required payment methods are enabled in your app settings

4. **404 errors from Coinbase API**
   - Ensure your Secret API Key is properly configured in the backend environment variables
   - Verify your Secret API Key is correct in the Coinbase CDP dashboard
   - Make sure you're using a Secret API Key (not a Client API Key)

5. **"Missing or invalid sessionToken" error**
   - This integration now uses Secure Init with session tokens
   - Ensure your Secret API Key is properly configured
   - Verify that the session token generation is working correctly
   - Check that the destination wallet address is valid
   - Session tokens expire after 5 minutes and are single-use

### Environment Variables

#### Frontend Variables
| Variable | Description | Required |
|----------|-------------|----------|
| `NEXT_PUBLIC_COINBASE_APP_ID` | Your Coinbase CDP App ID | Yes |
| `NEXT_PUBLIC_COINBASE_ENVIRONMENT` | Environment (sandbox/production) | Yes |

#### Backend Variables
| Variable | Description | Required |
|----------|-------------|----------|
| `COINBASE_SECRET_API_KEY` | Your Coinbase CDP Secret API Key | Yes |

## Security Considerations

1. **App ID Security**: The App ID is public and safe to include in frontend code
2. **User Data**: Only pass necessary user data (wallet address, email)
3. **Network Security**: Use HTTPS in production
4. **Origin Validation**: Always validate origins in your Coinbase CDP dashboard

## Migration from Transak

The migration from Transak to Coinbase CDP includes:

1. ✅ Replaced `TransakWidgetModal` with `CoinbaseCDPModal`
2. ✅ Updated WalletPage component to use new modal
3. ✅ Removed Transak-specific code and dependencies
4. ✅ Added Coinbase CDP configuration and event handling
5. ✅ Implemented popup window approach to avoid CSP issues
6. ✅ Implemented Secure Init authentication with session tokens

## Next Steps

1. Set up your Coinbase CDP application
2. Configure environment variables
3. Test the integration
4. Deploy to production when ready 