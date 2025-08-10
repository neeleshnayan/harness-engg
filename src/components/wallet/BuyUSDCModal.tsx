import axios from "axios";
import React, { useState, useEffect } from "react";
import ReactCountryFlag from "react-country-flag";

interface FiatCurrency {
  code: string;
  symbol: string;
}

interface BuyUSDCModalProps {
  fiatData: FiatCurrency[];
  onClose: () => void;
}

const BuyUSDCModal: React.FC<BuyUSDCModalProps> = ({ fiatData, onClose }) => {
  const [selectedCurrency, setSelectedCurrency] = useState<string>(
    fiatData[0]?.code || "EUR"
  );
  const [amount, setAmount] = useState<string>("");
  const [usdcAmount, setUsdcAmount] = useState<string>("0");
  const [loading, setLoading] = useState<boolean>(false);

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
        // Fixed template literal syntax with backticks
        const res = await axios.get(
          `https://api-stg.transak.com/api/v1/pricing/public/quotes?partnerApiKey=f4c10825-55fd-4ccc-bd3f-40fc021468e5&fiatCurrency=${selectedCurrency}&cryptoCurrency=USDC&fiatAmount=${amount}&isBuyOrSell=BUY&network=ethereum&paymentMethod=credit_debit_card`
        );
        const val = res.data?.response?.cryptoAmount || 0;
        if (isMounted) {
          setUsdcAmount(val.toFixed(2));
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

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-md flex items-center p-2 pt-4 pb-4 mt-4 mb-10 justify-center z-50">
      <div className="bg-zinc-900/90 border border-zinc-800 rounded-2xl w-full max-w-md p-2 shadow-2xl">
        {/* Header */}
        <h2 className="text-2xl font-bold text-white mb-6 text-center">
          Buy USDC
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
              <span className="text-blue-400 animate-pulse">Calculating...</span>
            ) : (
              `$${usdcAmount} USDC`
            )}
          </p>
        </div>

        {/* Buttons */}
        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-5 py-3 border border-zinc-700 rounded-xl text-zinc-300 hover:bg-zinc-800 transition-colors duration-200"
          >
            Cancel
          </button>
          <button
            className="px-5 py-3 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-xl font-semibold hover:from-blue-600 hover:to-purple-700 shadow-lg hover:shadow-xl transform hover:scale-[1.02] transition-all duration-300"
          >
            Buy Now
          </button>
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