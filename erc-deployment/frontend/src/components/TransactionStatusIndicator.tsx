import type { TransactionStatus } from '@/hooks/useTransactionStatus';

type TransactionStatusIndicatorProps = {
  status: TransactionStatus;
  hash?: `0x${string}`;
  message?: string;
  showHash?: boolean;
};

export const TransactionStatusIndicator = ({
  status,
  hash,
  message,
  showHash = true,
}: TransactionStatusIndicatorProps) => {
  if (status === 'idle') return null;

  const getStatusIcon = () => {
    switch (status) {
      case 'pending':
        return (
          <svg className="h-5 w-5 animate-spin text-blue-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        );
      case 'success':
        return (
          <svg className="h-5 w-5 text-green-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        );
      case 'failed':
        return (
          <svg className="h-5 w-5 text-red-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        );
      default:
        return null;
    }
  };

  const getStatusColor = () => {
    switch (status) {
      case 'pending':
        return 'border-blue-500/30 bg-blue-500/10';
      case 'success':
        return 'border-green-500/30 bg-green-500/10';
      case 'failed':
        return 'border-red-500/30 bg-red-500/10';
      default:
        return 'border-white/10 bg-white/5';
    }
  };

  const getStatusMessage = () => {
    if (message) return message;

    switch (status) {
      case 'pending':
        return 'Waiting for blockchain confirmation...';
      case 'success':
        return 'Transaction confirmed!';
      case 'failed':
        return 'Transaction failed';
      default:
        return '';
    }
  };

  const getExplorerUrl = (txHash: `0x${string}`) => {
    // Sepolia Etherscan
    return `https://sepolia.etherscan.io/tx/${txHash}`;
  };

  return (
    <div className={`rounded-xl border p-4 ${getStatusColor()} transition-all duration-300`}>
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0">{getStatusIcon()}</div>
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-medium ${
            status === 'pending' ? 'text-blue-200' :
            status === 'success' ? 'text-green-200' :
            'text-red-200'
          }`}>
            {getStatusMessage()}
          </p>
          {hash && showHash && (
            <a
              href={getExplorerUrl(hash)}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 text-xs text-white/50 hover:text-white/70 underline break-all"
            >
              {hash.slice(0, 10)}...{hash.slice(-8)}
            </a>
          )}
          {status === 'pending' && (
            <p className="mt-1 text-xs text-white/40">
              This usually takes ~15-30 seconds
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
