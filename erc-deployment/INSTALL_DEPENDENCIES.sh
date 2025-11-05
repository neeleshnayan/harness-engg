#!/bin/bash

# MAVC Yearn - Dependency Installation Script
# Run this script to install all required dependencies for deployment

set -e  # Exit on error

echo "================================================"
echo "  MAVC Yearn - Installing Dependencies"
echo "================================================"
echo ""

# Check if we're in the right directory
if [ ! -f "foundry.toml" ]; then
    echo "❌ Error: foundry.toml not found!"
    echo "Please run this script from the erc-deployment directory:"
    echo "  cd erc-deployment"
    echo "  bash INSTALL_DEPENDENCIES.sh"
    exit 1
fi

echo "✅ Found foundry.toml"
echo ""

# Check if Foundry is installed
if ! command -v forge &> /dev/null; then
    echo "❌ Foundry not found!"
    echo "Installing Foundry..."
    curl -L https://foundry.paradigm.xyz | bash
    foundryup
    echo "✅ Foundry installed!"
else
    echo "✅ Foundry already installed"
fi

echo ""
echo "================================================"
echo "  Installing Smart Contract Dependencies"
echo "================================================"
echo ""

# Install Yearn v3 Tokenized Strategy
echo "📦 Installing Yearn v3 Tokenized Strategy..."
if [ ! -d "lib/tokenized-strategy" ]; then
    forge install yearn/tokenized-strategy --no-commit
    echo "✅ Yearn v3 installed"
else
    echo "⚠️  Yearn v3 already installed (skipping)"
fi

# Install Uniswap V3 Periphery
echo ""
echo "📦 Installing Uniswap V3 Periphery..."
if [ ! -d "lib/v3-periphery" ]; then
    forge install Uniswap/v3-periphery --no-commit
    echo "✅ Uniswap V3 Periphery installed"
else
    echo "⚠️  Uniswap V3 Periphery already installed (skipping)"
fi

# Install Uniswap V3 Core
echo ""
echo "📦 Installing Uniswap V3 Core..."
if [ ! -d "lib/v3-core" ]; then
    forge install Uniswap/v3-core --no-commit
    echo "✅ Uniswap V3 Core installed"
else
    echo "⚠️  Uniswap V3 Core already installed (skipping)"
fi

echo ""
echo "================================================"
echo "  Updating foundry.toml"
echo "================================================"
echo ""

# Backup foundry.toml
cp foundry.toml foundry.toml.backup
echo "✅ Created backup: foundry.toml.backup"

# Check if remappings already exist
if grep -q "@yearn-vaults/" foundry.toml; then
    echo "⚠️  Remappings already configured (skipping)"
else
    echo "📝 Adding remappings to foundry.toml..."

    # Add remappings
    sed -i '/remappings = \[/a\    "@yearn-vaults/=lib/tokenized-strategy/src/",\n    "@uniswap/v3-periphery/contracts/=lib/v3-periphery/contracts/",\n    "@uniswap/v3-core/contracts/=lib/v3-core/contracts/"' foundry.toml

    echo "✅ Remappings added"
fi

echo ""
echo "================================================"
echo "  Testing Compilation"
echo "================================================"
echo ""

echo "🔨 Compiling contracts..."
forge build

if [ $? -eq 0 ]; then
    echo "✅ Compilation successful!"
else
    echo "❌ Compilation failed!"
    echo "Please check the error messages above."
    exit 1
fi

echo ""
echo "================================================"
echo "  Environment Setup"
echo "================================================"
echo ""

if [ -f ".env" ]; then
    echo "⚠️  .env file already exists (skipping creation)"
else
    echo "📝 Creating .env file template..."
    cat > .env << 'EOF'
# Deployment Configuration

# CRITICAL: Never commit this file to git!
# Add .env to .gitignore

# Deployer wallet private key (without 0x prefix)
PRIVATE_KEY=your_private_key_here

# Alchemy API key for RPC access
ALCHEMY_API_KEY=your_alchemy_api_key_here

# Etherscan API key for contract verification
ETHERSCAN_API_KEY=your_etherscan_api_key_here

# RPC URLs (automatically configured from ALCHEMY_API_KEY)
SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/${ALCHEMY_API_KEY}
MAINNET_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}
EOF
    echo "✅ Created .env template"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your keys!"
    echo "   - Get Alchemy key: https://alchemy.com"
    echo "   - Get Etherscan key: https://etherscan.io/myapikey"
    echo "   - Add your wallet private key"
fi

echo ""
echo "================================================"
echo "  Installation Complete! ✨"
echo "================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Edit .env file with your credentials:"
echo "   nano .env"
echo ""
echo "2. Fund your deployer wallet with ETH:"
echo "   - Sepolia: Get testnet ETH from https://sepoliafaucet.com"
echo "   - Check balance: cast balance YOUR_ADDRESS --rpc-url sepolia"
echo ""
echo "3. Deploy the contract:"
echo "   forge script script/DeployMAVCYearn.s.sol:DeployMAVCYearn \\"
echo "     --rpc-url sepolia \\"
echo "     --broadcast \\"
echo "     --verify \\"
echo "     -vvvv"
echo ""
echo "4. Add vault address to Firestore (see QUICK_DEPLOY.md)"
echo ""
echo "📚 Documentation:"
echo "   - Full guide: YEARN_DEPLOYMENT_GUIDE.md"
echo "   - Quick reference: QUICK_DEPLOY.md"
echo "   - Summary: ../MAVC_YEARN_SUMMARY.md"
echo ""
echo "================================================"
