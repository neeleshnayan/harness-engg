import "./globals.css";
import type { Metadata } from "next";
import { Instrument_Sans } from "next/font/google";
import { QueryProvider } from "@/providers/QueryProvider";

const instrumentSans = Instrument_Sans({
  variable: "--font-instrument-sans",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Krypton",
  description: "DeFi for the next Billion",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" href="/favicon.ico" sizes="32x32" type="image/x-icon" />
      </head>
      <body className={`${instrumentSans.variable} ${instrumentSans.className}`}>
        <QueryProvider>
          {children}
        </QueryProvider>
      </body>
    </html>
  );
}
