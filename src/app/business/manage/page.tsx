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
  ExternalLink,
  Plus,
  History,
  ChevronDown,
  UserPlus
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
  pitchVideo: string;
}

interface FundraisingData {
  tokenName: string;
  price: number;
  isMintingActive: boolean;
}

interface TeamMember {
  id: string;
  name: string;
  kryptonId: string; // Added Krypton ID
  type: 'employee' | 'intern' | 'vendor';
  usdcPayment: number;
  tokenPayment: number;
  schedule: 'monthly' | 'weekly' | 'custom';
  createdAt: string;
}

interface TeamData {
  members: TeamMember[];
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
    x: '',
    pitchVideo: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
  });

  const [fundraisingData, setFundraisingData] = useState<FundraisingData>({
    tokenName: '',
    price: 0,
    isMintingActive: false
  });

  const [teamData, setTeamData] = useState<TeamData>({
    members: []
  });

  const [existingBusinessId, setExistingBusinessId] = useState<string | null>(null);
  const [showAddMemberModal, setShowAddMemberModal] = useState(false);
  const [newMember, setNewMember] = useState<Omit<TeamMember, 'id' | 'createdAt'>>({
    name: '',
    kryptonId: '', // Added Krypton ID
    type: 'employee',
    usdcPayment: 0,
    tokenPayment: 0,
    schedule: 'monthly'
  });

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
              x: business.x || '',
              pitchVideo: business.pitch_video || ''
            });
            setFundraisingData({
              tokenName: business.token_name || '',
              price: business.price || 0,
              isMintingActive: business.is_minting_active || false
            });
            
            // Load team data if available
            if (business.team_data) {
              // Ensure all members have kryptonId
              const fixedTeamData = {
                ...business.team_data,
                members: (business.team_data.members || []).map((member: any) => ({
                  ...member,
                  kryptonId: member.kryptonId || '',
                })),
              };
              setTeamData(fixedTeamData);
            }
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

  const handleNewMemberChange = (field: keyof typeof newMember, value: string | number) => {
    setNewMember(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleAddMember = async () => {
    if (!newMember.name.trim()) {
      setSaveError('Please enter a member name');
      return;
    }

    if (!existingBusinessId) {
      setSaveError('Please save your business details first before adding team members');
      return;
    }

    setSaving(true);
    setSaveError(null);
    setSaveSuccess(null);

    try {
      const memberPayload = {
        name: newMember.name,
        kryptonId: newMember.kryptonId,
        type: newMember.type,
        usdcPayment: newMember.usdcPayment,
        tokenPayment: newMember.tokenPayment,
        schedule: newMember.schedule
      };

      const response = await api.post(
        `/api/v1/marketplace/business/${existingBusinessId}/team/member`,
        memberPayload
      );

      const savedMember: TeamMember = {
        ...response.data, // assuming API returns saved member with id and createdAt
      };

      setTeamData(prev => ({
        ...prev,
        members: [...prev.members, savedMember]
      }));

      // Reset form
      setNewMember({
        name: '',
        kryptonId: '',
        type: 'employee',
        usdcPayment: 0,
        tokenPayment: 0,
        schedule: 'monthly'
      });

      setShowAddMemberModal(false);
      setSaveSuccess('Team member added successfully!');
      setTimeout(() => setSaveSuccess(null), 3000);
    } catch (err: any) {
      console.error('Failed to add member:', err);
      setSaveError(err.response?.data?.detail || 'Failed to add member. Please try again.');
    } finally {
      setSaving(false);
    }
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
          x: businessData.x || undefined,
          pitch_video: businessData.pitchVideo || undefined
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
          pitch_video: businessData.pitchVideo || undefined,
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

      // Get user wallet address for token deployment
      const userData = JSON.parse(localStorage.getItem('userData') || '{}');
      const walletAddress = userData.wallet_address;

      if (!walletAddress) {
        throw new Error('Wallet address not found. Please ensure you have a connected wallet.');
      }

      // Prepare token deployment data according to ApeDeployTokenRequest schema
      const tokenDeploymentData = {
        contract_name: "SmartToken",
        name: businessData.name,
        symbol: fundraisingData.tokenName,
        initial_value: fundraisingData.price,
        initial_supply: 0, // Default initial supply
        owners: [walletAddress], // User's wallet address as owner
        business_id: existingBusinessId
      };

      await api.post('/api/v1/smarttoken/deploy_ape', tokenDeploymentData);

      setSaveSuccess('Fundraising settings saved successfully!');
      setTimeout(() => setSaveSuccess(null), 3000);
    } catch (err: any) {
      console.error('Failed to save fundraising settings:', err);
      setSaveError(err.response?.data?.detail || 'Failed to save fundraising settings. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveTeam = async () => {
    if (!existingBusinessId) {
      setSaveError('Please save your business details first before configuring team settings');
      return;
    }

    setSaving(true);
    setSaveError(null);
    setSaveSuccess(null);

    try {
      // Update marketplace item with team data
      const teamUpdate = {
        team_data: teamData
      };
      
      await api.put(`/api/v1/marketplace/business/${existingBusinessId}/team`, teamUpdate);
      
      setSaveSuccess('Team settings saved successfully!');
      setTimeout(() => setSaveSuccess(null), 3000);
    } catch (err: any) {
      console.error('Failed to save team settings:', err);
      setSaveError(err.response?.data?.detail || 'Failed to save team settings. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const handleSave = () => {
    if (activeTab === 'details') {
      handleSaveDetails();
    } else if (activeTab === 'fundraising') {
      handleSaveFundraising();
    } else if (activeTab === 'team') {
      handleSaveTeam();
    }
  };

  const getMembersByType = (type: 'employee' | 'intern' | 'vendor') => {
    return teamData.members.filter(member => member.type === type);
  };

  const getTypeColor = (type: 'employee' | 'intern' | 'vendor') => {
    switch (type) {
      case 'employee':
        return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'intern':
        return 'bg-green-500/20 text-green-400 border-green-500/30';
      case 'vendor':
        return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
      default:
        return 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30';
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
            onClick={() => setActiveTab('team')}
            className={`flex-1 flex items-center justify-center space-x-2 py-3 px-4 rounded-md transition-all ${
              activeTab === 'team'
                ? 'bg-cyan-500 text-white shadow-lg'
                : 'text-zinc-400 hover:text-white hover:bg-zinc-700/50'
            }`}
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
          <div className="bg-gradient-to-br from-zinc-900/80 via-zinc-800/60 to-cyan-900/40 backdrop-blur-2xl border border-cyan-400/10 rounded-3xl p-12 shadow-2xl mb-8 transition-all duration-300">
            <h2 className="text-3xl font-extrabold text-white tracking-tight drop-shadow-lg mb-10">Business Details</h2>
            <div className="space-y-8">
              <div>
                <label className="block text-base font-semibold text-zinc-200 mb-2">Business Name *</label>
                <input
                  type="text"
                  value={businessData.name}
                  onChange={(e) => handleBusinessDataChange('name', e.target.value)}
                  className="w-full px-5 py-4 bg-zinc-900/70 border border-zinc-600/40 rounded-xl text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-400/60 focus:border-transparent text-lg shadow-inner"
                  placeholder="Enter your business name"
                />
              </div>
              <div>
                <label className="block text-base font-semibold text-zinc-200 mb-2">Description *</label>
                <textarea
                  value={businessData.description}
                  onChange={(e) => handleBusinessDataChange('description', e.target.value)}
                  rows={4}
                  className="w-full px-5 py-4 bg-zinc-900/70 border border-zinc-600/40 rounded-xl text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-400/60 focus:border-transparent text-lg shadow-inner resize-none"
                  placeholder="Describe your business and what makes it unique"
                />
              </div>
              <div>
                <label className="block text-base font-semibold text-zinc-200 mb-2">Category *</label>
                <select
                  value={businessData.category}
                  onChange={(e) => handleBusinessDataChange('category', e.target.value)}
                  className="w-full px-5 py-4 bg-zinc-900/70 border border-zinc-600/40 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-cyan-400/60 focus:border-transparent text-lg shadow-inner"
                >
                  <option value="">Select a category</option>
                  {categories.map((category) => (
                    <option key={category} value={category}>{category}</option>
                  ))}
                </select>
              </div>
              {/* Move Pitch Video URL here */}
              <div>
                <label className="block text-base font-semibold text-zinc-200 mb-2">Pitch Video URL (YouTube)</label>
                <div className="relative">
                  <input
                    type="url"
                    value={businessData.pitchVideo}
                    onChange={(e) => handleBusinessDataChange('pitchVideo', e.target.value)}
                    className="w-full px-5 py-4 bg-zinc-900/70 border border-zinc-600/40 rounded-xl text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-400/60 focus:border-transparent text-lg shadow-inner"
                    placeholder="https://www.youtube.com/watch?v=..."
                  />
                  {businessData.pitchVideo && (
                    <ExternalLink className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-cyan-300" />
                  )}
                </div>
                <p className="text-zinc-400 text-sm mt-2">Add a YouTube video URL for your pitch video. This will be displayed to potential investors.</p>
              </div>
              {/* Social section */}
              <div className="mt-8">
                <h3 className="text-xl font-bold text-cyan-300 mb-6 tracking-tight">Social</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div>
                    <label className="block text-base font-semibold text-zinc-200 mb-2">LinkedIn URL</label>
                    <div className="relative">
                      <input
                        type="url"
                        value={businessData.linkedin}
                        onChange={(e) => handleBusinessDataChange('linkedin', e.target.value)}
                        className="w-full px-5 py-4 bg-zinc-900/70 border border-zinc-600/40 rounded-xl text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-400/60 focus:border-transparent text-lg shadow-inner"
                        placeholder="https://linkedin.com/company/..."
                      />
                      {businessData.linkedin && (
                        <ExternalLink className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-cyan-300" />
                      )}
                    </div>
                  </div>
                  <div>
                    <label className="block text-base font-semibold text-zinc-200 mb-2">YouTube URL</label>
                    <div className="relative">
                      <input
                        type="url"
                        value={businessData.youtube}
                        onChange={(e) => handleBusinessDataChange('youtube', e.target.value)}
                        className="w-full px-5 py-4 bg-zinc-900/70 border border-zinc-600/40 rounded-xl text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-400/60 focus:border-transparent text-lg shadow-inner"
                        placeholder="https://youtube.com/..."
                      />
                      {businessData.youtube && (
                        <ExternalLink className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-cyan-300" />
                      )}
                    </div>
                  </div>
                  <div>
                    <label className="block text-base font-semibold text-zinc-200 mb-2">X (Twitter) URL</label>
                    <div className="relative">
                      <input
                        type="url"
                        value={businessData.x}
                        onChange={(e) => handleBusinessDataChange('x', e.target.value)}
                        className="w-full px-5 py-4 bg-zinc-900/70 border border-zinc-600/40 rounded-xl text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-400/60 focus:border-transparent text-lg shadow-inner"
                        placeholder="https://x.com/..."
                      />
                      {businessData.x && (
                        <ExternalLink className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-cyan-300" />
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'fundraising' && (
          <div className="bg-gradient-to-br from-zinc-900/80 via-zinc-800/60 to-cyan-900/40 backdrop-blur-2xl border border-cyan-400/10 rounded-3xl p-12 shadow-2xl mb-8 transition-all duration-300">
            <h2 className="text-3xl font-extrabold text-white tracking-tight drop-shadow-lg mb-10">Fundraising Settings</h2>
            <div className="space-y-8">
              <div>
                <label className="block text-base font-semibold text-zinc-200 mb-2">Token Name *</label>
                <input
                  type="text"
                  value={fundraisingData.tokenName}
                  onChange={(e) => handleFundraisingDataChange('tokenName', e.target.value)}
                  className="w-full px-5 py-4 bg-zinc-900/70 border border-zinc-600/40 rounded-xl text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-400/60 focus:border-transparent text-lg shadow-inner"
                  placeholder="Enter your token name (e.g., MYTOKEN)"
                />
              </div>
              <div>
                <label className="block text-base font-semibold text-zinc-200 mb-2">Token Price (USDC) *</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={fundraisingData.price}
                  onChange={(e) => handleFundraisingDataChange('price', parseFloat(e.target.value) || 0)}
                  className="w-full px-5 py-4 bg-zinc-900/70 border border-zinc-600/40 rounded-xl text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-400/60 focus:border-transparent text-lg shadow-inner"
                  placeholder="0.00"
                />
              </div>
              <div className="flex items-center justify-between p-6 bg-zinc-900/60 rounded-2xl border border-cyan-400/10 shadow-inner">
                <div>
                  <h3 className="text-xl font-semibold text-white mb-1">Token Minting</h3>
                  <p className="text-zinc-400 text-base">
                    {fundraisingData.isMintingActive
                      ? 'Minting is currently active and investors can purchase tokens'
                      : 'Minting is paused and no new tokens can be purchased'
                    }
                  </p>
                </div>
                <button
                  onClick={() => handleFundraisingDataChange('isMintingActive', !fundraisingData.isMintingActive)}
                  className={`px-8 py-3 rounded-2xl font-semibold text-lg transition-all shadow-lg focus:outline-none focus:ring-2 focus:ring-cyan-400/60 border border-cyan-400/30
            ${fundraisingData.isMintingActive
              ? 'bg-gradient-to-r from-red-500 to-pink-600 hover:from-red-600 hover:to-pink-700 text-white'
              : 'bg-gradient-to-r from-green-500 to-cyan-600 hover:from-green-600 hover:to-cyan-700 text-white'
            }`}
        >
          {fundraisingData.isMintingActive ? 'Pause Minting' : 'Start Minting'}
        </button>
      </div>
      {/* Fundraising Summary */}
      {fundraisingData.tokenName && fundraisingData.price > 0 && (
        <div className="p-6 bg-gradient-to-r from-cyan-900/30 to-blue-900/30 border border-cyan-500/30 rounded-2xl shadow-inner">
          <h3 className="text-xl font-semibold text-white mb-4">Fundraising Summary</h3>
          <div className="grid grid-cols-2 gap-6">
            <div>
              <p className="text-zinc-400 text-base">Token Name</p>
              <p className="text-white font-bold text-lg">{fundraisingData.tokenName}</p>
            </div>
            <div>
              <p className="text-zinc-400 text-base">Token Price</p>
              <p className="text-white font-bold text-lg">${fundraisingData.price.toFixed(2)} USDC</p>
            </div>
            <div>
              <p className="text-zinc-400 text-base">Minting Status</p>
              <p className={`font-bold text-lg ${fundraisingData.isMintingActive ? 'text-green-400' : 'text-red-400'}`}>{fundraisingData.isMintingActive ? 'Active' : 'Paused'}</p>
            </div>
            <div>
              <p className="text-zinc-400 text-base">Marketplace Status</p>
              <p className="text-green-400 font-bold text-lg">Live</p>
            </div>
          </div>
        </div>
      )}
    </div>
  </div>
)}

        {activeTab === 'team' && (
          <div className="bg-gradient-to-br from-zinc-900/80 via-zinc-800/60 to-cyan-900/40 backdrop-blur-2xl border border-cyan-400/10 rounded-3xl p-12 shadow-2xl mb-8 transition-all duration-300">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-8 gap-4">
              <h2 className="text-3xl font-extrabold text-white tracking-tight drop-shadow-lg">Your Team</h2>
            </div>
            <div className="flex flex-row gap-4 mb-10">
              <button
                onClick={() => setShowAddMemberModal(true)}
                className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white rounded-2xl font-semibold text-lg shadow-lg hover:shadow-xl transition-all duration-200 transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-cyan-400/60 border border-cyan-400/30"
              >
                <UserPlus className="h-5 w-5 drop-shadow-[0_0_6px_rgba(34,211,238,0.7)]" />
                <span>Member</span>
              </button>
              <button
                className="flex items-center gap-2 px-6 py-3 bg-zinc-800/80 hover:bg-zinc-700/80 text-white rounded-2xl font-semibold text-lg shadow-md hover:shadow-lg transition-all duration-200 transform hover:scale-105 border border-zinc-600/40"
              >
                <History className="h-5 w-5 text-cyan-300 drop-shadow-[0_0_6px_rgba(34,211,238,0.4)]" />
                <span>Settlements</span>
              </button>
            </div>

            {/* Team Table */}
            <div className="space-y-6">
              {/* Employees */}
              <div>
                <h3 className="text-lg font-semibold text-white mb-4">Employees</h3>
                <div className="bg-zinc-900/50 rounded-lg overflow-hidden">
                  <table className="w-full">
                    <thead className="bg-zinc-800/50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-zinc-300 uppercase tracking-wider">Name</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-zinc-300 uppercase tracking-wider">Payments</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-zinc-300 uppercase tracking-wider">Schedule</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-700">
                      {getMembersByType('employee').length > 0 ? (
                        getMembersByType('employee').map((member) => (
                          <tr key={member.id} className="hover:bg-zinc-800/30">
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-white">{member.name}</td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <div className="space-y-1">
                                <div className="text-sm text-zinc-300">USDC: ${member.usdcPayment}</div>
                                <div className="text-sm text-zinc-300">{fundraisingData.tokenName}: {member.tokenPayment}</div>
                              </div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getTypeColor(member.type)}`}>
                                {member.schedule}
                              </span>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={3} className="px-6 py-4 text-center text-sm text-zinc-500">
                            No employees added yet
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Interns */}
              <div>
                <h3 className="text-lg font-semibold text-white mb-4">Interns</h3>
                <div className="bg-zinc-900/50 rounded-lg overflow-hidden">
                  <table className="w-full">
                    <thead className="bg-zinc-800/50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-zinc-300 uppercase tracking-wider">Name</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-zinc-300 uppercase tracking-wider">Payments</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-zinc-300 uppercase tracking-wider">Schedule</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-700">
                      {getMembersByType('intern').length > 0 ? (
                        getMembersByType('intern').map((member) => (
                          <tr key={member.id} className="hover:bg-zinc-800/30">
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-white">{member.name}</td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <div className="space-y-1">
                                <div className="text-sm text-zinc-300">USDC: ${member.usdcPayment}</div>
                                <div className="text-sm text-zinc-300">{fundraisingData.tokenName}: {member.tokenPayment}</div>
                              </div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getTypeColor(member.type)}`}>
                                {member.schedule}
                              </span>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={3} className="px-6 py-4 text-center text-sm text-zinc-500">
                            No interns added yet
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Vendors */}
              <div>
                <h3 className="text-lg font-semibold text-white mb-4">Vendors</h3>
                <div className="bg-zinc-900/50 rounded-lg overflow-hidden">
                  <table className="w-full">
                    <thead className="bg-zinc-800/50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-zinc-300 uppercase tracking-wider">Name</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-zinc-300 uppercase tracking-wider">Payments</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-zinc-300 uppercase tracking-wider">Schedule</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-700">
                      {getMembersByType('vendor').length > 0 ? (
                        getMembersByType('vendor').map((member) => (
                          <tr key={member.id} className="hover:bg-zinc-800/30">
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-white">{member.name}</td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <div className="space-y-1">
                                <div className="text-sm text-zinc-300">USDC: ${member.usdcPayment}</div>
                                <div className="text-sm text-zinc-300">{fundraisingData.tokenName}: {member.tokenPayment}</div>
                              </div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getTypeColor(member.type)}`}>
                                {member.schedule}
                              </span>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={3} className="px-6 py-4 text-center text-sm text-zinc-500">
                            No vendors added yet
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Add Member Modal */}
        {showAddMemberModal && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-2xl flex items-center justify-center z-50">
            <div className="bg-gradient-to-br from-zinc-900/90 via-zinc-800/80 to-cyan-900/60 border border-cyan-400/20 rounded-3xl p-10 w-full max-w-lg mx-4 shadow-2xl ring-2 ring-cyan-400/10">
              <h3 className="text-2xl font-extrabold text-white mb-6 tracking-tight drop-shadow-lg">Add Team Member</h3>
              <div className="space-y-6">
                <div>
                  <label className="block text-base font-semibold text-zinc-200 mb-2">Name *</label>
                  <input
                    type="text"
                    value={newMember.name}
                    onChange={(e) => handleNewMemberChange('name', e.target.value)}
                    className="w-full px-5 py-4 bg-zinc-900/70 border border-zinc-600/40 rounded-xl text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-400/60 focus:border-transparent text-lg shadow-inner"
                    placeholder="Enter member name"
                  />
                </div>
                <div>
                  <label className="block text-base font-semibold text-zinc-200 mb-2">Krypton ID</label>
                  <div className="flex items-center">
                    <span className="text-zinc-400 mr-2 text-lg">@</span>
                    <input
                      type="text"
                      value={newMember.kryptonId}
                      onChange={(e) => handleNewMemberChange('kryptonId', e.target.value)}
                      className="flex-1 px-5 py-4 bg-zinc-900/70 border border-zinc-600/40 rounded-xl text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-400/60 focus:border-transparent text-lg shadow-inner"
                      placeholder="kryptonid"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-base font-semibold text-zinc-200 mb-2">Type *</label>
                  <select
                    value={newMember.type}
                    onChange={(e) => handleNewMemberChange('type', e.target.value as 'employee' | 'intern' | 'vendor')}
                    className="w-full px-5 py-4 bg-zinc-900/70 border border-zinc-600/40 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-cyan-400/60 focus:border-transparent text-lg shadow-inner"
                  >
                    <option value="employee">Employee</option>
                    <option value="intern">Intern</option>
                    <option value="vendor">Vendor</option>
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-base font-semibold text-zinc-200 mb-2">USDC Payment</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={newMember.usdcPayment === 0 ? '' : String(newMember.usdcPayment)}
                      onChange={(e) => {
                        const value = e.target.value.replace(/^0+(?=\d)/, '');
                        handleNewMemberChange('usdcPayment', value === '' ? 0 : parseFloat(value));
                      }}
                      className="w-full px-5 py-4 bg-zinc-900/70 border border-zinc-600/40 rounded-xl text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-400/60 focus:border-transparent text-lg shadow-inner"
                      placeholder="0.00"
                    />
                  </div>
                  <div>
                    <label className="block text-base font-semibold text-zinc-200 mb-2">{fundraisingData.tokenName || 'Token'} Payment</label>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={newMember.tokenPayment === 0 ? '' : String(newMember.tokenPayment)}
                      onChange={(e) => {
                        const value = e.target.value.replace(/^0+(?=\d)/, '');
                        handleNewMemberChange('tokenPayment', value === '' ? 0 : parseFloat(value));
                      }}
                      className="w-full px-5 py-4 bg-zinc-900/70 border border-zinc-600/40 rounded-xl text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-400/60 focus:border-transparent text-lg shadow-inner"
                      placeholder="0.00"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-base font-semibold text-zinc-200 mb-2">Schedule *</label>
                  <select
                    value={newMember.schedule}
                    onChange={(e) => handleNewMemberChange('schedule', e.target.value as 'monthly' | 'weekly' | 'custom')}
                    className="w-full px-5 py-4 bg-zinc-900/70 border border-zinc-600/40 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-cyan-400/60 focus:border-transparent text-lg shadow-inner"
                  >
                    <option value="monthly">Monthly</option>
                    <option value="weekly">Weekly</option>
                    <option value="custom">Custom</option>
                  </select>
                </div>
              </div>
              <div className="flex space-x-4 mt-8">
                <button
                  onClick={() => setShowAddMemberModal(false)}
                  className="flex-1 px-6 py-3 bg-zinc-700 hover:bg-zinc-600 text-white rounded-2xl font-semibold text-lg shadow-md transition-all duration-200"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddMember}
                  className="flex-1 px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white rounded-2xl font-semibold text-lg shadow-lg hover:shadow-xl transition-all duration-200 transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-cyan-400/60 border border-cyan-400/30"
                >
                  Confirm
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Save Button */}
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
      </div>
    </div>
  );
}