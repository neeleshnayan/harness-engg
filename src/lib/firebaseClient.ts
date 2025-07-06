import { initializeApp, getApps, getApp } from "firebase/app";

const firebaseConfig = {
  apiKey: "AIzaSyAO04zToJ4_lSAENhjgOjCGfhHI-yzLNn4",
  authDomain: "krypton-test-38298.firebaseapp.com",
  projectId: "krypton-test-38298",
  storageBucket: "krypton-test-38298.appspot.com",
  messagingSenderId: "693002187983",
  appId: "1:693002187983:web:50ff2f852405cfcd81f3ba",
  measurementId: "G-QN1V0Q3X3R"
};


export function getFirebaseApp() {
  if (typeof window === "undefined") return undefined; // Only run in browser
  if (!getApps().length) {
    return initializeApp(firebaseConfig);
  }
  return getApp();
}