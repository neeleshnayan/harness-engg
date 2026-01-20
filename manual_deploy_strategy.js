const { ethers } = require("ethers");
const fs = require("fs");
const path = require("path");

async function main() {
    console.log("Starting manual strategy deployment test...");

    // 1. Setup Provider & Signer
    const rpcUrl = "https://sepolia.infura.io/v3/2f996d80c4664ac68e012f3052a31ee3";
    const privateKey = "0xccb53cc1bdc9aac716c44ef9cf0c88973ec34296ba50ebc4ce94f0029afdb58d";

    const provider = new ethers.JsonRpcProvider(rpcUrl);
    const wallet = new ethers.Wallet(privateKey, provider);

    console.log("Account:", wallet.address);

    // 2. Load Factory Artifact
    const hedgeFundPath = path.resolve(__dirname, "../Krypton_HedgeFund");
    const factoryArtifactPath = path.join(hedgeFundPath, "out/YearnStrategyFactory.sol/YearnStrategyFactory.json");
    if (!fs.existsSync(factoryArtifactPath)) throw new Error(`Artifact not found at ${factoryArtifactPath}`);

    const factoryArtifact = JSON.parse(fs.readFileSync(factoryArtifactPath, "utf8"));
    const FACTORY_ADDRESS = "0xB53183894a5C5bc9cE7b368E3dEA013bCaA38A3b";

    const factory = new ethers.Contract(FACTORY_ADDRESS, factoryArtifact.abi, wallet);

    // 3. Deployment Parameters
    const USDC = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238";
    const WETH = "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14";
    // TokenizedStrategy Implementation address (passed as _vault parameter)
    const TOKENIZED_STRATEGY_IMPL = "0xAe6a5aC4035b5fD9438164D0768Bd366CaCAb6FF";
    const NAME = "Yearn WETH Manual Test";
    const ADMIN = wallet.address;
    const FEE = 2000; // 20%

    // 4. Execute Deployment
    // deployStrategy(address _asset, string _name, address _targetToken, address _vault, address _admin, uint24 _fee)
    console.log("Sending deployStrategy transaction...");
    try {
        // Estimate gas first to check for reverts
        const gasEstimate = await factory.deployStrategy.estimateGas(USDC, NAME, WETH, TOKENIZED_STRATEGY_IMPL, ADMIN, FEE);
        console.log("Gas Estimate:", gasEstimate.toString());

        const tx = await factory.deployStrategy(USDC, NAME, WETH, TOKENIZED_STRATEGY_IMPL, ADMIN, FEE);
        console.log("Transaction Hash:", tx.hash);

        console.log("Waiting for confirmation...");
        const receipt = await tx.wait();

        // Find StrategyDeployed event
        // Event signature: StrategyDeployed(address indexed strategy, string name, address indexed asset, address indexed targetToken, address vault)
        const eventTopic = factory.interface.getEvent("StrategyDeployed").topicHash;
        const log = receipt.logs.find(x => x.topics[0] === eventTopic);

        if (log) {
            const parsedLog = factory.interface.parseLog(log);
            console.log("========================================");
            console.log("SUCCESS! Strategy Deployed.");
            console.log("Strategy Address:", parsedLog.args.strategy);
            console.log("Name:", parsedLog.args.name);
            console.log("Asset:", parsedLog.args.asset);
            console.log("Vault/Impl:", parsedLog.args.vault);
            console.log("========================================");
        } else {
            console.log("Transaction successful but StrategyDeployed event not found.");
        }

    } catch (error) {
        console.error("DEPLOYMENT FAILED");
        if (error.data) {
            console.error("Revert Data:", error.data);
        }
        console.error(error);
    }
}

main().catch(console.error);
