'use client';

import React, { useState } from "react";
import axios from "axios";
import { getAuth, signInWithPopup, GoogleAuthProvider } from "firebase/auth";
import { useRouter } from "next/navigation";
import { getFirebaseApp } from "@/lib/firebaseClient";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";

const googleLogo = (
  <svg width="20" height="20" viewBox="0 0 48 48" className="mr-3">
    <g>
      <path fill="#4285F4" d="M43.6 20.5h-1.9V20H24v8h11.3c-1.6 4.3-5.7 7-11.3 7-6.6 0-12-5.4-12-12s5.4-12 12-12c2.7 0 5.2.9 7.2 2.4l6-6C36.1 5.1 30.4 3 24 3 12.9 3 4 11.9 4 23s8.9 20 20 20c11 0 19.7-8 19.7-20 0-1.3-.1-2.2-.3-3.5z"/>
      <path fill="#34A853" d="M6.3 14.7l6.6 4.8C14.3 16.1 18.7 13 24 13c2.7 0 5.2.9 7.2 2.4l6-6C36.1 5.1 30.4 3 24 3 15.7 3 8.4 8.2 6.3 14.7z"/>
      <path fill="#FBBC05" d="M24 43c6.2 0 11.4-2 15.2-5.5l-7-5.7c-2 1.4-4.5 2.2-8.2 2.2-5.6 0-10.3-3.7-12-8.7l-6.8 5.2C8.3 39.8 15.7 43 24 43z"/>
      <path fill="#EA4335" d="M43.6 20.5h-1.9V20H24v8h11.3c-1.1 3-4.1 7-11.3 7-6.6 0-12-5.4-12-12s5.4-12 12-12c2.7 0 5.2.9 7.2 2.4l6-6C36.1 5.1 30.4 3 24 3 12.9 3 4 11.9 4 23s8.9 20 20 20c11 0 19.7-8 19.7-20 0-1.3-.1-2.2-.3-3.5z" opacity=".1"/>
    </g>
  </svg>
);

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const handleLogin = async () => {
    setLoading(true);
    setError(null);
    try {
      const app = getFirebaseApp();
      if (!app) throw new Error("Firebase not initialized");
      const auth = getAuth(app);
      const provider = new GoogleAuthProvider();
      const result = await signInWithPopup(auth, provider);
      const idToken = await result.user.getIdToken();
      const res = await axios.post("/api/v1/login", { idToken });
      localStorage.setItem('userData', JSON.stringify(res.data));
      router.push('/wallet');
    } catch (err: any) {
      setError(err?.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-black via-zinc-900 to-neutral-900">
      <Card className="w-full max-w-md rounded-3xl bg-black/60 border border-white/10 shadow-2xl backdrop-blur-xl">
        <CardHeader className="text-center">
          <div className="mb-6 flex justify-center">
            <img src="/krypton_logo.svg" alt="Krypton Logo" className="w-28 h-28 mx-auto mb-2 drop-shadow-[0_4px_24px_rgba(16,255,180,0.5)]" />
          </div>
          <CardTitle className="text-3xl font-extrabold text-white mb-2 tracking-tight">Welcome to Krypton</CardTitle>
          <p className="text-zinc-300 text-lg font-medium">Your secure digital wallet</p>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <Alert className="bg-red-900/80 border-red-700 text-white">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <Button 
            onClick={handleLogin} 
            disabled={loading}
            className="w-full py-6 text-lg font-bold rounded-2xl bg-gradient-to-r from-green-400 via-teal-400 to-cyan-400 hover:from-green-300 hover:to-cyan-500 text-black shadow-lg shadow-cyan-500/20 flex items-center justify-center gap-2 transition-all duration-200"
            size="lg"
          >
            {googleLogo}
            {loading ? "Signing in..." : "Continue with Google"}
          </Button>
          <p className="text-sm text-zinc-400 text-center mt-8">
            By continuing, you agree to our{' '}
            <a href="#" className="text-cyan-400 font-medium underline">Terms of Service</a>
            {' '}and{' '}
            <a href="#" className="text-cyan-400 font-medium underline">Privacy Policy</a>
          </p>
          <p className="text-xs text-zinc-500 text-center mt-6">
            Secure • Fast • Reliable
          </p>
        </CardContent>
      </Card>
    </div>
  );
} 