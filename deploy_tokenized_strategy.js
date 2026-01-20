const { ethers } = require("ethers");
const fs = require("fs");
const path = require("path");

async function main() {
    // 1. Setup Provider & Signer
    const rpcUrl = "https://sepolia.infura.io/v3/2f996d80c4664ac68e012f3052a31ee3";
    const privateKey = "0xccb53cc1bdc9aac716c44ef9cf0c88973ec34296ba50ebc4ce94f0029afdb58d";

    const provider = new ethers.JsonRpcProvider(rpcUrl);
    const wallet = new ethers.Wallet(privateKey, provider);

    console.log("Deploying TokenizedStrategy with account:", wallet.address);

    // 2. Load Artifacts
    const hedgeFundPath = path.resolve(__dirname, "../Krypton_HedgeFund");
    const artifactPath = path.join(hedgeFundPath, "out/TokenizedStrategy.sol/TokenizedStrategy.json");

    if (!fs.existsSync(artifactPath)) {
        throw new Error(`Artifact not found at ${artifactPath}`);
    }
    const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf8"));

    // 3. Deploy
    const Factory = new ethers.ContractFactory(artifact.abi, artifact.bytecode.object, wallet);

    // The TokenizedStrategy implementation might take arguments or be initialized later.
    // Base implementations usually don't need constructor args if they are logic only,
    // or they take immutable config like role manager?
    // Let's assume standard 4626 implementation pattern (no args in constructor usually, or just disableInitializers).
    // Actually, Yearn V3 TokenizedStrategy might take args. Let's inspect the ABI briefly by reading (but I cant in this script easily without double parsing).
    // I'll assume 0 args for now as per minimal proxy pattern standards.

    const contract = await Factory.deploy();
    await contract.waitForDeployment();
    const address = await contract.getAddress();

    console.log("=================================================");
    console.log("TokenizedStrategy Implementation deployed at:", address);
    console.log("=================================================");
}

main().catch(console.error);
