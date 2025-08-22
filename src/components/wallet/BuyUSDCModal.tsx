import axios from "axios";
import React, { useState, useEffect } from "react";
import ReactCountryFlag from "react-country-flag";
import { fetchOnrampQuote } from '@coinbase/onchainkit/fund';
import { set } from "zod";

interface FiatCurrency {
  code: string;
  symbol: string;
}

interface BuyUSDCModalProps {
  fiatData: FiatCurrency[];
  onClose: () => void;
  walletAddress?: string;
}

const BuyUSDCModal: React.FC<BuyUSDCModalProps> = ({ fiatData, onClose, walletAddress }) => {
  const [selectedCurrency, setSelectedCurrency] = useState<string>(
    fiatData[0]?.code || "EUR"
  );
  const [amount, setAmount] = useState<string>("");
  const [usdcAmount, setUsdcAmount] = useState<string>("0");
  const [loading, setLoading] = useState<boolean>(false);
  const [bestExchange, setBestExchange] = useState<string>("Coinbase");
  const [coinbaseBuyUrl, setCoinbaseBuyUrl] = useState<string>("");
  const [isCreatingQuote, setIsCreatingQuote] = useState<boolean>(false);

  // Dummy API function
  const fetchUSDC = (fiat: string, amt: number): Promise<string> => {
    return new Promise((resolve) => {
      setTimeout(() => {
        const rate = 0.862644; // Fixed rate from screenshot
        const result = (amt / rate).toFixed(2);
        resolve(result);
      }, 500);
    });
  };

  useEffect(() => {
    if (!amount || isNaN(Number(amount))) {
      setUsdcAmount("0");
      return;
    }

    let isMounted = true;

    const fetchData = async () => {
      setLoading(true);
      try {
        const transakResponse = await axios.get(
          `https://api-stg.transak.com/api/v1/pricing/public/quotes?partnerApiKey=f4c10825-55fd-4ccc-bd3f-40fc021468e5&fiatCurrency=${selectedCurrency}&cryptoCurrency=USDC&fiatAmount=${amount}&isBuyOrSell=BUY&network=ethereum&paymentMethod=credit_debit_card`
        );
        
        const coinbaseQuoteResponse = await fetch('https://api.developer.coinbase.com/onramp/v1/buy/quote', {
          method: 'POST',
          body: JSON.stringify({
            purchase_currency: 'USDC',
            purchase_network: 'ethereum',
            payment_currency: selectedCurrency,
            payment_method: 'CARD',
            payment_amount: amount,
            country: 'GB',
            destinationAddress: walletAddress || ''
          }),
          headers: {
            Authorization: `Bearer XPGt5SREGfGGfgXf6SWACggGkjh3HwQE`,
          },
        });
        const coinbaseQuote = await coinbaseQuoteResponse.json();
        setCoinbaseBuyUrl(coinbaseQuote?.onramp_url || "");
        const transakAmount = transakResponse.data?.response?.cryptoAmount || 0;
        const coinbaseAmount = coinbaseQuote?.purchase_amount?.value || "0";
        const val = Math.max(parseFloat(transakAmount), parseFloat(coinbaseAmount)).toFixed(2);

        if (isMounted) {
          setUsdcAmount(val);
          if (parseFloat(transakAmount) > parseFloat(coinbaseAmount)) {
            setBestExchange("Transak");
          } else {
            setBestExchange("Coinbase");
            // Store the Coinbase quote response for later use
            setCoinbaseBuyUrl(coinbaseQuote.onramp_url || "");
          }
        }
      } catch (error) {
        console.error("Error fetching USDC:", error);
        if (isMounted) {
          setUsdcAmount("0");
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchData();

    return () => {
      isMounted = false;
    };
  }, [amount, selectedCurrency]);

  const handleBuyNow = async () => {
    if (bestExchange === "Coinbase" && coinbaseBuyUrl) {
      // Open Coinbase widget in a new window/tab
      window.open(coinbaseBuyUrl, '_blank', 'width=500,height=700');
    } else {
      // Fallback for Transak or when Coinbase URL is not available
      console.log("Opening Transak or fallback payment method");
      // You can implement Transak widget integration here if needed
    }
  };

  const handleViaExchange = async () => {
    if (bestExchange === "Coinbase") {
      setIsCreatingQuote(true);
      try {
        // Create a fresh buy quote for the specific exchange
        const quoteResponse = await fetchOnrampQuote({
          purchaseCurrency: 'USDC',
          purchaseNetwork: 'ethereum',
          paymentCurrency: selectedCurrency,
          paymentMethod: 'CARD',
          paymentAmount: amount,
          country: 'US',
          subdivision: 'CA',
          apiKey: 'XPGt5SREGfGGfgXf6SWACggGkjh3HwQE'
        });

        if ((quoteResponse as any)?.onrampUrl) {
          window.open((quoteResponse as any).onrampUrl, '_blank', 'width=500,height=700');
        }
      } catch (error) {
        console.error("Error creating Coinbase quote:", error);
      } finally {
        setIsCreatingQuote(false);
      }
    } else {
      // Handle Transak integration
      console.log("Opening Transak payment flow");
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-md flex items-center p-2 pt-4 pb-4 mt-4 mb-10 justify-center z-50">
      <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl w-full max-w-md p-2 shadow-2xl">
        {/* Header */}
        <h2 className="flex items-center justify-center text-2xl font-bold text-white mb-6 text-center">
          <img
            src='/transak-logo.svg'
            alt="Transak"
            className="h-6 rounded-full"
          />
          &nbsp;&nbsp;Buy USDC&nbsp;
          <img
            src='/coinbase-logo.svg'
            alt="Coinbase"
            className="h-10 rounded-full"
          />
        </h2>

        {/* Amount Input */}
        <div className="flex items-center bg-zinc-800/50 border border-zinc-700 rounded-xl overflow-hidden mb-5">
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="flex-1 bg-transparent p-3 text-white placeholder-zinc-500 outline-none"
            placeholder="Enter amount"
          />
          
          {/* Fixed dropdown with proper currency filtering */}
          <div className="relative">
            <select
              value={selectedCurrency}
              onChange={(e) => setSelectedCurrency(e.target.value)}
              className="bg-zinc-800 p-3 pl-10 text-white outline-none border-l border-zinc-700 appearance-none cursor-pointer min-w-[100px]"
            >
              {fiatData
                .filter(currency => currency.code !== "INR")
                .map((currency) => (
                  <option
                    key={currency.code}
                    value={currency.code}
                    className="bg-zinc-900 text-white"
                  >
                    {currency.code}
                  </option>
                ))}
            </select>
            
            {/* Currency flag display */}
            <div className="absolute left-3 top-1/2 transform -translate-y-1/2 pointer-events-none">
              <ReactCountryFlag
                countryCode={getCurrencyCountryCode(selectedCurrency)}
                svg
                style={{
                  width: "1.2em",
                  height: "1.2em"
                }}
                title={selectedCurrency}
              />
            </div>
          </div>
        </div>

        {/* USDC Output */}
        <div className="bg-zinc-800/50 border border-zinc-700 rounded-xl p-4 mb-6">
          <p className="text-3xl font-bold text-white mt-1">
            {loading ? (
              <span className="text-zinc-500 animate-pulse">Getting Quote...</span>
            ) : (
              <>{usdcAmount} <span className="text-zinc-400 text-lg" >USDC</span></>
            )}
          </p>
        </div>

        {/* Buttons */}
        <div className="flex justify-between gap-3 items-center">
          {usdcAmount !== "0" && (
            <button
              onClick={handleViaExchange}
              disabled={isCreatingQuote}
              className="px-5 py-3 bg-gradient-to-r from-blue-900 to-green-700 text-white rounded-xl font-semibold hover:from-blue-800 hover:to-green-600 shadow-lg hover:shadow-xl transform hover:scale-[1.02] transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isCreatingQuote ? (
                <span className="animate-pulse">Loading...</span>
              ) : (
                `via ${bestExchange}`
              )}
            </button>
          )}

          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-5 py-3 border border-zinc-700 rounded-xl text-zinc-300 hover:bg-zinc-800 transition-colors duration-200"
            >
              Cancel
            </button>
            <button
              onClick={handleBuyNow}
              disabled={!usdcAmount || usdcAmount === "0"}
              className="px-5 py-3 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-xl font-semibold hover:from-blue-600 hover:to-purple-700 shadow-lg hover:shadow-xl transform hover:scale-[1.02] transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Buy Now
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// Helper function to map currency codes to country codes for flags
const getCurrencyCountryCode = (currencyCode: string): string => {
  const currencyToCountryMap: { [key: string]: string } = {
    'USD': 'US',
    'EUR': 'EU',
    'GBP': 'GB',
    'JPY': 'JP',
    'CAD': 'CA',
    'AUD': 'AU',
    'CHF': 'CH',
    'CNY': 'CN',
    'SEK': 'SE',
    'NZD': 'NZ',
    'KRW': 'KR',
    'SGD': 'SG',
    'NOK': 'NO',
    'MXN': 'MX',
    'BRL': 'BR',
    'RUB': 'RU',
    'ZAR': 'ZA',
    'TRY': 'TR',
    'PLN': 'PL',
    'DKK': 'DK',
    'HKD': 'HK',
    'THB': 'TH',
    'MYR': 'MY',
    'PHP': 'PH',
    'IDR': 'ID',
    'VND': 'VN'
  };
  
  return currencyToCountryMap[currencyCode] || 'US'; // Default to US if not found
};

export default BuyUSDCModal;