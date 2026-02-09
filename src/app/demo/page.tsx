'use client';

import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { getAuth, signInWithCustomToken } from "firebase/auth";
import { useRouter } from "next/navigation";
import { getFirebaseApp } from "@/lib/firebaseClient";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, Loader2 } from "lucide-react";

const DEMO_EMAIL = "testkryptonx@gmail.com";

export default function DemoPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    const performDemoLogin = async () => {
      try {
        setLoading(true);
        setError(null);

        const app = getFirebaseApp();
        if (!app) {
          throw new Error("Firebase not initialized");
        }

        const auth = getAuth(app);

        // Get a custom token from backend for demo login
        const customTokenResponse = await api.post("/api/v1/demo/login", {
          email: DEMO_EMAIL,
        });
        
        if (!customTokenResponse.data?.customToken) {
          throw new Error("No custom token received from demo endpoint");
        }

        // Sign in with custom token
        const userCredential = await signInWithCustomToken(auth, customTokenResponse.data.customToken);
        const idToken = await userCredential.user.getIdToken();

        // Call the login API with the ID token to get user data and create wallet if needed
        const res = await api.post("/api/v1/login", { idToken });
        
        // Store user data
        localStorage.setItem('userData', JSON.stringify(res.data));
        
        // Redirect to customer page
        router.push('/customer');
      } catch (err: any) {
        console.error("Demo login error:", err);
        const errorMessage = err?.response?.data?.detail || err?.message || "Demo login failed. Please contact support.";
        setError(errorMessage);
        setLoading(false);
      }
    };

    performDemoLogin();
  }, [router]);

  return (
    <div className="relative min-h-screen w-full flex flex-col items-center justify-center font-sans overflow-x-hidden">
      {/* Background Images */}
      <div className="fixed inset-0 z-0">
        <img
          src="/Desktop login.svg"
          alt="Background"
          className="hidden md:block w-full h-full object-cover"
        />
        <img
          src="/Mobile login.svg"
          alt="Background"
          className="block md:hidden w-full h-full object-cover"
        />
      </div>

      {/* Main Content Area */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center w-full p-6 md:p-12">
        {/* Glass Box */}
        <div className="relative w-full max-w-[440px] flex flex-col items-center pt-6 pb-8 md:pt-8 md:pb-10 px-10 md:px-14">
          {/* Glass BG SVG */}
          <img
            src="/Glass BG.svg"
            alt="Glass Background"
            className="absolute inset-0 w-full h-full z-0 object-fill pointer-events-none"
          />

          {/* Content inside Glass Box */}
          <div className="relative z-10 flex flex-col items-center w-full">
            <img src="/Krypton logo.svg" alt="Krypton Logo" className="w-10 h-10 mb-4" />

            <h1 className="text-3xl md:text-[42px] font-bold text-white mb-1 text-center leading-tight">
              Demo Login
            </h1>

            <p className="text-zinc-200 text-sm md:text-base mb-5 text-center px-4">
              Logging in as {DEMO_EMAIL}...
            </p>

            {loading && (
              <div className="flex flex-col items-center gap-4 w-full">
                <Loader2 className="h-8 w-8 text-white animate-spin" />
                <p className="text-zinc-300 text-sm">Please wait...</p>
              </div>
            )}

            {error && (
              <Alert className="bg-red-900/50 border-red-700/50 text-white mb-4 w-full backdrop-blur-md">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
