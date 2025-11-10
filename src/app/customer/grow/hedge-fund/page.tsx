"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle, AlertCircle } from "lucide-react";
import api from "@/lib/api";
import HedgeFundDashboard from "@/components/HedgeFundDashboard";
import { HedgeFundForm } from "@/lib/types";

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
  const [showDashboard, setShowDashboard] = useState(true);

  useEffect(() => {
    const storedUserData = localStorage.getItem('userData');
    if (storedUserData) {
      const parsedData = JSON.parse(storedUserData);
      setUserData(parsedData);
      
      // Check if user has already submitted a questionnaire
      if (parsedData?.user_id) {
        // checkExistingSubmission(parsedData.user_id);
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
        setShowDashboard(true); // Show dashboard if user has completed questionnaire
        
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
      setLoading(false);
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
          setShowDashboard(true); // Show dashboard after successful submission
          setTimeout(() => {
            setSuccess(false);
          }, 3000);
        }
      }
    } catch (err: any) {
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
    <div className="mb-8 p-6 bg-zinc-900/50 rounded-xl border border-zinc-700/50">
      <h3 className="text-lg font-semibold text-white mb-4">{title}</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {options.map((option) => (
          <label key={option.value} className="flex items-center p-4 rounded-lg bg-zinc-800/50 hover:bg-zinc-700/50 border border-zinc-700/50 cursor-pointer transition-all duration-200">
            <input
              type="radio"
              name={field}
              value={option.value}
              checked={formData[field] === option.value}
              onChange={(e) => handleInputChange(field, e.target.value)}
              className="w-5 h-5 text-blue-500 bg-zinc-700 border-zinc-600 focus:ring-blue-500 focus:ring-2 focus:ring-offset-2 focus:ring-offset-zinc-900"
            />
            <span className="ml-4 text-zinc-300 group-hover:text-white transition-colors">
              {option.label}
            </span>
          </label>
        ))}
      </div>
    </div>
  );

  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const totalFields = Object.keys(formData).length;
    const filledFields = Object.values(formData).filter(value => value !== "").length;
    setProgress((filledFields / totalFields) * 100);
  }, [formData]);

  if (success) {
    return (
      <div className="min-h-screen w-full flex flex-col items-center justify-center bg-gradient-to-br from-black via-zinc-900 to-neutral-900 p-8">
        <div className="text-center max-w-md bg-zinc-800/50 backdrop-blur-sm border border-zinc-700/50 rounded-2xl p-8 shadow-2xl">
          <div className="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <CheckCircle className="h-10 w-10 text-green-400" />
          </div>
          <h2 className="text-3xl font-bold text-white mb-4">All Set!</h2>
          <p className="text-zinc-400 mb-8">
            Your investment profile is complete. You can now explore personalized hedge fund strategies.
          </p>
          <button
            onClick={() => setShowDashboard(true)}
            className="w-full bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white font-semibold py-4 px-8 rounded-xl transition-all duration-200 transform hover:scale-[1.02] active:scale-[0.98]"
          >
            Go to Dashboard
          </button>
        </div>
      </div>
    );
  }

  // Show dashboard if user has completed questionnaire
  if (showDashboard) {
    return <HedgeFundDashboard />;
  }

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900 p-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        {/* <div className="flex items-center mb-8">
          <button
            onClick={() => router.back()}
            className="flex items-center space-x-2 text-zinc-400 hover:text-white transition-colors mb-4"
          >
            <ArrowLeft className="h-5 w-5" />
            <span>Back</span>
          </button>
        </div> */}
        <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900 dark overflow-x-hidden flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent mx-auto mb-4"></div>
            <p className="text-zinc-400 font-medium">
            Loading your hedge fund dashboard...
            </p>
          </div>
      </div>
      </div>
    </div>
  );
} 