@echo off
REM MAVC Yearn - Dependency Installation Script (Windows)
REM Run this script to install all required dependencies for deployment

echo ================================================
echo   MAVC Yearn - Installing Dependencies
echo ================================================
echo.

REM Check if we're in the right directory
if not exist "foundry.toml" (
    echo [ERROR] foundry.toml not found!
    echo Please run this script from the erc-deployment directory
    echo   cd erc-deployment
    echo   INSTALL_DEPENDENCIES.bat
    exit /b 1
)

echo [OK] Found foundry.toml
echo.

REM Check if Foundry is installed
where forge >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Foundry not found!
    echo.
    echo Please install Foundry first:
    echo   1. Visit: https://book.getfoundry.sh/getting-started/installation
    echo   2. Run PowerShell as Administrator
    echo   3. Run: irm https://raw.githubusercontent.com/foundry-rs/foundry/master/foundryup/install.ps1 ^| iex
    echo   4. Then run this script again
    pause
    exit /b 1
) else (
    echo [OK] Foundry is installed
)

echo.
echo ================================================
echo   Installing Smart Contract Dependencies
echo ================================================
echo.

REM Install Yearn v3 Tokenized Strategy
echo Installing Yearn v3 Tokenized Strategy...
if not exist "lib\tokenized-strategy" (
    forge install yearn/tokenized-strategy --no-commit
    echo [OK] Yearn v3 installed
) else (
    echo [SKIP] Yearn v3 already installed
)

echo.

REM Install Uniswap V3 Periphery
echo Installing Uniswap V3 Periphery...
if not exist "lib\v3-periphery" (
    forge install Uniswap/v3-periphery --no-commit
    echo [OK] Uniswap V3 Periphery installed
) else (
    echo [SKIP] Uniswap V3 Periphery already installed
)

echo.

REM Install Uniswap V3 Core
echo Installing Uniswap V3 Core...
if not exist "lib\v3-core" (
    forge install Uniswap/v3-core --no-commit
    echo [OK] Uniswap V3 Core installed
) else (
    echo [SKIP] Uniswap V3 Core already installed
)

echo.
echo ================================================
echo   Updating foundry.toml
echo ================================================
echo.

REM Backup foundry.toml
copy foundry.toml foundry.toml.backup >nul
echo [OK] Created backup: foundry.toml.backup

REM Check if remappings already exist
findstr /C:"@yearn-vaults/" foundry.toml >nul
if %errorlevel% equ 0 (
    echo [SKIP] Remappings already configured
) else (
    echo Adding remappings to foundry.toml...
    echo.
    echo [MANUAL STEP REQUIRED]
    echo Please add these lines to your foundry.toml remappings section:
    echo.
    echo     "@yearn-vaults/=lib/tokenized-strategy/src/",
    echo     "@uniswap/v3-periphery/contracts/=lib/v3-periphery/contracts/",
    echo     "@uniswap/v3-core/contracts/=lib/v3-core/contracts/"
    echo.
    echo Press any key to open foundry.toml in notepad...
    pause >nul
    notepad foundry.toml
)

echo.
echo ================================================
echo   Testing Compilation
echo ================================================
echo.

echo Compiling contracts...
forge build

if %errorlevel% equ 0 (
    echo [OK] Compilation successful!
) else (
    echo [ERROR] Compilation failed!
    echo Please check the error messages above.
    pause
    exit /b 1
)

echo.
echo ================================================
echo   Environment Setup
echo ================================================
echo.

if exist ".env" (
    echo [SKIP] .env file already exists
) else (
    echo Creating .env file template...
    (
        echo # Deployment Configuration
        echo.
        echo # CRITICAL: Never commit this file to git!
        echo # Add .env to .gitignore
        echo.
        echo # Deployer wallet private key ^(without 0x prefix^)
        echo PRIVATE_KEY=your_private_key_here
        echo.
        echo # Alchemy API key for RPC access
        echo ALCHEMY_API_KEY=your_alchemy_api_key_here
        echo.
        echo # Etherscan API key for contract verification
        echo ETHERSCAN_API_KEY=your_etherscan_api_key_here
        echo.
        echo # RPC URLs ^(automatically configured from ALCHEMY_API_KEY^)
        echo SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/${ALCHEMY_API_KEY}
        echo MAINNET_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}
    ) > .env
    echo [OK] Created .env template
    echo.
    echo [IMPORTANT] Edit .env and add your keys!
    echo    - Get Alchemy key: https://alchemy.com
    echo    - Get Etherscan key: https://etherscan.io/myapikey
    echo    - Add your wallet private key
    echo.
    echo Press any key to open .env in notepad...
    pause >nul
    notepad .env
)

echo.
echo ================================================
echo   Installation Complete!
echo ================================================
echo.
echo Next steps:
echo.
echo 1. Edit .env file with your credentials
echo    ^(should already be open in notepad^)
echo.
echo 2. Fund your deployer wallet with ETH:
echo    - Sepolia: Get testnet ETH from https://sepoliafaucet.com
echo    - Check balance: cast balance YOUR_ADDRESS --rpc-url sepolia
echo.
echo 3. Deploy the contract:
echo    forge script script/DeployMAVCYearn.s.sol:DeployMAVCYearn --rpc-url sepolia --broadcast --verify -vvvv
echo.
echo 4. Add vault address to Firestore ^(see QUICK_DEPLOY.md^)
echo.
echo Documentation:
echo    - Full guide: YEARN_DEPLOYMENT_GUIDE.md
echo    - Quick reference: QUICK_DEPLOY.md
echo    - Summary: ..\MAVC_YEARN_SUMMARY.md
echo.
echo ================================================
echo.
pause
