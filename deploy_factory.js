const { ethers } = require("ethers");
const fs = require("fs");
const path = require("path");

async function main() {
    // 1. Setup Provider & Signer
    const rpcUrl = "https://sepolia.infura.io/v3/2f996d80c4664ac68e012f3052a31ee3";
    const privateKey = "0xccb53cc1bdc9aac716c44ef9cf0c88973ec34296ba50ebc4ce94f0029afdb58d";

    const provider = new ethers.JsonRpcProvider(rpcUrl);
    const wallet = new ethers.Wallet(privateKey, provider);

    console.log("Deploying with account:", wallet.address);

    // 2. Load Artifacts
    const hedgeFundPath = path.resolve(__dirname, "../Krypton_HedgeFund");

    // Load Implementation
    const implArtifactPath = path.join(hedgeFundPath, "out/YearnUSDCWETHStrategyV1.sol/YearnUSDCWETHStrategyV1.json");
    if (!fs.existsSync(implArtifactPath)) {
        throw new Error(`Implementation artifact not found at ${implArtifactPath}`);
    }
    const implArtifact = JSON.parse(fs.readFileSync(implArtifactPath, "utf8"));

    // Load Factory
    const factoryArtifactPath = path.join(hedgeFundPath, "out/YearnStrategyFactory.sol/YearnStrategyFactory.json");
    if (!fs.existsSync(factoryArtifactPath)) {
        throw new Error(`Factory artifact not found at ${factoryArtifactPath}`);
    }
    const factoryArtifact = JSON.parse(fs.readFileSync(factoryArtifactPath, "utf8"));

    // 3. Deploy Implementation
    console.log("Deploying Implementation...");
    const ImplFactory = new ethers.ContractFactory(implArtifact.abi, implArtifact.bytecode.object, wallet);

    // Constructor args: asset, name, tokenizedStrategy
    // Using Sepolia defaults for constructor validation
    const USDC = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238";
    const PLACEHOLDER_STRAT = "0xBB51273D6c746910C7C06fe718f30c936170feD0"; // Random address

    const implementation = await ImplFactory.deploy(USDC, "IMPL", PLACEHOLDER_STRAT);
    await implementation.waitForDeployment();
    const implAddress = await implementation.getAddress();
    console.log("Implementation deployed at:", implAddress);

    // 4. Deploy Factory
    console.log("Deploying Factory...");
    const FactoryFactory = new ethers.ContractFactory(factoryArtifact.abi, factoryArtifact.bytecode.object, wallet);

    const UNISWAP_V3_ROUTER = "0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E";
    const QUOTER = "0xEd1f6473345F45b75F8179591dd5bA1888cf2FB3";
    const KEEPER = "0x63E6D9a78ED79a6Ca7ceed418a9b78A8f08C7335";

    const factory = await FactoryFactory.deploy(
        implAddress,
        UNISWAP_V3_ROUTER,
        QUOTER,
        KEEPER
    );
    await factory.waitForDeployment();
    const factoryAddress = await factory.getAddress();

    console.log("=================================================");
    console.log("Factory deployed at:", factoryAddress);
    console.log("=================================================");
}

main().catch(console.error);
