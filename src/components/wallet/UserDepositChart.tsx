import React, { useMemo } from "react";
import { BarChart, Bar, ResponsiveContainer, XAxis, YAxis, Tooltip, Cell, ReferenceLine } from "recharts";
import { TrendingUp, TrendingDown, Activity } from "lucide-react";

interface Deposit {
  id: string;
  owner: string;
  assets: string;
  shares: string;
  timestamp: string;
}

interface Withdrawal {
  id: string;
  owner: string;
  receiver: string;
  assets: string;
  shares: string;
  timestamp: string;
}

interface UserDepositChartProps {
  deposits: Deposit[];
  withdrawals: Withdrawal[];
  userWalletAddress?: string;
  tokenSymbol: string;
}

type TransactionPoint = {
  timestamp: number;
  amount: number;
  type: 'deposit' | 'withdrawal';
  date: string;
  formattedAmount: string;
};

const formatDate = (timestamp: number): string => {
  const date = new Date(timestamp * 1000);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

const formatAmount = (amount: number): string => {
  if (amount >= 1000000) return `$${(amount / 1000000).toFixed(2)}M`;
  if (amount >= 1000) return `$${(amount / 1000).toFixed(2)}K`;
  return `$${amount.toFixed(2)}`;
};

const buildTransactionTimeline = (
  deposits: Deposit[],
  withdrawals: Withdrawal[],
  userWalletAddress?: string
): TransactionPoint[] => {
  if (!userWalletAddress) return [];

  const normalizedAddress = userWalletAddress.toLowerCase();
  const transactions: TransactionPoint[] = [];

  deposits
    .filter((d) => d.owner.toLowerCase() === normalizedAddress)
    .forEach((deposit) => {
      const timestamp = Number(deposit.timestamp);
      const amount = Number(deposit.assets) / 1e6;
      
      if (Number.isFinite(timestamp) && Number.isFinite(amount) && amount > 0) {
        transactions.push({
          timestamp,
          amount,
          type: 'deposit',
          date: formatDate(timestamp),
          formattedAmount: formatAmount(amount)
        });
      }
    });

  withdrawals
    .filter((w) => w.owner.toLowerCase() === normalizedAddress)
    .forEach((withdrawal) => {
      const timestamp = Number(withdrawal.timestamp);
      const amount = Number(withdrawal.assets) / 1e6;
      
      if (Number.isFinite(timestamp) && Number.isFinite(amount) && amount > 0) {
        transactions.push({
          timestamp,
          amount: -amount,
          type: 'withdrawal',
          date: formatDate(timestamp),
          formattedAmount: formatAmount(amount)
        });
      }
    });

  return transactions.sort((a, b) => a.timestamp - b.timestamp);
};

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0].payload as TransactionPoint;
  const isDeposit = data.type === 'deposit';

  return (
    <div className="bg-zinc-800/95 backdrop-blur-xl border border-zinc-700 rounded-lg p-3 shadow-xl">
      <p className="text-xs text-zinc-400 mb-1">{data.date}</p>
      <p className={`text-sm font-bold ${isDeposit ? 'text-green-400' : 'text-red-400'}`}>
        {isDeposit ? '+' : ''}{data.formattedAmount}
      </p>
      <p className="text-xs text-zinc-500 mt-1">
        {isDeposit ? 'Deposit' : 'Withdrawal'}
      </p>
    </div>
  );
};

export const UserDepositChart: React.FC<UserDepositChartProps> = ({
  deposits,
  withdrawals,
  userWalletAddress,
  tokenSymbol
}) => {
  const transactionTimeline = useMemo(
    () => buildTransactionTimeline(deposits, withdrawals, userWalletAddress),
    [deposits, withdrawals, userWalletAddress]
  );

  const stats = useMemo(() => {
    if (transactionTimeline.length === 0) return null;

    const totalDeposits = transactionTimeline
      .filter(t => t.type === 'deposit')
      .reduce((sum, t) => sum + t.amount, 0);
    
    const totalWithdrawals = transactionTimeline
      .filter(t => t.type === 'withdrawal')
      .reduce((sum, t) => sum + Math.abs(t.amount), 0);
    
    const netAmount = totalDeposits - totalWithdrawals;
    const depositsCount = transactionTimeline.filter(t => t.type === 'deposit').length;
    const withdrawalsCount = transactionTimeline.filter(t => t.type === 'withdrawal').length;

    return {
      totalDeposits,
      totalWithdrawals,
      netAmount,
      depositsCount,
      withdrawalsCount
    };
  }, [transactionTimeline]);

  if (transactionTimeline.length === 0) {
    return (
      <div className="mt-3 pt-3 border-t border-zinc-600/30">
        <div className="flex items-center justify-center py-6 text-zinc-500">
          <Activity className="w-4 h-4 mr-2" />
          <span className="text-xs">No transaction history</span>
        </div>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="mt-3 pt-3 border-t border-zinc-600/30">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-400">Transaction History</span>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1">
            <TrendingUp className="w-3 h-3 text-green-400" />
            <span className="text-green-400">{stats.depositsCount}</span>
          </div>
          {stats.withdrawalsCount > 0 && (
            <div className="flex items-center gap-1">
              <TrendingDown className="w-3 h-3 text-red-400" />
              <span className="text-red-400">{stats.withdrawalsCount}</span>
            </div>
          )}
        </div>
      </div>

      <div className="h-32">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart 
            data={transactionTimeline} 
            margin={{ top: 5, right: 5, left: 5, bottom: 20 }}
          >
            <XAxis 
              dataKey="date"
              tick={{ fill: '#71717a', fontSize: 10 }}
              stroke="#3f3f46"
              angle={-45}
              textAnchor="end"
              height={50}
            />
            <YAxis 
              tick={{ fill: '#71717a', fontSize: 10 }}
              stroke="#3f3f46"
              tickFormatter={(value) => formatAmount(Math.abs(value))}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={0} stroke="#52525b" strokeWidth={1} />
            <Bar dataKey="amount" radius={[4, 4, 0, 0]}>
              {transactionTimeline.map((entry, index) => (
                <Cell 
                  key={`cell-${index}`} 
                  fill={entry.type === 'deposit' ? '#3b82f6' : '#ef4444'}
                  opacity={0.8}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="flex justify-between mt-2 text-xs">
        <div className="text-zinc-400">
          <span className="text-green-400">↑</span> {formatAmount(stats.totalDeposits)}
        </div>
        {stats.totalWithdrawals > 0 && (
          <div className="text-zinc-400">
            <span className="text-red-400">↓</span> {formatAmount(stats.totalWithdrawals)}
          </div>
        )}
        <div className="text-zinc-300 font-semibold">
          Net: {formatAmount(stats.netAmount)}
        </div>
      </div>
    </div>
  );
};

