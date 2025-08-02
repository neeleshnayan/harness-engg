"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle, AlertCircle } from "lucide-react";
import api from "@/lib/api";

interface HedgeFundForm {
  age: string;
  annualIncome: string;
  emergencyFund: string;
  investmentDropReaction: string;
  investmentStyle: string;
  marketLossExperience: string;
  portfolioComfort: string;
}

export default function HedgeFundPage() {
  const router = useRouter();
  const [formData, setFormData] = useState<HedgeFundForm>({
    age: "",
    annualIncome: "",
    emergencyFund: "",
    investmentDropReaction: "",
    investmentStyle: "",
    marketLossExperience: "",
    portfolioComfort: ""
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [userData, setUserData] = useState<any>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [existingSubmission, setExistingSubmission] = useState<any>(null);

  useEffect(() => {
    const storedUserData = localStorage.getItem('userData');
    if (storedUserData) {
      const parsedData = JSON.parse(storedUserData);
      setUserData(parsedData);
      
      // Check if user has already submitted a questionnaire
      if (parsedData?.user_id) {
        checkExistingSubmission(parsedData.user_id);
      }
    }
  }, []);

  const checkExistingSubmission = async (userId: string) => {
    try {
      const response = await api.get(`/api/v1/hedge-fund/${userId}`);
      if (response.status === 200 && response.data.status === "success") {
        const submissionData = response.data.data;
        setExistingSubmission(submissionData);
        setIsEditing(true);
        
        // Pre-populate form with existing data
        setFormData({
          age: submissionData.age,
          annualIncome: submissionData.annualIncome,
          emergencyFund: submissionData.emergencyFund,
          investmentDropReaction: submissionData.investmentDropReaction,
          investmentStyle: submissionData.investmentStyle,
          marketLossExperience: submissionData.marketLossExperience,
          portfolioComfort: submissionData.portfolioComfort
        });
      }
    } catch (err: any) {
      // If 404, user hasn't submitted yet, which is fine
      if (err.response?.status !== 404) {
        console.error('Error checking existing submission:', err);
      }
    }
  };

  const handleInputChange = (field: keyof HedgeFundForm, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate all fields are filled
    const requiredFields = Object.keys(formData) as (keyof HedgeFundForm)[];
    const emptyFields = requiredFields.filter(field => !formData[field]);
    
    if (emptyFields.length > 0) {
      setError("Please fill in all required fields");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const endpoint = isEditing ? "/api/v1/hedge-fund/update" : "/api/v1/hedge-fund/submit";
      const response = await api.post(endpoint, {
        user_id: userData?.user_id,
        submission_id: existingSubmission?.id, // Include submission ID for updates
        ...formData
      });

      if (response.status === 200 || response.status === 201) {
        // Check if user has already submitted
        if (response.data.status === "already_submitted") {
          setError("You have already submitted a hedge fund questionnaire. Please contact support if you need to update your responses.");
          setTimeout(() => {
            router.push('/customer/grow');
          }, 5000);
        } else {
          setSuccess(true);
          setTimeout(() => {
            router.push('/customer/grow');
          }, 3000);
        }
      }
    } catch (err: any) {
      console.error('Error submitting hedge fund form:', err);
      setError(err.response?.data?.detail || "Failed to submit questionnaire. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const RadioGroup = ({ 
    title, 
    field, 
    options 
  }: { 
    title: string; 
    field: keyof HedgeFundForm; 
    options: { value: string; label: string }[] 
  }) => (
    <div className="mb-8">
      <h3 className="text-lg font-semibold text-white mb-4">{title}</h3>
      <div className="space-y-3">
        {options.map((option) => (
          <label key={option.value} className="flex items-center space-x-3 cursor-pointer group">
            <input
              type="radio"
              name={field}
              value={option.value}
              checked={formData[field] === option.value}
              onChange={(e) => handleInputChange(field, e.target.value)}
              className="w-4 h-4 text-blue-600 bg-zinc-800 border-zinc-600 focus:ring-blue-500 focus:ring-2"
            />
            <span className="text-zinc-300 group-hover:text-white transition-colors">
              {option.label}
            </span>
          </label>
        ))}
      </div>
    </div>
  );

  if (success) {
    return (
      <div className="min-h-screen w-full flex flex-col items-center justify-center bg-gradient-to-br from-black via-zinc-900 to-neutral-900 p-8">
        <div className="text-center max-w-md">
          <div className="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle className="h-10 w-10 text-green-400" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-4">Questionnaire Submitted!</h2>
          <p className="text-zinc-400 mb-6">
            Thank you for completing the hedge fund questionnaire. Our team will review your responses and contact you soon.
          </p>
          <p className="text-sm text-zinc-500">
            Redirecting you back to the grow page...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900 p-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="flex items-center mb-8">
          <button
            onClick={() => router.back()}
            className="flex items-center space-x-2 text-zinc-400 hover:text-white transition-colors mb-4"
          >
            <ArrowLeft className="h-5 w-5" />
            <span>Back</span>
          </button>
        </div>

        <div className="bg-zinc-800/50 backdrop-blur-sm border border-zinc-700/50 rounded-2xl p-8 shadow-2xl">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-white mb-4">Hedge Fund Questionnaire</h1>
            <p className="text-zinc-400">
              Help us understand your investment profile to provide personalized hedge fund recommendations.
            </p>
            {isEditing && (
              <div className="mt-4 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                <p className="text-blue-400 font-medium">
                  You've already submitted the questionnaire. You can still edit your response.
                </p>
              </div>
            )}
          </div>

          {error && (
            <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center space-x-3">
              <AlertCircle className="h-5 w-5 text-red-400" />
              <span className="text-red-400">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <RadioGroup
              title="Age"
              field="age"
              options={[
                { value: "under_30", label: "Under 30" },
                { value: "30_45", label: "30–45" },
                { value: "46_60", label: "46–60" },
                { value: "60_plus", label: "60+" }
              ]}
            />

            <RadioGroup
              title="Annual Income (approx.)"
              field="annualIncome"
              options={[
                { value: "below_50000", label: "Below $50,000" },
                { value: "50000_100000", label: "$50,000–$100,000" },
                { value: "100000_250000", label: "$100,000–$250,000" },
                { value: "above_250000", label: "Above $250,000" }
              ]}
            />

            <RadioGroup
              title="Emergency Fund"
              field="emergencyFund"
              options={[
                { value: "none", label: "None" },
                { value: "1_3_months", label: "Covers 1–3 months" },
                { value: "3_6_months", label: "Covers 3–6 months" },
                { value: "more_than_6_months", label: "More than 6 months" }
              ]}
            />

            <RadioGroup
              title="How would you feel if your investment dropped 20% in a year?"
              field="investmentDropReaction"
              options={[
                { value: "very_anxious", label: "Very anxious—would consider selling" },
                { value: "uncomfortable", label: "Uncomfortable—but would likely hold" },
                { value: "acceptable", label: "Acceptable—it's part of investing" },
                { value: "invest_more", label: "Would invest more at lower prices" }
              ]}
            />

            <RadioGroup
              title="Which investment style suits you best?"
              field="investmentStyle"
              options={[
                { value: "safety_over_returns", label: "Prefer safety over returns" },
                { value: "moderate_returns", label: "Want moderate returns with some risk" },
                { value: "high_risk_high_returns", label: "Comfortable with high risk for high returns" }
              ]}
            />

            <RadioGroup
              title="Have you experienced a market loss before?"
              field="marketLossExperience"
              options={[
                { value: "no", label: "No" },
                { value: "yes_exited", label: "Yes, and I exited" },
                { value: "yes_held", label: "Yes, and I held on" },
                { value: "yes_bought_more", label: "Yes, and I bought more" }
              ]}
            />

            <RadioGroup
              title="Choose the portfolio you're most comfortable with:"
              field="portfolioComfort"
              options={[
                { value: "conservative", label: "Conservative (20% stocks, 80% bonds)" },
                { value: "moderate", label: "Moderate (60% stocks, 40% bonds)" },
                { value: "aggressive", label: "Aggressive (80% stocks, 20% bonds)" },
                { value: "very_aggressive", label: "Very Aggressive (100% stocks)" }
              ]}
            />

            <div className="pt-6">
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 disabled:from-zinc-600 disabled:to-zinc-700 text-white font-semibold py-4 px-8 rounded-xl transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98] disabled:transform-none"
              >
                {loading ? (isEditing ? "Updating..." : "Submitting...") : (isEditing ? "Update Questionnaire" : "Submit Questionnaire")}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
} 