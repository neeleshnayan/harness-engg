const { ethers } = require("ethers");
const fs = require("fs");
const path = require("path");

async function main() {
    // 1. Setup Provider & Signer
    const rpcUrl = "https://sepolia.infura.io/v3/2f996d80c4664ac68e012f3052a31ee3";
    const privateKey = "0xccb53cc1bdc9aac716c44ef9cf0c88973ec34296ba50ebc4ce94f0029afdb58d";
    const factoryAddress = "0xB53183894a5C5bc9cE7b368E3dEA013bCaA38A3b"; // Previously deployed factory

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

    // The constructor takes _factory address
    console.log("Deploying with Factory Address:", factoryAddress);
    const contract = await Factory.deploy(factoryAddress);
    await contract.waitForDeployment();
    const address = await contract.getAddress();

    console.log("=================================================");
    console.log("New TokenizedStrategy Implementation deployed at:", address);
    console.log("=================================================");
}

main().catch(console.error);
