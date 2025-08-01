# Transak On-Ramp Setup

This guide explains how to set up Transak on-ramp widget that integrates with Sumsub KYC for USDC purchases.

## Prerequisites

1. A Transak account
2. Access to Transak dashboard
3. Your application's wallet addresses (for destination configuration)
4. Sumsub KYC integration (already configured)

## Setup Steps

### 1. Create a Transak Application

1. Go to [Transak Dashboard](https://dashboard.transak.com/)
2. Sign in with your Transak account
3. Create a new application
4. Navigate to your project's **API Keys** tab
5. Generate your API key
6. Configure your application settings

### 2. Configure Environment Variables

#### Frontend Configuration
Create a `.env.local` file in the frontend directory with the following variables:

```env
# Transak Configuration
NEXT_PUBLIC_TRANSAK_API_KEY=your-transak-api-key-here
NEXT_PUBLIC_TRANSAK_ENVIRONMENT=STAGING

# API Configuration
NEXT_PUBLIC_API_URL=https://api.kryptonfund.com
```

**Important**: 
- Replace `your-transak-api-key-here` with your actual Transak API Key
- Use `STAGING` for development/testing, `PRODUCTION` for live environment

### 3. Configure Your Application in Transak Dashboard

1. In your Transak dashboard, configure the following settings:
   - **Allowed Origins**: Add your frontend domain (e.g., `https://yourdomain.com`)
   - **Redirect URLs**: Add your success/error redirect URLs (e.g., `https://yourdomain.com/wallet`)
   - **Webhook URL**: Add your webhook endpoint (e.g., `https://yourdomain.com/api/v1/transak-webhook`)
   - **KYC Status URL**: Add your KYC status endpoint (e.g., `https://yourdomain.com/api/v1/kyc/status/{email}`)
   - **Supported Assets**: Ensure USDC is enabled
   - **Supported Networks**: Enable Ethereum Sepolia (for testnet)
   - **KYC Integration**: Configure Sumsub integration
   - **Payment Methods**: Enable credit/debit cards and bank transfers

2. **KYC Configuration in Transak Dashboard:**
   - **KYC Level**: Set to Level 1 or disable for verified users
   - **KYC Provider**: Configure Sumsub as the KYC provider
   - **KYC Skip**: Enable "Skip KYC for verified users" option
   - **KYC Integration**: Enable Sumsub integration settings
   - **Test Mode**: Enable test mode for development

### 4. Test the Integration

1. Start your frontend application
2. Navigate to the wallet page
3. Click the "Buy" button to open the Transak widget
4. Test the purchase flow with a small amount

## Configuration Details

### Integration Method
- **Popup Window Integration**: Opens Transak in a new popup window
- **KYC Integration**: Integrates with existing Sumsub KYC
- **Skip KYC**: Automatically skips KYC if user is already verified
- **Secure**: Uses Transak's official payment platform
- **Fallback**: Manual "Open Transak" button if popup is blocked

### Supported Payment Methods
- Credit/Debit Cards
- Bank Transfers
- Apple Pay / Google Pay

### Supported Networks
- **Ethereum Sepolia (testnet)** - Configured to match Circle wallet blockchain
- **USDC Token Contract**: `0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238` (Sepolia)
- Can be extended to mainnet when ready

**Important**: The Transak widget is configured to use the same blockchain network (ETH-SEPOLIA) as your Circle wallet to ensure test USDC purchases are properly added to the customer's wallet.

### Blockchain Configuration
The Transak widget is configured to match your Circle wallet blockchain:

- **Network**: Ethereum Sepolia (testnet)
- **Token**: USDC
- **Contract Address**: `0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238`
- **Environment**: Staging (testnet mode)

This ensures that test USDC purchases via Transak are sent to the same blockchain network as your Circle wallet, allowing customers to see their purchased USDC in their wallet balance.

### User Data Integration
The integration automatically passes:
- User's wallet address (destination)
- User's email (if available)
- KYC status (to skip verification if already approved)

## KYC Integration

### Sumsub Integration
The Transak widget is configured to:
- Use existing Sumsub KYC verification
- Skip KYC process if user is already approved
- Require KYC only for new users or unverified users

### KYC Flow
1. **Verified Users**: KYC is skipped, direct to payment
2. **Unverified Users**: KYC Level 1 is required (minimal requirements)
3. **KYC Status**: Displayed in the modal to inform users
4. **KYC Level**: Set to Level 1 for lower verification requirements

### Webhook Integration
The backend includes a webhook endpoint (`/api/v1/transak-webhook`) that:
- Receives order status updates from Transak
- Logs successful and failed transactions
- Can be extended to update user records and send notifications

## Troubleshooting

### Common Issues

1. **"API Key not found" error**
   - Verify your `NEXT_PUBLIC_TRANSAK_API_KEY` is correct
   - Ensure your app is properly configured in Transak dashboard
   - Make sure you've replaced the placeholder with your actual API Key

2. **"Origin not allowed" error**
   - Add your domain to the allowed origins in Transak dashboard
   - For local development, add `http://localhost:3000`
   - Ensure your app is properly configured

3. **Payment methods not showing**
   - Verify your Transak account is properly verified
   - Check that the required payment methods are enabled in your app settings

4. **KYC not working**
   - Ensure Sumsub integration is properly configured
   - Check that KYC status is being passed correctly
   - Verify webhook endpoints are working

5. **Popup not opening**
   - Check if popup blockers are enabled in the browser
   - Use the manual "Open Transak" button as fallback
   - Ensure the domain is allowed in browser popup settings

6. **KYC still required despite being verified**
   - Check Transak dashboard KYC configuration
   - Ensure Sumsub integration is properly configured
   - Verify KYC status endpoint is accessible
   - Check if KYC skip options are enabled in Transak dashboard
   - Try using test mode for development

7. **USDC not appearing in wallet after purchase**
   - Verify the blockchain network is set to Ethereum Sepolia (testnet)
   - Check that the USDC token contract address is correct for Sepolia
   - Ensure the wallet address is on the same network (Sepolia)
   - Verify the purchase was completed successfully in Transak
   - Check if the Circle wallet is configured for ETH-SEPOLIA network



### Environment Variables

#### Frontend Variables
| Variable | Description | Required |
|----------|-------------|----------|
| `NEXT_PUBLIC_TRANSAK_API_KEY` | Your Transak API Key | Yes |
| `NEXT_PUBLIC_TRANSAK_ENVIRONMENT` | Environment (STAGING/PRODUCTION) | Yes |

## Security Considerations

1. **API Key Security**: The API Key is public and safe to include in frontend code
2. **User Data**: Only pass necessary user data (wallet address, email, KYC status)
3. **Network Security**: Use HTTPS in production
4. **Origin Validation**: Always validate origins in your Transak dashboard

## Migration from Coinbase

The migration from Coinbase CDP to Transak includes:

1. ✅ Replaced `CoinbaseCDPModal` with `TransakWidgetModal`
2. ✅ Updated WalletPage component to use new modal
3. ✅ Removed Coinbase-specific code and dependencies
4. ✅ Added Transak configuration and popup window handling
5. ✅ Implemented Sumsub KYC integration
6. ✅ Added KYC status checking and skipping
7. ✅ Added fallback manual button for popup blockers

## Next Steps

1. Set up your Transak application
2. Configure your API keys
3. Test the integration
4. Deploy to production when ready

## Features

- **Seamless KYC Integration**: Uses existing Sumsub KYC
- **KYC Skipping**: Automatically skips KYC for verified users
- **Multiple Payment Methods**: Credit cards, bank transfers, digital wallets
- **Real-time Status**: Shows KYC status in the modal
- **Secure Transactions**: Uses Transak's secure platform
- **User-Friendly**: Clear messaging about KYC requirements 