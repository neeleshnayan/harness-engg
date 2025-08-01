'use client';

import React, { useState } from "react";
import api from "@/lib/api";
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
  const [loading, setLoading] = useState<'business' | 'customer' | false>(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const handleLogin = (role: 'business' | 'customer') => {
    setLoading(role);
    setError(null);
    const app = getFirebaseApp();
    if (!app) {
      setError("Firebase not initialized");
      setLoading(false);
      return;
    }
    const auth = getAuth(app);
    const provider = new GoogleAuthProvider();

    signInWithPopup(auth, provider)
      .then(async (result) => {
        const idToken = await result.user.getIdToken();
        const res = await api.post("/api/v1/login", { idToken });
        localStorage.setItem('userData', JSON.stringify(res.data));
        if (role === 'business') {
          router.push('/business');
        } else {
          router.push('/customer');
        }
      })
      .catch((err) => {
        setError(err?.message || "Login failed");
      })
      .finally(() => {
        setLoading(false);
      });
  };

  return (
    <div className="min-h-screen w-full flex flex-col bg-gradient-to-br from-black via-zinc-900 to-neutral-900 overflow-x-hidden">
      <div className="flex-1 flex flex-col items-center justify-center w-full font-sans">
        <div className="mb-20 mt-8 text-center">
          <span className="block text-4xl sm:text-5xl font-extrabold text-center mb-2 text-white">
            DeFi for the
          </span>
          <span className="block text-5xl sm:text-6xl md:text-7xl font-black text-center">
            <span className="text-zinc-400 font-semibold">next </span>
            <span className="text-white">Billion</span>
          </span>
        </div>
        <div className="relative flex items-center justify-center mb-10">
          <div className="absolute w-80 h-80 rounded-full bg-cyan-400/10 blur-3xl z-0" style={{ top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}></div>
          <img src="/krypton_logo.svg" alt="Krypton Logo" className="w-64 h-64 mx-auto relative z-10 drop-shadow-[0_0_64px_rgba(16,255,180,0.25)]" />
        </div>
        
        {/* Login Section */}
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold text-white mb-2">Login with Google</h2>
          <p className="text-zinc-400 text-lg">Choose your account type to continue</p>
        </div>
        
        {error && (
          <Alert className="bg-red-900/80 border-red-700 text-white mb-6 max-w-md">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        
        <div className="flex flex-col gap-4 w-4/5 max-w-md mx-auto">
          <button
            type="button"
            onClick={() => handleLogin('business')}
            disabled={loading === 'business'}
            className="flex items-center justify-center py-4 px-8 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white text-lg font-semibold shadow-lg hover:scale-[1.02] transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-purple-400 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading === 'business' ? "Signing in..." : "As Business"}
          </button>
          
          <button
            type="button"
            onClick={() => handleLogin('customer')}
            disabled={loading === 'customer'}
            className="flex items-center justify-center py-4 px-8 rounded-xl bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 text-white text-lg font-semibold shadow-lg hover:scale-[1.02] transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-green-400 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {loading === 'customer' ? "Signing in..." : "As Customer"}
          </button>
        </div>
      </div>
      
      <footer className="w-full py-2 flex flex-col justify-center items-center border-t border-zinc-800 mt-auto">
        <span className="text-zinc-500 text-sm">Yield like God • Pay Like Ghost</span>
        <span className="text-zinc-600 text-xs mt-1">© {new Date().getFullYear()} Krypton Fund LLC</span>
      </footer>
    </div>
  );
} 