import "./globals.css";
import type { Metadata } from "next";
import { Instrument_Sans } from "next/font/google";
import { QueryProvider } from "@/providers/QueryProvider";
import { RatesProvider } from "@/providers/RatesProvider";

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
        <link rel="icon" href="/Krypton logo.svg" type="image/svg+xml" />
      </head>
      <body className={`${instrumentSans.variable} ${instrumentSans.className}`}>
        <QueryProvider>
          <RatesProvider>
            {children}
          </RatesProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
