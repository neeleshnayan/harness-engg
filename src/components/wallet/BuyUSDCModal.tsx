import axios from "axios";
import React, { useState, useEffect } from "react";
import ReactCountryFlag from "react-country-flag";
import { fetchOnrampQuote } from '@coinbase/onchainkit/fund';
import { number } from "zod";

interface FiatCurrency {
  code: string;
  symbol: string;
}

interface BuyUSDCModalProps {
  fiatData: FiatCurrency[];
  onClose: () => void;
  walletAddress?: string;
}

const TRANSAK_PARTNER_API_KEY = process.env.NEXT_PUBLIC_TRANSAK_PARTNER_API_KEY;

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
  const [inputMode, setInputMode] = useState<'fiat' | 'usdc'>('fiat');
  const [exchangeRates, setExchangeRates] = useState<{ [key: string]: string }>({});
  const [showRates, setShowRates] = useState<boolean>(false);
  const [transakQuoteUSDC, setTransakQuoteUSDC] = useState<string>("0");
  const [coinbaseQuoteUSDC, setCoinbaseQuoteUSDC] = useState<string>("0");
  const [transakFiatQuote, setTransakFiatQuote] = useState<string>("0");
  const [coinbaseFiatQuote, setCoinbaseFiatQuote] = useState<string>("0");

  // Fetch exchange rates once at component initialization
  useEffect(() => {
    const fetchExchangeRates = async () => {
      try {
        const currencyToUSD = await fetch(`https://api.coinbase.com/v2/exchange-rates?currency=USD`);
        const currencyToUSDJson = await currencyToUSD.json();
        setExchangeRates(currencyToUSDJson.data.rates);
      } catch (error) {
        console.error('Error fetching exchange rates:', error);
        // Set default rates if API fails
        setExchangeRates({});
      }
    };

    fetchExchangeRates();
  }, []);

  // Function to calculate fiat amount needed for a specific USDC amount
  const calculateFiatAmount = async (usdcAmount: string, currency: string): Promise<string> => {
    if (!usdcAmount || isNaN(Number(usdcAmount))) {
      return "0";
    }

    try {
      // Use a small fiat amount to get the rate, then calculate backwards
      const transak_url = `https://api-stg.transak.com/api/v1/pricing/public/quotes?partnerApiKey=${TRANSAK_PARTNER_API_KEY}&fiatCurrency=${currency}&cryptoCurrency=USDC&cryptoAmount=${usdcAmount}&isBuyOrSell=BUY&network=ethereum&paymentMethod=credit_debit_card`;
      
      let transakResponse;
      let coinbaseQuoteResponse;
      
      try {
        transakResponse = await axios.get(transak_url);
      } catch (error) {
        console.error('Error fetching Transak quote in getMinFiatAmount:', error);
        transakResponse = { data: { response: null } };
      }
      
      var transak_fiatamount = "999999999";
      if (transakResponse.data?.response?.fiatAmount) {
        transak_fiatamount = Math.min(999999999, parseFloat(transakResponse.data.response.fiatAmount)).toFixed(2);
      }

      try {
        const conversionRate = exchangeRates[currency];
        if (!conversionRate) {
          console.error(`Exchange rate not found for currency: ${currency}`);
          return "0";
        }
        coinbaseQuoteResponse = await fetch('https://api.developer.coinbase.com/onramp/v1/buy/quote', {
          method: 'POST',
          body: JSON.stringify({
            purchase_currency: 'USDC',
            purchase_network: 'ethereum',
            payment_currency: currency,
            payment_method: 'CARD',
            payment_amount: (parseFloat(usdcAmount)*parseFloat(conversionRate)/0.97).toFixed(2),
            country: 'GB',
            destinationAddress: walletAddress || ''
          }),
          headers: {
            Authorization: `Bearer ${process.env.NEXT_PUBLIC_COINBASE_API_KEY}`,
          },
        });
      } catch (error) {
        console.error('Error fetching Coinbase quote in getMinFiatAmount:', error);
        coinbaseQuoteResponse = { json: async () => ({ payment_total: { value: "999999999" } }) };
      }
      var coinbase_fiatamount = "999999999";
      const coinbaseQuote = await coinbaseQuoteResponse.json();
      const coinbaseAmount = coinbaseQuote?.payment_total?.value || "999999999";
      coinbase_fiatamount = Math.min(999999999, parseFloat(coinbaseAmount)).toFixed(2);
      // store individual fiat quotes for rate card
      setTransakFiatQuote(transak_fiatamount);
      setCoinbaseFiatQuote(coinbase_fiatamount);
      const min_fiatamount = Math.min(parseFloat(transak_fiatamount), parseFloat(coinbase_fiatamount));
      if (min_fiatamount == 999999999) {
        return "0";
      }
      if (parseFloat(coinbase_fiatamount) < parseFloat(transak_fiatamount)) {
        setBestExchange("Coinbase");
      } else {
        setBestExchange("Transak");
      }
      return min_fiatamount.toFixed(2);
    } catch (error) {
      console.error("Error calculating fiat amount:", error);
      return "0";
    }
  };

  const [calculatedFiatAmount, setCalculatedFiatAmount] = useState<string>("0");

  useEffect(() => {
    if (!amount || isNaN(Number(amount))) {
      if (inputMode === 'fiat') {
        setUsdcAmount("0");
      } else {
        setCalculatedFiatAmount("0");
      }
      return;
    }

    let isMounted = true;

    const fetchData = async () => {
      setLoading(true);
      try {
        if (inputMode === 'fiat') {
          // Original logic for fiat to USDC conversion
          const transak_url = `https://api-stg.transak.com/api/v1/pricing/public/quotes?partnerApiKey=${TRANSAK_PARTNER_API_KEY}&fiatCurrency=${selectedCurrency}&cryptoCurrency=USDC&fiatAmount=${amount}&isBuyOrSell=BUY&network=ethereum&paymentMethod=credit_debit_card`
          
          let transakResponse;
          let coinbaseQuoteResponse;
          
          try {
            transakResponse = await axios.get(transak_url);
          } catch (error) {
            console.error('Error fetching Transak quote:', error);
            transakResponse = { data: { response: { cryptoAmount: 0 } } };
          }
          
          try {
            coinbaseQuoteResponse = await fetch('https://api.developer.coinbase.com/onramp/v1/buy/quote', {
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
                Authorization: `Bearer ${process.env.NEXT_PUBLIC_COINBASE_API_KEY}`,
              },
            });
          } catch (error) {
            console.error('Error fetching Coinbase quote:', error);
            coinbaseQuoteResponse = { json: async () => ({ onramp_url: "", purchase_amount: { value: "0" } }) };
          }
          
          const coinbaseQuote = await coinbaseQuoteResponse.json();
          setCoinbaseBuyUrl(coinbaseQuote?.onramp_url || "");
          const transakAmount = transakResponse.data?.response?.cryptoAmount || 0;
          const coinbaseAmount = coinbaseQuote?.purchase_amount?.value || "0";
          const val = Math.max(parseFloat(transakAmount), parseFloat(coinbaseAmount)).toFixed(2);

          if (isMounted) {
            setUsdcAmount(val);
            // store individual usdc quotes for rate card
            setTransakQuoteUSDC(parseFloat(transakAmount || 0).toFixed(2));
            setCoinbaseQuoteUSDC(parseFloat(coinbaseAmount || 0).toFixed(2));
            if (parseFloat(transakAmount) > parseFloat(coinbaseAmount)) {
              setBestExchange("Transak");
            } else {
              setBestExchange("Coinbase");
              setCoinbaseBuyUrl(coinbaseQuote.onramp_url || "");
            }
          }
        } else {
          // New logic for USDC to fiat conversion
          const fiatAmount = await calculateFiatAmount(amount, selectedCurrency);
          if (isMounted) {
            setUsdcAmount(amount); // Set USDC amount to input value
            setCalculatedFiatAmount(fiatAmount);
          }
        }
      } catch (error) {
        console.error("Error fetching USDC:", error);
        if (isMounted) {
          if (inputMode === 'fiat') {
            setUsdcAmount("0");
          } else {
            setCalculatedFiatAmount("0");
          }
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
  }, [amount, selectedCurrency, inputMode]);

  // Reset amounts when switching input modes
  useEffect(() => {
    setAmount("");
    setUsdcAmount("0");
    setCalculatedFiatAmount("0");
  }, [inputMode]);

  const handleBuyNow = async () => {
    if (bestExchange === "Coinbase" && coinbaseBuyUrl) {
      // Open Coinbase widget in a new window/tab
      window.open(coinbaseBuyUrl, '_blank', 'width=500,height=700');
    } else {
      // Fallback for Transak or when Coinbase URL is not available
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
    }
  };

  const handleSwapInputMode = () => {
    setInputMode(inputMode === 'fiat' ? 'usdc' : 'fiat');
    setShowRates(false);
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-md flex items-center p-2 pt-4 pb-4 mt-4 mb-10 justify-center z-50">
      <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl w-full max-w-md p-2 shadow-2xl">
        {/* Header */}
        <h2 className="flex items-center justify-center text-2xl font-bold text-white mb-6 text-center">
          <svg
            className="w-8 h-8 text-blue-400 mr-3"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          Add USDC
        </h2>

        {/* Amount Input */}
        <div className="relative mb-5">
          <div className="flex items-center bg-zinc-800/50 border border-zinc-700 rounded-xl overflow-hidden">
            <input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="flex-1 bg-transparent p-3 text-white placeholder-zinc-500 outline-none"
              placeholder={inputMode === 'fiat' ? `Enter ${selectedCurrency} amount` : "Enter USDC amount"}
            />
            
            {/* Fixed dropdown with proper currency filtering */}
            <div className="relative">
              <select
                value={selectedCurrency}
                onChange={(e) => setSelectedCurrency(e.target.value)}
                className="bg-zinc-800 p-3 pl-10 text-white outline-none border-l border-zinc-700 appearance-none cursor-pointer min-w-[100px]"
              >
                {fiatData
                  // .filter(currency => currency.code !== "INR")
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
        </div>

        {/* Floating swap icon overlapping both inputs */}
        <div className="relative mb-5">
          <div className="absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2 z-10">
            <div className="bg-zinc-700 hover:bg-zinc-600 rounded-full p-3 shadow-lg cursor-pointer transition-all duration-200 hover:scale-110 border-2 border-zinc-900" onClick={handleSwapInputMode}>
              <svg
                className="w-6 h-6 text-white"

                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"
                />
              </svg>
            </div>
          </div>
        </div>

        {/* Output Display */}
        <div className="relative mb-6">
          <div className="bg-zinc-800/50 border border-zinc-700 rounded-xl p-4">
            {inputMode === 'fiat' ? (
              // Show USDC amount when inputting fiat
              <div>
                <p className="text-sm text-zinc-400 mb-1">You'll receive:</p>
                <p className="text-3xl font-bold text-white mt-1">
                  {loading ? (
                    <span className="text-zinc-500 animate-pulse">Getting Quote...</span>
                  ) : (
                    <>{usdcAmount} <span className="text-zinc-400 text-lg" >USDC</span></>
                  )}
                </p>
              </div>
            ) : (
              // Show fiat amount when inputting USDC
              <div>
                <p className="text-sm text-zinc-400 mb-1">You'll pay:</p>
                <p className="text-3xl font-bold text-white mt-1">
                  {loading ? (
                    <span className="text-zinc-500 animate-pulse">Calculating...</span>
                  ) : (
                    <>{calculatedFiatAmount} <span className="text-zinc-400 text-lg" >{selectedCurrency}</span></>
                  )}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Buttons */}
        <div className="flex justify-between gap-3 items-center">
          {((inputMode === 'fiat' && usdcAmount !== "0") || (inputMode === 'usdc' && amount !== "")) && (
            <button
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
            {((inputMode === 'fiat' && usdcAmount !== "0") || (inputMode === 'usdc' && calculatedFiatAmount !== "0")) && (
              <button
                onClick={() => setShowRates(!showRates)}
                className="px-5 py-3 bg-gradient-to-r from-blue-900 to-green-700 text-white rounded-xl font-semibold hover:from-blue-800 hover:to-green-600 shadow-lg hover:shadow-xl transform hover:scale-[1.02] transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {showRates ? 'Hide rates' : 'View rates'}
              </button>
            )}
            <button
              onClick={onClose}
              className="px-5 py-3 border border-zinc-700 rounded-xl text-zinc-300 hover:bg-zinc-800 transition-colors duration-200"
            >
              Cancel
            </button>
            <button
              onClick={handleBuyNow}
              disabled={!amount || amount === "" || (inputMode === 'fiat' && usdcAmount === "0")}
              className="px-5 py-3 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-xl font-semibold hover:from-blue-600 hover:to-purple-700 shadow-lg hover:shadow-xl transform hover:scale-[1.02] transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Buy Now
            </button>
          </div>
        </div>
        {showRates && (
          <div className="mt-4 bg-zinc-800/50 border border-zinc-700 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-zinc-400">Best offer</span>
              <span className="text-xs px-2 py-1 rounded-full bg-green-900/30 text-green-400 border border-green-600/30">{bestExchange}</span>
            </div>
            {inputMode === 'fiat' ? (
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-zinc-900/40 rounded-lg p-3 border border-zinc-700/50">
                  <div className="text-xs text-zinc-400 mb-1">Transak (USDC received)</div>
                  <div className="text-white text-lg font-semibold">{transakQuoteUSDC} <span className="text-zinc-400 text-sm">USDC</span></div>
                </div>
                <div className="bg-zinc-900/40 rounded-lg p-3 border border-zinc-700/50">
                  <div className="text-xs text-zinc-400 mb-1">Coinbase (USDC received)</div>
                  <div className="text-white text-lg font-semibold">{coinbaseQuoteUSDC} <span className="text-zinc-400 text-sm">USDC</span></div>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-zinc-900/40 rounded-lg p-3 border border-zinc-700/50">
                  <div className="text-xs text-zinc-400 mb-1">Transak (You pay)</div>
                  <div className="text-white text-lg font-semibold">{transakFiatQuote} <span className="text-zinc-400 text-sm">{selectedCurrency}</span></div>
                </div>
                <div className="bg-zinc-900/40 rounded-lg p-3 border border-zinc-700/50">
                  <div className="text-xs text-zinc-400 mb-1">Coinbase (You pay)</div>
                  <div className="text-white text-lg font-semibold">{coinbaseFiatQuote} <span className="text-zinc-400 text-sm">{selectedCurrency}</span></div>
                </div>
              </div>
            )}
          </div>
        )}
        <p className="text-sm text-zinc-400 mt-1 mb-1">Powered by Coinbase & Transak</p>
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
    'INR': 'IN',
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