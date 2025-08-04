"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { 
  Building2, 
  DollarSign, 
  Users, 
  Save, 
  Loader2,
  CheckCircle,
  AlertCircle,
  ExternalLink
} from "lucide-react";
import { MarketplaceService } from "@/lib/marketplace";
import api from "@/lib/api";

interface BusinessData {
  name: string;
  description: string;
  category: string;
  linkedin: string;
  youtube: string;
  x: string;
}

interface FundraisingData {
  tokenName: string;
  price: number;
  isMintingActive: boolean;
}

export default function ManageBusinessPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<'details' | 'fundraising' | 'team'>('details');
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  
  const [businessData, setBusinessData] = useState<BusinessData>({
    name: '',
    description: '',
    category: '',
    linkedin: '',
    youtube: '',
    x: ''
  });
  
  const [fundraisingData, setFundraisingData] = useState<FundraisingData>({
    tokenName: '',
    price: 0,
    isMintingActive: false
  });

  const [existingBusinessId, setExistingBusinessId] = useState<string | null>(null);

  useEffect(() => {
    const userData = localStorage.getItem('userData');
    if (!userData) {
      router.push('/');
      return;
    }

    const fetchCategories = async () => {
      try {
        const categoriesData = await MarketplaceService.getCategories();
        setCategories(categoriesData.categories);
      } catch (err) {
        console.error('Failed to fetch categories:', err);
        setSaveError('Failed to load categories. Please try again later.');
      }
    };

    const fetchExistingBusiness = async () => {
      try {
        const userData = JSON.parse(localStorage.getItem('userData') || '{}');
        if (userData.user_id) {
          const businesses = await MarketplaceService.getBusinessItemsByOwner(userData.user_id);
          if (businesses.length > 0) {
            const business = businesses[0]; // Take the first business
            setExistingBusinessId(business.id);
            setBusinessData({
              name: business.name || '',
              description: business.description || '',
              category: business.category || '',
              linkedin: business.linkedin || '',
              youtube: business.youtube || '',
              x: business.x || ''
            });
            setFundraisingData({
              tokenName: business.token_name || '',
              price: business.price || 0,
              isMintingActive: business.is_minting_active || false
            });
          }
        }
      } catch (err) {
        console.error('Failed to fetch existing business:', err);
        // Don't show error for this as it's expected for new businesses
      }
    };

    const initializeData = async () => {
      await Promise.all([fetchCategories(), fetchExistingBusiness()]);
      setLoading(false);
    };

    initializeData();
  }, [router]);

  const handleBusinessDataChange = (field: keyof BusinessData, value: string) => {
    setBusinessData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleFundraisingDataChange = (field: keyof FundraisingData, value: string | number | boolean) => {
    setFundraisingData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSaveDetails = async () => {
    if (!businessData.name.trim() || !businessData.description.trim() || !businessData.category) {
      setSaveError('Please fill in all required fields (name, description, and category)');
      return;
    }

    setSaving(true);
    setSaveError(null);
    setSaveSuccess(null);

    try {
      const userData = JSON.parse(localStorage.getItem('userData') || '{}');
      
      if (existingBusinessId) {
        // Update existing business
        const updateData = {
          category: businessData.category,
          name: businessData.name,
          description: businessData.description,
          price: fundraisingData.price || 0,
          linkedin: businessData.linkedin || undefined,
          youtube: businessData.youtube || undefined,
          x: businessData.x || undefined
        };
        
        await api.put(`/api/v1/marketplace/${existingBusinessId}`, updateData);
      } else {
        // Create new marketplace item with business details
        const marketplaceItem = {
          category: businessData.category,
          name: businessData.name,
          description: businessData.description,
          price: fundraisingData.price || 0,
          linkedin: businessData.linkedin || undefined,
          youtube: businessData.youtube || undefined,
          x: businessData.x || undefined,
          owner_id: userData.user_id
        };

        const response = await api.post('/api/v1/marketplace', marketplaceItem);
        setExistingBusinessId(response.data.id);
      }
      
      setSaveSuccess('Business details saved successfully!');
      setTimeout(() => setSaveSuccess(null), 3000);
    } catch (err: any) {
      console.error('Failed to save business details:', err);
      setSaveError(err.response?.data?.detail || 'Failed to save business details. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveFundraising = async () => {
    if (!fundraisingData.tokenName.trim() || fundraisingData.price <= 0) {
      setSaveError('Please fill in all required fields (token name and price)');
      return;
    }

    if (!existingBusinessId) {
      setSaveError('Please save your business details first before configuring fundraising settings');
      return;
    }

    setSaving(true);
    setSaveError(null);
    setSaveSuccess(null);

    try {
      // Update marketplace item with fundraising data
      const fundraisingUpdate = {
        token_name: fundraisingData.tokenName,
        price: fundraisingData.price,
        is_minting_active: fundraisingData.isMintingActive
      };
      
      await api.put(`/api/v1/marketplace/business/${existingBusinessId}/fundraising`, fundraisingUpdate);
      
      setSaveSuccess('Fundraising settings saved successfully!');
      setTimeout(() => setSaveSuccess(null), 3000);
    } catch (err: any) {
      console.error('Failed to save fundraising settings:', err);
      setSaveError(err.response?.data?.detail || 'Failed to save fundraising settings. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleSave = () => {
    if (activeTab === 'details') {
      handleSaveDetails();
    } else if (activeTab === 'fundraising') {
      handleSaveFundraising();
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen w-full flex flex-col items-center justify-center bg-gradient-to-br from-black via-zinc-900 to-neutral-900 p-8">
        <Loader2 className="h-12 w-12 text-cyan-400 animate-spin mb-4" />
        <p className="text-zinc-400 text-lg">Loading business management...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900">
      {/* Header */}
      <div className="border-b border-zinc-800">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-white mb-2">Manage Business</h1>
              <p className="text-zinc-400">Configure your business profile and fundraising settings</p>
            </div>
            <button
              onClick={() => router.push('/business')}
              className="px-6 py-3 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg transition-colors"
            >
              Back to Dashboard
            </button>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8 max-w-4xl">
        {/* Tabs */}
        <div className="flex space-x-1 bg-zinc-800/50 rounded-lg p-1 mb-8">
          <button
            onClick={() => setActiveTab('details')}
            className={`flex-1 flex items-center justify-center space-x-2 py-3 px-4 rounded-md transition-all ${
              activeTab === 'details'
                ? 'bg-cyan-500 text-white shadow-lg'
                : 'text-zinc-400 hover:text-white hover:bg-zinc-700/50'
            }`}
          >
            <Building2 className="h-5 w-5" />
            <span>Details</span>
          </button>
          <button
            onClick={() => setActiveTab('fundraising')}
            className={`flex-1 flex items-center justify-center space-x-2 py-3 px-4 rounded-md transition-all ${
              activeTab === 'fundraising'
                ? 'bg-cyan-500 text-white shadow-lg'
                : 'text-zinc-400 hover:text-white hover:bg-zinc-700/50'
            }`}
          >
            <DollarSign className="h-5 w-5" />
            <span>Fundraising</span>
          </button>
          <button
            disabled
            className="flex-1 flex items-center justify-center space-x-2 py-3 px-4 rounded-md transition-all text-zinc-600 cursor-not-allowed opacity-50"
          >
            <Users className="h-5 w-5" />
            <span>Team</span>
          </button>
        </div>

        {/* Business Status */}
        {existingBusinessId && (
          <div className="mb-6 p-4 bg-cyan-900/20 border border-cyan-500/30 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-white">Business Status</h3>
                <p className="text-cyan-400 text-sm">Your business is live on the marketplace</p>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
                <span className="text-green-400 text-sm font-medium">Active</span>
              </div>
            </div>
          </div>
        )}

        {/* Success/Error Messages */}
        {saveSuccess && (
          <div className="mb-6 p-4 bg-green-900/30 border border-green-500/30 rounded-lg flex items-center space-x-3">
            <CheckCircle className="h-5 w-5 text-green-400" />
            <span className="text-green-400">{saveSuccess}</span>
          </div>
        )}

        {saveError && (
          <div className="mb-6 p-4 bg-red-900/30 border border-red-500/30 rounded-lg flex items-center space-x-3">
            <AlertCircle className="h-5 w-5 text-red-400" />
            <span className="text-red-400">{saveError}</span>
          </div>
        )}

        {/* Tab Content */}
        {activeTab === 'details' && (
          <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-8 backdrop-blur-sm">
            <h2 className="text-2xl font-bold text-white mb-6">Business Details</h2>
            
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">
                  Business Name *
                </label>
                <input
                  type="text"
                  value={businessData.name}
                  onChange={(e) => handleBusinessDataChange('name', e.target.value)}
                  className="w-full px-4 py-3 bg-zinc-900/50 border border-zinc-600/50 rounded-lg text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
                  placeholder="Enter your business name"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">
                  Description *
                </label>
                <textarea
                  value={businessData.description}
                  onChange={(e) => handleBusinessDataChange('description', e.target.value)}
                  rows={4}
                  className="w-full px-4 py-3 bg-zinc-900/50 border border-zinc-600/50 rounded-lg text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent resize-none"
                  placeholder="Describe your business and what makes it unique"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">
                  Category *
                </label>
                <select
                  value={businessData.category}
                  onChange={(e) => handleBusinessDataChange('category', e.target.value)}
                  className="w-full px-4 py-3 bg-zinc-900/50 border border-zinc-600/50 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
                >
                  <option value="">Select a category</option>
                  {categories.map((category) => (
                    <option key={category} value={category}>
                      {category}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-zinc-300 mb-2">
                    LinkedIn URL
                  </label>
                  <div className="relative">
                    <input
                      type="url"
                      value={businessData.linkedin}
                      onChange={(e) => handleBusinessDataChange('linkedin', e.target.value)}
                      className="w-full px-4 py-3 bg-zinc-900/50 border border-zinc-600/50 rounded-lg text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
                      placeholder="https://linkedin.com/company/..."
                    />
                    {businessData.linkedin && (
                      <ExternalLink className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-zinc-400" />
                    )}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-zinc-300 mb-2">
                    YouTube URL
                  </label>
                  <div className="relative">
                    <input
                      type="url"
                      value={businessData.youtube}
                      onChange={(e) => handleBusinessDataChange('youtube', e.target.value)}
                      className="w-full px-4 py-3 bg-zinc-900/50 border border-zinc-600/50 rounded-lg text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
                      placeholder="https://youtube.com/..."
                    />
                    {businessData.youtube && (
                      <ExternalLink className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-zinc-400" />
                    )}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-zinc-300 mb-2">
                    X (Twitter) URL
                  </label>
                  <div className="relative">
                    <input
                      type="url"
                      value={businessData.x}
                      onChange={(e) => handleBusinessDataChange('x', e.target.value)}
                      className="w-full px-4 py-3 bg-zinc-900/50 border border-zinc-600/50 rounded-lg text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
                      placeholder="https://x.com/..."
                    />
                    {businessData.x && (
                      <ExternalLink className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-zinc-400" />
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'fundraising' && (
          <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-8 backdrop-blur-sm">
            <h2 className="text-2xl font-bold text-white mb-6">Fundraising Settings</h2>
            
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">
                  Token Name *
                </label>
                <input
                  type="text"
                  value={fundraisingData.tokenName}
                  onChange={(e) => handleFundraisingDataChange('tokenName', e.target.value)}
                  className="w-full px-4 py-3 bg-zinc-900/50 border border-zinc-600/50 rounded-lg text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
                  placeholder="Enter your token name (e.g., MYTOKEN)"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">
                  Token Price (USDC) *
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={fundraisingData.price}
                  onChange={(e) => handleFundraisingDataChange('price', parseFloat(e.target.value) || 0)}
                  className="w-full px-4 py-3 bg-zinc-900/50 border border-zinc-600/50 rounded-lg text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent"
                  placeholder="0.00"
                />
              </div>

              <div className="flex items-center justify-between p-4 bg-zinc-900/30 rounded-lg border border-zinc-600/30">
                <div>
                  <h3 className="text-lg font-medium text-white">Token Minting</h3>
                  <p className="text-zinc-400 text-sm">
                    {fundraisingData.isMintingActive 
                      ? 'Minting is currently active and investors can purchase tokens'
                      : 'Minting is paused and no new tokens can be purchased'
                    }
                  </p>
                </div>
                <button
                  onClick={() => handleFundraisingDataChange('isMintingActive', !fundraisingData.isMintingActive)}
                  className={`px-6 py-3 rounded-lg font-medium transition-all ${
                    fundraisingData.isMintingActive
                      ? 'bg-red-600 hover:bg-red-700 text-white'
                      : 'bg-green-600 hover:bg-green-700 text-white'
                  }`}
                >
                  {fundraisingData.isMintingActive ? 'Pause Minting' : 'Start Minting'}
                </button>
              </div>

              {/* Fundraising Summary */}
              {fundraisingData.tokenName && fundraisingData.price > 0 && (
                <div className="p-4 bg-gradient-to-r from-cyan-900/20 to-blue-900/20 border border-cyan-500/30 rounded-lg">
                  <h3 className="text-lg font-medium text-white mb-3">Fundraising Summary</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-zinc-400 text-sm">Token Name</p>
                      <p className="text-white font-semibold">{fundraisingData.tokenName}</p>
                    </div>
                    <div>
                      <p className="text-zinc-400 text-sm">Token Price</p>
                      <p className="text-white font-semibold">${fundraisingData.price.toFixed(2)} USDC</p>
                    </div>
                    <div>
                      <p className="text-zinc-400 text-sm">Minting Status</p>
                      <p className={`font-semibold ${fundraisingData.isMintingActive ? 'text-green-400' : 'text-red-400'}`}>
                        {fundraisingData.isMintingActive ? 'Active' : 'Paused'}
                      </p>
                    </div>
                    <div>
                      <p className="text-zinc-400 text-sm">Marketplace Status</p>
                      <p className="text-green-400 font-semibold">Live</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'team' && (
          <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-8 backdrop-blur-sm">
            <div className="text-center py-12">
              <Users className="h-16 w-16 text-zinc-600 mx-auto mb-4" />
              <h2 className="text-2xl font-bold text-white mb-2">Team Management</h2>
              <p className="text-zinc-400">Team management features are coming soon!</p>
            </div>
          </div>
        )}

        {/* Save Button */}
        {activeTab !== 'team' && (
          <div className="mt-8 flex justify-end">
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center space-x-2 px-8 py-3 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white font-medium rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Save className="h-5 w-5" />
                  <span>Save Changes</span>
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
} 