import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  TransactionLikelihood,
  TransactionLikelihoodResult,
  getLikelihoodDisplay,
  TransactionStatusUpdate,
  getTransactionStageMessage,
} from '../../services/transactionLikelihood';

interface TransactionStatusIndicatorProps {
  likelihoodResult?: TransactionLikelihoodResult;
  status: TransactionStatusUpdate;
  showDetails?: boolean;
}

export const TransactionStatusIndicator: React.FC<TransactionStatusIndicatorProps> = ({
  likelihoodResult,
  status,
  showDetails = true,
}) => {
  const display = likelihoodResult ? getLikelihoodDisplay(likelihoodResult.likelihood) : null;
  const stageMessage = getTransactionStageMessage(status.stage);

  // Color coding based on stage and likelihood
  const getStageColor = () => {
    if (status.stage === 'failed') return '#EF4444'; // red
    if (status.stage === 'confirmed') return '#10B981'; // green
    if (display) return display.color;
    return '#3B82F6'; // blue (default)
  };

  const progressPercentage = {
    validating: 10,
    signing: 25,
    broadcasting: 50,
    confirming: 75,
    confirmed: 100,
    failed: 100,
  }[status.stage];

  return (
    <div className="transaction-status-indicator">
      {/* Progress Bar */}
      <div className="progress-container">
        <div className="progress-bar-bg">
          <motion.div
            className="progress-bar-fill"
            initial={{ width: 0 }}
            animate={{ width: `${progressPercentage}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            style={{
              backgroundColor: getStageColor(),
            }}
          />
        </div>
      </div>

      {/* Status Message */}
      <div className="status-message-container">
        <div className="status-icon-wrapper">
          {status.stage === 'confirming' || status.stage === 'broadcasting' ? (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              className="spinner"
            >
              ⟳
            </motion.div>
          ) : status.stage === 'confirmed' ? (
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', stiffness: 200, damping: 10 }}
              className="success-icon"
            >
              ✓
            </motion.div>
          ) : status.stage === 'failed' ? (
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className="error-icon"
            >
              ✗
            </motion.div>
          ) : null}
        </div>

        <div className="status-text">
          <p className="stage-message">{stageMessage}</p>

          {/* Likelihood Indicator */}
          {likelihoodResult && status.stage !== 'confirmed' && status.stage !== 'failed' && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="likelihood-badge"
              style={{
                borderColor: display?.color,
                color: display?.color,
              }}
            >
              <span className="likelihood-dot" style={{ backgroundColor: display?.color }} />
              <span>{display?.label}</span>
              <span className="confidence-score">({likelihoodResult.estimatedSuccessRate}%)</span>
            </motion.div>
          )}
        </div>
      </div>

      {/* Warning Messages */}
      <AnimatePresence>
        {showDetails && likelihoodResult && likelihoodResult.warnings.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="warnings-container"
          >
            {likelihoodResult.warnings.map((warning, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="warning-item"
              >
                <span className="warning-icon">⚠</span>
                <span className="warning-text">{warning}</span>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Transaction Hash (if available) */}
      {status.txHash && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="tx-hash-container"
        >
          <span className="tx-hash-label">Transaction:</span>
          <a
            href={`https://sepolia.etherscan.io/tx/${status.txHash}`}
            target="_blank"
            rel="noopener noreferrer"
            className="tx-hash-link"
          >
            {status.txHash.slice(0, 10)}...{status.txHash.slice(-8)}
          </a>
        </motion.div>
      )}

      {/* Risk Factors Details (collapsible) */}
      {showDetails && likelihoodResult && status.stage === 'validating' && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="risk-factors-container"
        >
          <details className="risk-factors-details">
            <summary>View risk factors</summary>
            <div className="risk-factors-grid">
              <RiskFactorItem
                label="Balance Margin"
                value={`${likelihoodResult.riskFactors.balanceMargin.toFixed(1)}%`}
                status={
                  likelihoodResult.riskFactors.balanceMargin > 5
                    ? 'good'
                    : likelihoodResult.riskFactors.balanceMargin > 1
                    ? 'warning'
                    : 'error'
                }
              />
              <RiskFactorItem
                label="Network Congestion"
                value={likelihoodResult.riskFactors.networkCongestion}
                status={
                  likelihoodResult.riskFactors.networkCongestion === 'low'
                    ? 'good'
                    : likelihoodResult.riskFactors.networkCongestion === 'medium'
                    ? 'warning'
                    : 'error'
                }
              />
              <RiskFactorItem
                label="Gas Available"
                value={likelihoodResult.riskFactors.hasEnoughForGas ? 'Yes' : 'No'}
                status={likelihoodResult.riskFactors.hasEnoughForGas ? 'good' : 'error'}
              />
              <RiskFactorItem
                label="Contract Status"
                value={likelihoodResult.riskFactors.contractReachable ? 'Reachable' : 'Unreachable'}
                status={likelihoodResult.riskFactors.contractReachable ? 'good' : 'error'}
              />
            </div>
          </details>
        </motion.div>
      )}

      <style jsx>{`
        .transaction-status-indicator {
          width: 100%;
          padding: 16px;
          background: rgba(0, 0, 0, 0.2);
          border-radius: 12px;
          border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .progress-container {
          margin-bottom: 16px;
        }

        .progress-bar-bg {
          width: 100%;
          height: 6px;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 3px;
          overflow: hidden;
        }

        .progress-bar-fill {
          height: 100%;
          border-radius: 3px;
          transition: background-color 0.3s ease;
        }

        .status-message-container {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 12px;
        }

        .status-icon-wrapper {
          font-size: 24px;
          min-width: 24px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .spinner {
          color: #3B82F6;
          font-size: 24px;
        }

        .success-icon {
          color: #10B981;
          font-size: 24px;
          font-weight: bold;
        }

        .error-icon {
          color: #EF4444;
          font-size: 24px;
          font-weight: bold;
        }

        .status-text {
          flex: 1;
        }

        .stage-message {
          font-size: 14px;
          font-weight: 500;
          color: #fff;
          margin: 0 0 6px 0;
        }

        .likelihood-badge {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 4px 10px;
          border: 1px solid;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 500;
          background: rgba(0, 0, 0, 0.3);
        }

        .likelihood-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          animation: pulse 2s ease-in-out infinite;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }

        .confidence-score {
          opacity: 0.8;
          font-size: 11px;
        }

        .warnings-container {
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid rgba(255, 255, 255, 0.1);
        }

        .warning-item {
          display: flex;
          align-items: flex-start;
          gap: 8px;
          padding: 6px 8px;
          background: rgba(245, 158, 11, 0.1);
          border-left: 2px solid #F59E0B;
          border-radius: 4px;
          margin-bottom: 6px;
          font-size: 12px;
        }

        .warning-icon {
          color: #F59E0B;
          font-size: 14px;
        }

        .warning-text {
          color: #FCD34D;
          flex: 1;
        }

        .tx-hash-container {
          margin-top: 12px;
          padding: 8px 12px;
          background: rgba(59, 130, 246, 0.1);
          border-radius: 6px;
          font-size: 12px;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .tx-hash-label {
          color: #93C5FD;
        }

        .tx-hash-link {
          color: #60A5FA;
          text-decoration: none;
          font-family: monospace;
        }

        .tx-hash-link:hover {
          text-decoration: underline;
        }

        .risk-factors-container {
          margin-top: 12px;
        }

        .risk-factors-details {
          background: rgba(0, 0, 0, 0.2);
          border-radius: 6px;
          padding: 8px;
        }

        .risk-factors-details summary {
          cursor: pointer;
          font-size: 12px;
          color: #9CA3AF;
          user-select: none;
          padding: 4px;
        }

        .risk-factors-details summary:hover {
          color: #D1D5DB;
        }

        .risk-factors-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 8px;
          margin-top: 8px;
        }
      `}</style>
    </div>
  );
};

interface RiskFactorItemProps {
  label: string;
  value: string;
  status: 'good' | 'warning' | 'error';
}

const RiskFactorItem: React.FC<RiskFactorItemProps> = ({ label, value, status }) => {
  const colors = {
    good: '#10B981',
    warning: '#F59E0B',
    error: '#EF4444',
  };

  return (
    <div className="risk-factor-item">
      <div className="risk-factor-label">{label}</div>
      <div className="risk-factor-value" style={{ color: colors[status] }}>
        {value}
      </div>
      <style jsx>{`
        .risk-factor-item {
          padding: 6px 8px;
          background: rgba(255, 255, 255, 0.05);
          border-radius: 4px;
        }

        .risk-factor-label {
          font-size: 10px;
          color: #9CA3AF;
          margin-bottom: 2px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .risk-factor-value {
          font-size: 13px;
          font-weight: 600;
        }
      `}</style>
    </div>
  );
};

export default TransactionStatusIndicator;
