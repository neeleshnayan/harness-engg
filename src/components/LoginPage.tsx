'use client';

import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import {
  browserLocalPersistence,
  getAuth,
  getRedirectResult,
  GoogleAuthProvider,
  setPersistence,
  signInWithPopup,
  signInWithRedirect,
  UserCredential,
} from "firebase/auth";
import { useRouter } from "next/navigation";
import { getFirebaseApp } from "@/lib/firebaseClient";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";

const LOGIN_ROLE_STORAGE_KEY = "krypton_login_role";
const POPUP_FALLBACK_ERROR_CODES = new Set([
  "auth/popup-blocked",
  "auth/cancelled-popup-request",
  "auth/operation-not-supported-in-this-environment",
]);

export default function LoginPage() {
  const [loading, setLoading] = useState<'business' | 'customer' | false>(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const finishLogin = async (credential: UserCredential, role: 'business' | 'customer') => {
    const idToken = await credential.user.getIdToken();
    const res = await api.post("/api/v1/login", { idToken });
    localStorage.setItem('userData', JSON.stringify(res.data));
    sessionStorage.removeItem(LOGIN_ROLE_STORAGE_KEY);
    router.push(role === 'business' ? '/business' : '/customer');
  };

  useEffect(() => {
    const app = getFirebaseApp();
    if (!app) return;

    const auth = getAuth(app);
    let cancelled = false;

    const recoverRedirectLogin = async () => {
      const pendingRole = (sessionStorage.getItem(LOGIN_ROLE_STORAGE_KEY) as 'business' | 'customer' | null) || 'customer';
      try {
        const result = await getRedirectResult(auth);
        if (!result || cancelled) return;
        setLoading(pendingRole);
        await finishLogin(result, pendingRole);
      } catch (err: any) {
        if (cancelled) return;
        sessionStorage.removeItem(LOGIN_ROLE_STORAGE_KEY);
        if (err?.code?.startsWith?.('auth/')) {
          setError(err.message || 'Google sign-in failed after redirect.');
        } else {
          const status = err?.response?.status;
          const detail = err?.response?.data?.detail ?? err?.response?.data?.message;
          const msg = typeof detail === 'string' ? detail : err?.message || 'Login failed';
          setError(status ? `Login error (${status}): ${msg}` : msg);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    recoverRedirectLogin();
    return () => {
      cancelled = true;
    };
  }, [router]);

  const handleLogin = async (role: 'business' | 'customer') => {
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
    provider.setCustomParameters({ prompt: "select_account" });
    sessionStorage.setItem(LOGIN_ROLE_STORAGE_KEY, role);

    try {
      await setPersistence(auth, browserLocalPersistence);

      const result = await signInWithPopup(auth, provider);
      await finishLogin(result, role);
    } catch (err: any) {
      if (POPUP_FALLBACK_ERROR_CODES.has(err?.code)) {
        try {
          await signInWithRedirect(auth, provider);
          return;
        } catch (redirectErr: any) {
          const redirectMessage = redirectErr?.message || 'Google sign-in redirect failed.';
          setError(redirectMessage);
          sessionStorage.removeItem(LOGIN_ROLE_STORAGE_KEY);
          setLoading(false);
          return;
        }
      }

      if (err?.code?.startsWith?.('auth/')) {
        if (err.code === "auth/popup-closed-by-user") {
          setError("Google sign-in popup was closed before completion.");
        } else {
          setError(err.message || 'Google sign-in failed. Try again or check that this app is allowed in Firebase.');
        }
        sessionStorage.removeItem(LOGIN_ROLE_STORAGE_KEY);
        setLoading(false);
        return;
      }

      const status = err?.response?.status;
      const detail = err?.response?.data?.detail ?? err?.response?.data?.message;
      const msg = typeof detail === 'string' ? detail : err?.message || 'Login failed';
      setError(status ? `Login error (${status}): ${msg}` : msg);
      sessionStorage.removeItem(LOGIN_ROLE_STORAGE_KEY);
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen w-full flex flex-col items-center font-sans overflow-x-hidden">
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
        <div className="relative w-full max-w-[440px] flex flex-col items-center pt-6 pb-8 md:pt-8 md:pb-10 px-10 md:px-14 mt-20 md:mb-20">
          {/* Glass BG SVG */}
          <img
            src="/Glass BG.svg"
            alt="Glass Background"
            className="absolute inset-0 w-full h-full z-0 object-fill pointer-events-none"
          />

          {/* Content inside Glass Box */}
          <div className="relative z-10 flex flex-col items-center w-full">
            <img src="/Krypton logo.svg" alt="Krypton Logo" className="w-10 h-10 mb-4" />

            <h1 className="text-3xl md:text-[42px] font-bold text-white mb-1 text-center leading-tight whitespace-nowrap">
              Sign in to Krypton
            </h1>

            <p className="text-zinc-200 text-sm md:text-base mb-5 text-center px-4">
              continue via Google
            </p>

            {error && (
              <Alert className="bg-red-900/50 border-red-700/50 text-white mb-4 w-full backdrop-blur-md">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="flex flex-col gap-3 w-full">
              {/* Business Button */}
              <button
                type="button"
                onClick={() => handleLogin('business')}
                disabled={loading !== false}
                className="relative w-full aspect-[340/80] group transition-transform active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <img
                  src="/As Business CTA.svg"
                  alt="As Business"
                  className="w-full h-full object-contain"
                />
                {loading === 'business' && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/20 rounded-2xl">
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  </div>
                )}
              </button>

              {/* Customer Button */}
              <button
                type="button"
                onClick={() => handleLogin('customer')}
                disabled={loading !== false}
                className="relative w-full aspect-[340/80] group transition-transform active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <img
                  src="/As Customer CTA.svg"
                  alt="As Customer"
                  className="w-full h-full object-contain"
                />
                {loading === 'customer' && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/20 rounded-2xl">
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                  </div>
                )}
              </button>
            </div>
          </div>
        </div>
      </main>

      {/* Footer - Moved to bottom of page */}
      <footer className="relative z-10 w-full py-8 flex flex-col items-center gap-3 mt-auto">
        <p className="text-zinc-400 text-sm">© 2026 Krypton Fund LLC</p>
        <div className="flex gap-6 md:gap-10 text-zinc-500 text-sm">
          <a href="#" className="hover:text-white transition-colors">Privacy Policy</a>
          <a href="#" className="hover:text-white transition-colors">Terms of Service</a>
          <a href="https://www.kryptonfund.com/" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">Website</a>
        </div>
      </footer>
    </div>
  );
}
