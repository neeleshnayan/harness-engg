import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";
import { FaArrowUp } from "react-icons/fa";

interface SendUSDCModalProps {
  visible: boolean;
  onClose: () => void;
  receiverUsername: string;
  setReceiverUsername: (username: string) => void;
  sendAmount: string;
  setSendAmount: (amount: string) => void;
  sendLoading: boolean;
  sendError: string | null;
  sendSuccess: string | null;
  onSend: () => void;
}

const SendUSDCModal: React.FC<SendUSDCModalProps> = ({
  visible,
  onClose,
  receiverUsername,
  setReceiverUsername,
  sendAmount,
  setSendAmount,
  sendLoading,
  sendError,
  sendSuccess,
  onSend,
}) => {
  if (!visible) return null;
  return (
    <div
      className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={sendSuccess ? onClose : undefined}
      style={{ cursor: sendSuccess ? 'pointer' : 'default' }}
    >
      <Card
        className="w-full max-w-md bg-zinc-900/95 backdrop-blur-xl border border-zinc-800 shadow-2xl relative overflow-hidden"
        onClick={e => e.stopPropagation()} // Prevent modal click from closing overlay
      >
        <CardHeader>
          <CardTitle className="text-xl font-bold text-white flex items-center">
            <FaArrowUp className="mr-3 text-blue-400" />
            Send USDC
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Success Animation */}
          {sendSuccess && (
            <div className="flex flex-col items-center justify-center py-8">
              <div className="mb-4">
                <svg className="animate-checkmark" width="72" height="72" viewBox="0 0 72 72">
                  <circle cx="36" cy="36" r="34" fill="#1a2e22" stroke="#22c55e" strokeWidth="3" />
                  <path
                    d="M22 38l10 10 18-18"
                    fill="none"
                    stroke="#22c55e"
                    strokeWidth="4"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="checkmark-path"
                  />
                </svg>
              </div>
              <div className="text-green-400 text-lg font-semibold mb-2">Transaction Successful!</div>
              <div className="text-zinc-300 text-sm text-center">{sendSuccess}</div>
              <div className="mt-6 text-zinc-500 text-xs">Tap anywhere to close</div>
            </div>
          )}
          {/* Form (hide if success) */}
          {!sendSuccess && (
            <>
              {sendError && (
                <Alert variant="destructive" className="bg-red-900/80 border-red-700 text-red-200">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{sendError}</AlertDescription>
                </Alert>
              )}
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-zinc-200 mb-2">
                    Receiver Username
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-zinc-500">@</span>
                    <input
                      type="text"
                      value={receiverUsername}
                      onChange={(e) => setReceiverUsername(e.target.value)}
                      placeholder="username"
                      className="w-full pl-8 pr-4 py-3 border border-zinc-800 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 bg-zinc-800 text-white"
                      disabled={sendLoading}
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-200 mb-2">
                    Amount (USDC)
                  </label>
                  <input
                    type="number"
                    value={sendAmount}
                    onChange={(e) => setSendAmount(e.target.value)}
                    placeholder="0.00"
                    step="0.01"
                    min="0"
                    className="w-full px-4 py-3 border border-zinc-800 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 bg-zinc-800 text-white"
                    disabled={sendLoading}
                  />
                </div>
              </div>
              <div className="flex space-x-3 pt-4">
                <Button
                  onClick={onSend}
                  disabled={sendLoading || !receiverUsername.trim() || !sendAmount.trim()}
                  className="flex-1 bg-gradient-to-r from-blue-500 via-purple-500 to-blue-600 hover:from-blue-600 hover:to-purple-700 text-white py-3 rounded-lg text-lg font-semibold shadow-md"
                >
                  {sendLoading ? "Sending..." : "Send USDC"}
                </Button>
                <Button
                  onClick={onClose}
                  variant="outline"
                  className="flex-1 py-3 rounded-lg text-lg font-semibold"
                  disabled={sendLoading}
                >
                  Cancel
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default SendUSDCModal; 