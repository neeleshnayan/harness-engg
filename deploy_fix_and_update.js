const { ethers } = require("ethers");
const fs = require("fs");
const path = require("path");

async function main() {
    // 1. Setup Provider & Signer
    const rpcUrl = "https://sepolia.infura.io/v3/2f996d80c4664ac68e012f3052a31ee3";
    const privateKey = "0xccb53cc1bdc9aac716c44ef9cf0c88973ec34296ba50ebc4ce94f0029afdb58d";

    const provider = new ethers.JsonRpcProvider(rpcUrl);
    const wallet = new ethers.Wallet(privateKey, provider);

    console.log("Deploying Fixed Strategy Implementation with account:", wallet.address);

    // 2. Load Artifacts
    // Note: We need YearnUSDCWETHStrategyV1 artifact.
    // It should be in out/YearnUSDCWETHStrategyV1.sol/YearnUSDCWETHStrategyV1.json
    const hedgeFundPath = path.resolve(__dirname, "../Krypton_HedgeFund");
    const artifactPath = path.join(hedgeFundPath, "out/YearnUSDCWETHStrategyV1.sol/YearnUSDCWETHStrategyV1.json");

    if (!fs.existsSync(artifactPath)) {
        throw new Error(`Artifact not found at ${artifactPath}`);
    }
    const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf8"));

    // 3. Deploy
    // Constructor args for Implementation: 
    // ERC4626 implementation usually doesn't take constructor args or takes immutable args?
    // Let's check the solidity file again.
    // constructor(
    //    address _asset,
    //    string memory _name,
    //    address _tokenizedStrategy
    // ) BaseStrategy(_asset, _name, _tokenizedStrategy)

    // We need USDC, Name, and TokenizedStrategy addresses for the MASTER implementation constructor.
    // These values for the master implementation don't matter much (logic is in initialize), 
    // BUT BaseStrategy constructor might set immutables.
    // Let's use the same Sepolia values as before.

    const USDC = "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238";
    const NAME = "Yearn WETH V2";
    // We MUST use the NEW TokenizedStrategy Implementation address we deployed!
    const TOKENIZED_STRATEGY_IMPL = "0xAe6a5aC4035b5fD9438164D0768Bd366CaCAb6FF";

    const Factory = new ethers.ContractFactory(artifact.abi, artifact.bytecode.object, wallet);

    console.log("Deploying implementation...");
    const contract = await Factory.deploy(USDC, NAME, TOKENIZED_STRATEGY_IMPL);
    await contract.waitForDeployment();
    const address = await contract.getAddress();

    console.log("=================================================");
    console.log("Fixed Strategy Implementation deployed at:", address);
    console.log("=================================================");

    // 4. Update Factory
    const FACTORY_ADDRESS = "0xB53183894a5C5bc9cE7b368E3dEA013bCaA38A3b";
    // Load Factory Artifact
    const factoryArtifactPath = path.join(hedgeFundPath, "out/YearnStrategyFactory.sol/YearnStrategyFactory.json");
    const factoryArtifact = JSON.parse(fs.readFileSync(factoryArtifactPath, "utf8"));

    const factory = new ethers.Contract(FACTORY_ADDRESS, factoryArtifact.abi, wallet);

    console.log("Updating Factory Implementation...");
    const tx = await factory.updateImplementation(address);
    console.log("Update Transaction sent:", tx.hash);
    await tx.wait();
    console.log("Factory updated successfully!");
}

main().catch(console.error);
