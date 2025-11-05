import { BigDecimal, BigInt } from '@graphprotocol/graph-ts';
import {
  Deposit as DepositEvent,
  Withdraw as WithdrawEvent,
  MAVCPriceUpdated as MAVCPriceUpdatedEvent,
} from '../generated/MultiAssetVaultUSDCWETH/MultiAssetVaultUSDCWETH';
import {
  Deposit as MAVPDepositEvent,
  Withdraw as MAVPWithdrawEvent,
  AssetSwapIn as AssetSwapInEvent,
  AssetSwapOut as AssetSwapOutEvent,
  AllocationInitialized as AllocationInitializedEvent,
  MAVPPriceUpdated as MAVPPriceUpdatedEvent,
} from '../generated/MAVP/MAVP';
import {
  Deposit as MAVCYearnDepositEvent,
  Withdraw as MAVCYearnWithdrawEvent,
} from '../generated/MAVCYearnStrategyUSDCWETH/MAVCYearnStrategyUSDCWETH';
import {
  Deposit,
  Withdrawal,
  AssetSwapIn,
  AssetSwapOut,
  AllocationInitialized,
  VaultMetric,
  MAVCVaultMetric,
  MAVPVaultMetric,
  Participant,
  MAVCPriceUpdate,
  MAVCPriceCurrent,
  MAVPPriceUpdate,
  MAVPPriceCurrent,
  MAVCYearnVaultMetric,
} from '../generated/schema';

const VAULT_METRIC_ID = 'vault';
const MAVC_VAULT_METRIC_ID = 'mavc-vault';
const MAVP_VAULT_METRIC_ID = 'mavp-vault';
const MAVC_YEARN_VAULT_METRIC_ID = 'mavc-yearn-vault';
const USDC_DECIMALS = 6;
const SHARE_DECIMALS = 18;
const PRICE_DECIMALS = 8;

const DEPOSIT_ROLE = 'DEPOSITOR';
const WITHDRAW_ROLE = 'WITHDRAWER';

const MAVC_PRICE_CURRENT_ID = 'current';
const MAVP_PRICE_CURRENT_ID = 'current';

const ZERO_BD = BigDecimal.fromString('0');
const ZERO_BI = BigInt.zero();

function decimalScale(decimals: i32): BigDecimal {
  const ten = BigInt.fromI32(10);
  const scale = ten.pow(<u8>decimals).toBigDecimal();
  return scale;
}

function bigDecimalFromBigInt(value: BigInt, decimals: i32): BigDecimal {
  if (decimals === 0) {
    return value.toBigDecimal();
  }
  return value.toBigDecimal().div(decimalScale(decimals));
}

function getMetric(): VaultMetric {
  let metric = VaultMetric.load(VAULT_METRIC_ID);
  if (!metric) {
    metric = new VaultMetric(VAULT_METRIC_ID);
    metric.totalDeposits = ZERO_BD;
    metric.totalWithdrawals = ZERO_BD;
    metric.mintedShares = ZERO_BD;
    metric.burnedShares = ZERO_BD;
    metric.uniqueDepositors = 0;
    metric.uniqueWithdrawers = 0;
    metric.lastUpdated = ZERO_BI;
    metric.save();
  }
  return metric as VaultMetric;
}

function getMAVCMetric(): MAVCVaultMetric {
  let metric = MAVCVaultMetric.load(MAVC_VAULT_METRIC_ID);
  if (!metric) {
    metric = new MAVCVaultMetric(MAVC_VAULT_METRIC_ID);
    metric.totalDeposits = ZERO_BD;
    metric.totalWithdrawals = ZERO_BD;
    metric.mintedShares = ZERO_BD;
    metric.burnedShares = ZERO_BD;
    metric.uniqueDepositors = 0;
    metric.uniqueWithdrawers = 0;
    metric.lastUpdated = ZERO_BI;
    metric.save();
  }
  return metric as MAVCVaultMetric;
}

function getMAVPMetric(): MAVPVaultMetric {
  let metric = MAVPVaultMetric.load(MAVP_VAULT_METRIC_ID);
  if (!metric) {
    metric = new MAVPVaultMetric(MAVP_VAULT_METRIC_ID);
    metric.totalDeposits = ZERO_BD;
    metric.totalWithdrawals = ZERO_BD;
    metric.mintedShares = ZERO_BD;
    metric.burnedShares = ZERO_BD;
    metric.uniqueDepositors = 0;
    metric.uniqueWithdrawers = 0;
    metric.lastUpdated = ZERO_BI;
    metric.save();
  }
  return metric as MAVPVaultMetric;
}

function getMAVCYearnMetric(): MAVCYearnVaultMetric {
  let metric = MAVCYearnVaultMetric.load(MAVC_YEARN_VAULT_METRIC_ID);
  if (!metric) {
    metric = new MAVCYearnVaultMetric(MAVC_YEARN_VAULT_METRIC_ID);
    metric.totalDeposits = ZERO_BD;
    metric.totalWithdrawals = ZERO_BD;
    metric.mintedShares = ZERO_BD;
    metric.burnedShares = ZERO_BD;
    metric.uniqueDepositors = 0;
    metric.uniqueWithdrawers = 0;
    metric.lastUpdated = ZERO_BI;
    metric.save();
  }
  return metric as MAVCYearnVaultMetric;
}

function trackParticipant(id: string, role: string, vault: string): bool {
  const participantId = id.concat('-').concat(role).concat('-').concat(vault);
  let participant = Participant.load(participantId);
  if (participant) {
    return false;
  }
  participant = new Participant(participantId);
  participant.role = role;
  participant.save();
  return true;
}

export function handleDeposit(event: DepositEvent): void {
  const metric = getMAVCMetric();

  const assets = bigDecimalFromBigInt(event.params.assets, USDC_DECIMALS);
  const shares = bigDecimalFromBigInt(event.params.shares, SHARE_DECIMALS);

  const entity = new Deposit(event.transaction.hash
    .toHex()
    .concat('-MAVC-')
    .concat(event.logIndex.toString()));

  entity.txHash = event.transaction.hash;
  entity.sender = event.params.sender;
  entity.owner = event.params.owner;
  entity.assets = assets;
  entity.shares = shares;
  entity.timestamp = event.block.timestamp;
  entity.save();

  metric.totalDeposits = metric.totalDeposits.plus(assets);
  metric.mintedShares = metric.mintedShares.plus(shares);

  const isNewDepositor = trackParticipant(event.params.owner.toHexString(), DEPOSIT_ROLE, 'MAVC');
  if (isNewDepositor) {
    metric.uniqueDepositors += 1;
  }

  metric.lastUpdated = event.block.timestamp;
  metric.save();
}

export function handleWithdraw(event: WithdrawEvent): void {
  const metric = getMAVCMetric();

  const assets = bigDecimalFromBigInt(event.params.assets, USDC_DECIMALS);
  const shares = bigDecimalFromBigInt(event.params.shares, SHARE_DECIMALS);

  const entity = new Withdrawal(event.transaction.hash
    .toHex()
    .concat('-MAVC-')
    .concat(event.logIndex.toString()));

  entity.txHash = event.transaction.hash;
  entity.sender = event.params.sender;
  entity.receiver = event.params.receiver;
  entity.owner = event.params.owner;
  entity.assets = assets;
  entity.shares = shares;
  entity.timestamp = event.block.timestamp;
  entity.save();

  metric.totalWithdrawals = metric.totalWithdrawals.plus(assets);
  metric.burnedShares = metric.burnedShares.plus(shares);

  const isNewWithdrawer = trackParticipant(event.params.owner.toHexString(), WITHDRAW_ROLE, 'MAVC');
  if (isNewWithdrawer) {
    metric.uniqueWithdrawers += 1;
  }

  metric.lastUpdated = event.block.timestamp;
  metric.save();
}

// MAVP Event Handlers
export function handleMAVPDeposit(event: MAVPDepositEvent): void {
  const metric = getMAVPMetric();

  const assets = bigDecimalFromBigInt(event.params.assets, USDC_DECIMALS);
  const shares = bigDecimalFromBigInt(event.params.shares, SHARE_DECIMALS);

  const entity = new Deposit(event.transaction.hash
    .toHex()
    .concat('-MAVP-')
    .concat(event.logIndex.toString()));

  entity.txHash = event.transaction.hash;
  entity.sender = event.params.sender;
  entity.owner = event.params.owner;
  entity.assets = assets;
  entity.shares = shares;
  entity.timestamp = event.block.timestamp;
  entity.save();

  metric.totalDeposits = metric.totalDeposits.plus(assets);
  metric.mintedShares = metric.mintedShares.plus(shares);

  const isNewDepositor = trackParticipant(event.params.owner.toHexString(), DEPOSIT_ROLE, 'MAVP');
  if (isNewDepositor) {
    metric.uniqueDepositors += 1;
  }

  metric.lastUpdated = event.block.timestamp;
  metric.save();
}

export function handleMAVPWithdraw(event: MAVPWithdrawEvent): void {
  const metric = getMAVPMetric();

  const assets = bigDecimalFromBigInt(event.params.assets, USDC_DECIMALS);
  const shares = bigDecimalFromBigInt(event.params.shares, SHARE_DECIMALS);

  const entity = new Withdrawal(event.transaction.hash
    .toHex()
    .concat('-MAVP-')
    .concat(event.logIndex.toString()));

  entity.txHash = event.transaction.hash;
  entity.sender = event.params.sender;
  entity.receiver = event.params.receiver;
  entity.owner = event.params.owner;
  entity.assets = assets;
  entity.shares = shares;
  entity.timestamp = event.block.timestamp;
  entity.save();

  metric.totalWithdrawals = metric.totalWithdrawals.plus(assets);
  metric.burnedShares = metric.burnedShares.plus(shares);

  const isNewWithdrawer = trackParticipant(event.params.owner.toHexString(), WITHDRAW_ROLE, 'MAVP');
  if (isNewWithdrawer) {
    metric.uniqueWithdrawers += 1;
  }

  metric.lastUpdated = event.block.timestamp;
  metric.save();
}

export function handleAssetSwapIn(event: AssetSwapInEvent): void {
  const entity = new AssetSwapIn(event.transaction.hash
    .toHex()
    .concat('-')
    .concat(event.logIndex.toString()));

  entity.txHash = event.transaction.hash;
  entity.token = event.params.token;
  entity.usdcAmountIn = bigDecimalFromBigInt(event.params.usdcAmountIn, USDC_DECIMALS);
  entity.tokenAmountOut = bigDecimalFromBigInt(event.params.tokenAmountOut, 18); // Assume 18 decimals for most tokens
  entity.timestamp = event.block.timestamp;
  entity.save();
}

export function handleAssetSwapOut(event: AssetSwapOutEvent): void {
  const entity = new AssetSwapOut(event.transaction.hash
    .toHex()
    .concat('-')
    .concat(event.logIndex.toString()));

  entity.txHash = event.transaction.hash;
  entity.token = event.params.token;
  entity.tokenAmountIn = bigDecimalFromBigInt(event.params.tokenAmountIn, 18); // Assume 18 decimals for most tokens
  entity.usdcAmountOut = bigDecimalFromBigInt(event.params.usdcAmountOut, USDC_DECIMALS);
  entity.timestamp = event.block.timestamp;
  entity.save();
}

export function handleAllocationInitialized(event: AllocationInitializedEvent): void {
  const entity = new AllocationInitialized(event.transaction.hash
    .toHex()
    .concat('-')
    .concat(event.logIndex.toString()));

  entity.txHash = event.transaction.hash;
  entity.token = event.params.token;
  entity.allocationBps = event.params.allocationBps;
  entity.timestamp = event.block.timestamp;
  entity.save();
}

export function handleMAVCPriceUpdated(event: MAVCPriceUpdatedEvent): void {
  // Create immutable price update record
  const priceUpdate = new MAVCPriceUpdate(event.transaction.hash
    .toHex()
    .concat('-')
    .concat(event.logIndex.toString()));

  const priceInUSD = bigDecimalFromBigInt(event.params.newPrice, PRICE_DECIMALS);

  priceUpdate.txHash = event.transaction.hash;
  priceUpdate.price = priceInUSD;
  priceUpdate.timestamp = event.block.timestamp;
  priceUpdate.save();

  // Update current price entity
  let currentPrice = MAVCPriceCurrent.load(MAVC_PRICE_CURRENT_ID);
  if (!currentPrice) {
    currentPrice = new MAVCPriceCurrent(MAVC_PRICE_CURRENT_ID);
    currentPrice.updateCount = 0;
  }

  currentPrice.price = priceInUSD;
  currentPrice.lastUpdate = event.block.timestamp;
  currentPrice.updateCount += 1;
  currentPrice.save();
}

export function handleMAVPPriceUpdated(event: MAVPPriceUpdatedEvent): void {
  // Create immutable price update record
  const priceUpdate = new MAVPPriceUpdate(event.transaction.hash
    .toHex()
    .concat('-')
    .concat(event.logIndex.toString()));

  const priceInUSD = bigDecimalFromBigInt(event.params.newPrice, PRICE_DECIMALS);

  priceUpdate.txHash = event.transaction.hash;
  priceUpdate.price = priceInUSD;
  priceUpdate.timestamp = event.block.timestamp;
  priceUpdate.save();

  // Update current price entity
  let currentPrice = MAVPPriceCurrent.load(MAVP_PRICE_CURRENT_ID);
  if (!currentPrice) {
    currentPrice = new MAVPPriceCurrent(MAVP_PRICE_CURRENT_ID);
    currentPrice.updateCount = 0;
  }

  currentPrice.price = priceInUSD;
  currentPrice.lastUpdate = event.block.timestamp;
  currentPrice.updateCount += 1;
  currentPrice.save();
}

export function handleMAVCYearnDeposit(event: MAVCYearnDepositEvent): void {
  const metric = getMAVCYearnMetric();

  const assets = bigDecimalFromBigInt(event.params.assets, USDC_DECIMALS);
  const shares = bigDecimalFromBigInt(event.params.shares, SHARE_DECIMALS);

  const entity = new Deposit(event.transaction.hash
    .toHex()
    .concat('-MAVC-YEARN-')
    .concat(event.logIndex.toString()));

  entity.txHash = event.transaction.hash;
  entity.sender = event.params.caller;
  entity.owner = event.params.owner;
  entity.assets = assets;
  entity.shares = shares;
  entity.timestamp = event.block.timestamp;
  entity.save();

  metric.totalDeposits = metric.totalDeposits.plus(assets);
  metric.mintedShares = metric.mintedShares.plus(shares);

  const isNewDepositor = trackParticipant(event.params.owner.toHexString(), DEPOSIT_ROLE, 'MAVC-YEARN');
  if (isNewDepositor) {
    metric.uniqueDepositors += 1;
  }

  metric.lastUpdated = event.block.timestamp;
  metric.save();
}

export function handleMAVCYearnWithdraw(event: MAVCYearnWithdrawEvent): void {
  const metric = getMAVCYearnMetric();

  const assets = bigDecimalFromBigInt(event.params.assets, USDC_DECIMALS);
  const shares = bigDecimalFromBigInt(event.params.shares, SHARE_DECIMALS);

  const entity = new Withdrawal(event.transaction.hash
    .toHex()
    .concat('-MAVC-YEARN-')
    .concat(event.logIndex.toString()));

  entity.txHash = event.transaction.hash;
  entity.sender = event.params.caller;
  entity.receiver = event.params.receiver;
  entity.owner = event.params.owner;
  entity.assets = assets;
  entity.shares = shares;
  entity.timestamp = event.block.timestamp;
  entity.save();

  metric.totalWithdrawals = metric.totalWithdrawals.plus(assets);
  metric.burnedShares = metric.burnedShares.plus(shares);

  const isNewWithdrawer = trackParticipant(event.params.owner.toHexString(), WITHDRAW_ROLE, 'MAVC-YEARN');
  if (isNewWithdrawer) {
    metric.uniqueWithdrawers += 1;
  }

  metric.lastUpdated = event.block.timestamp;
  metric.save();
}
