import React from "react";
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

const UsernameCard: React.FC<UsernameCardProps> = ({
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
        <div className="bg-zinc-900/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-zinc-800 mb-8">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xl font-bold text-white flex items-center">
              <FaUser className="mr-3 text-purple-400" />
              Krypton Username
            </h3>
          </div>
          <div className="text-center">
            <p className="text-zinc-400 mb-4">Set a unique username to receive payments by handle</p>
            <Button
              onClick={() => setShowUsernameForm(true)}
              className="bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white px-6 py-3 rounded-2xl font-semibold transition-all duration-300 shadow-lg hover:shadow-xl"
            >
              <FaUser className="mr-2" />
              Set Username
            </Button>
          </div>
        </div>
      )}
      {/* Username Form Modal */}
      {showUsernameForm && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-md bg-white/95 backdrop-blur-xl border border-white/20 shadow-2xl">
            <CardHeader>
              <CardTitle className="text-xl font-bold text-gray-900 flex items-center">
                <FaUser className="mr-3 text-purple-500" />
                Set Your Username
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {usernameError && (
                <Alert variant="destructive" className="bg-red-50 border-red-200 text-red-700">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{usernameError}</AlertDescription>
                </Alert>
              )}
              {usernameSuccess && (
                <Alert className="bg-green-50 border-green-200 text-green-700">
                  <FaCheck className="h-4 w-4" />
                  <AlertDescription>{usernameSuccess}</AlertDescription>
                </Alert>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Username
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500">@</span>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="yourusername"
                    className="w-full pl-8 pr-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all duration-200"
                    disabled={usernameLoading}
                  />
                </div>
                <p className="text-xs text-gray-500 mt-2">
                  Letters, numbers, and underscores only. 3-20 characters.
                </p>
              </div>
              <div className="flex space-x-3">
                <Button
                  onClick={handleSetUsername}
                  disabled={usernameLoading || !username.trim()}
                  className="flex-1 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white"
                >
                  {usernameLoading ? "Setting..." : "Set Username"}
                </Button>
                <Button
                  onClick={handleCancelUsername}
                  variant="outline"
                  className="flex-1"
                  disabled={usernameLoading}
                >
                  Cancel
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
};

export default UsernameCard; 