import React, { memo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";
import { FaUser, FaCheck } from "react-icons/fa";

interface UsernameCardProps {
  accountData: any;
  showUsernameForm: boolean;
  username: string;
  usernameLoading: boolean;
  usernameError: string | null;
  usernameSuccess: string | null;
  setShowUsernameForm: (show: boolean) => void;
  setUsername: (username: string) => void;
  handleSetUsername: () => void;
  handleCancelUsername: () => void;
}

const UsernameCard: React.FC<UsernameCardProps> = memo(({
  accountData,
  showUsernameForm,
  username,
  usernameLoading,
  usernameError,
  usernameSuccess,
  setShowUsernameForm,
  setUsername,
  handleSetUsername,
  handleCancelUsername,
}) => {
  return (
    <>
      {/* Username display or set username card */}
      {!accountData?.username && (
        <div className="bg-[hsl(var(--brand-bg))]/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-white/10 mb-8">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-bold text-white flex items-center">
              <FaUser className="mr-3 text-teal-400" />
              Krypton Username
            </h3>
          </div>
          <div className="text-center">
            <p className="text-zinc-400 mb-4">Set a unique username to receive payments by handle</p>
            <Button
              onClick={() => setShowUsernameForm(true)}
              className="bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-700 hover:to-cyan-700 text-white px-6 py-3 rounded-2xl font-semibold transition-all duration-300 shadow-lg hover:shadow-xl"
            >
              <FaUser className="mr-2" />
              Set Username
            </Button>
          </div>
        </div>
      )}
      {/* Username Form Modal */}
      {showUsernameForm && (
        <div
          className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={usernameSuccess ? handleCancelUsername : undefined}
          style={{ cursor: usernameSuccess ? 'pointer' : 'default' }}
        >
          <Card
            className="w-full max-w-md bg-[hsl(var(--brand-bg))]/95 backdrop-blur-xl border border-white/10 shadow-2xl relative overflow-hidden"
            onClick={e => e.stopPropagation()} // Prevent modal click from closing overlay
          >
            <CardHeader>
              <CardTitle className="text-xl font-bold text-white flex items-center">
                <FaUser className="mr-3 text-teal-400" />
                Set Your Username
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Success State */}
              {usernameSuccess && (
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
                  <div className="text-green-400 text-lg font-semibold mb-2">Username Set!</div>
                  <div className="text-zinc-300 text-sm text-center">{usernameSuccess}</div>
                  <div className="mt-6 text-zinc-500 text-xs">Tap anywhere to close</div>
                </div>
              )}
              {/* Form (hide if success) */}
              {!usernameSuccess && (
                <>
                  {usernameError && (
                    <Alert variant="destructive" className="bg-red-900/80 border-red-700 text-red-200">
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription>{usernameError}</AlertDescription>
                    </Alert>
                  )}
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-zinc-200 mb-2">
                        Username
                      </label>
                      <div className="relative">
                        <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-zinc-500">@</span>
                        <input
                          type="text"
                          value={username}
                          onChange={(e) => setUsername(e.target.value)}
                          placeholder="yourusername"
                          className="w-full pl-8 pr-4 py-3 border border-white/10 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all duration-200 bg-white/5 text-white"
                          disabled={usernameLoading}
                        />
                      </div>
                      <p className="text-xs text-zinc-500 mt-2">
                        Letters, numbers, and underscores only. 3-20 characters.
                      </p>
                    </div>
                  </div>
                  <div className="flex space-x-3 pt-4">
                    <Button
                      onClick={handleSetUsername}
                      disabled={usernameLoading || !username.trim()}
                      className="flex-1 bg-gradient-to-r from-teal-500 to-cyan-600 hover:from-teal-600 hover:to-cyan-700 text-white py-3 rounded-lg text-lg font-semibold shadow-md"
                    >
                      {usernameLoading ? "Setting..." : "Set Username"}
                    </Button>
                    <Button
                      onClick={handleCancelUsername}
                      variant="outline"
                      className="flex-1 py-3 rounded-lg text-lg font-semibold"
                      disabled={usernameLoading}
                    >
                      Cancel
                    </Button>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
});

UsernameCard.displayName = 'UsernameCard';

export default UsernameCard; 