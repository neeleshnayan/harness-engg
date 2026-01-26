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
  History,
  UserPlus,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Zap,
} from "lucide-react";
import { MarketplaceService } from "@/lib/marketplace";
import api, { getTokenInfo } from "@/lib/api";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Area, CartesianGrid, XAxis, YAxis, ComposedChart, Line } from "recharts";
import {
  ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart"

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
  schedule: 'monthly' | 'bi-weekly' | 'weekly' | 'custom';
  createdAt: string;
}

interface TeamData {
  members: TeamMember[];
}

const chartConfig = {
  raised: {
    label: "Log10 (Funds Raised in $)",
    color: "#98b8eb",
  },
  price: {
    label: "Token Price ($)",
    color: "#98b8eb",
  },
  minted: {
    label: "Tokens Minted",
    color: "#98b8eb",
  },
} satisfies ChartConfig;

export default function ManageBusinessPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<'details' | 'fundraising' | 'team'>('details');
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [tranchingDetails, setTranchingDetails] = useState<Array<Object>>([]);
  const [priceInputValue, setPriceInputValue] = useState<string>('0.5');

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
    price: 0.5,
    isMintingActive: false
  });

  const [teamData, setTeamData] = useState<TeamData>({
    members: []
  });

  const [existingBusinessId, setExistingBusinessId] = useState<string | null>(null);
  const [hasExistingAddress, setHasExistingAddress] = useState<boolean>(false);
  const [tokenAddress, setTokenAddress] = useState<string | null>(null);
  const [tokenInfo, setTokenInfo] = useState<any>(null);
  const [tokenInfoLoading, setTokenInfoLoading] = useState<boolean>(false);
  const [showAddMemberModal, setShowAddMemberModal] = useState(false);
  const [showSavingFundraisingModal, setShowSavingFundraisingModal] = useState(false);
  const [showTokenDeploymentModal, setShowTokenDeploymentModal] = useState(false);
  const [showSalaryContractDeploymentModal, setShowSalaryContractDeploymentModal] = useState(false);
  const [showAddingEmployeeModal, setShowAddingEmployeeModal] = useState(false);
  const [showForcePayoutModal, setShowForcePayoutModal] = useState(false);
  const [salaryContractAddress, setSalaryContractAddress] = useState<string | null>(null);
  const [showSettlementsModal, setShowSettlementsModal] = useState(false);
  const [settlementsData, setSettlementsData] = useState<any[]>([]);
  const [settlementsLoading, setSettlementsLoading] = useState(false);
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
            const price = business.price || 0.5;
            setFundraisingData({
              tokenName: business.token_name || '',
              price: price,
              isMintingActive: business.is_minting_active || false
            });
            setPriceInputValue(price.toString());

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

              // Try to load existing salary contract if team members exist
              if (business.team_data.members && business.team_data.members.length > 0) {
                try {
                  const salaryContractResponse = await api.get(`/api/v1/salary_contract/contract_by_company/${business.id}`);
                  if (salaryContractResponse.data && salaryContractResponse.data.address) {
                    setSalaryContractAddress(salaryContractResponse.data.address);
                  }
                } catch (error) {
                  console.log('No existing salary contract found, will deploy new one when adding first member');
                }
              }
            }

            // fetch token address details
            try {
              const response = await api.get('/api/v1/smarttoken/token_address/' + business.id);
              setHasExistingAddress(response.data.has_address);
              if (response.data.has_address && response.data.address) {
                setTokenAddress(response.data.address);
                // Fetch token info
                try {
                  setTokenInfoLoading(true);
                  const tokenInfoData = await getTokenInfo(response.data.address);
                  setTokenInfo(tokenInfoData);
                } catch (tokenErr) {
                  console.error('Failed to fetch token info:', tokenErr);
                } finally {
                  setTokenInfoLoading(false);
                }
              }
            } catch (err) {
              console.error('Failed to fetch existing address:', err);
            }
          }
        }
      } catch (err) {
        console.error('Failed to fetch existing business:', err);
        // Don't show error for this as it's expected for new businesses
      }
    };

    const initializeData = async () => {
      await Promise.all([fetchCategories(), fetchExistingBusiness(), fetchTranchingDetails(fundraisingData.price)]);
      setLoading(false);
    };

    initializeData();
  }, [router]);

  const fetchTranchingDetails = async (initial_price: number) => {
    try {
      const response = await api.post('/api/v1/smarttoken/tranching_details_for_demo', {
        amount: 1e6,
        initial_value: initial_price,
      });

      var tranches = [];
      for (let tranche of response.data.minting_details.tranche_breakdown) {
        tranches.push({
          minted: tranche.current_supply,
          raised: tranche.total_raised,
          price: Math.log10(tranche.price),
        });
      }

      setTranchingDetails(tranches);
    } catch (err) {
      console.error('Failed to fetch tranching details:', err);
    }
  }

  const fetchTokenInfo = async (address: string) => {
    if (!address) return;

    setTokenInfoLoading(true);
    try {
      const tokenInfoData = await getTokenInfo(address);
      setTokenInfo(tokenInfoData);
    } catch (err) {
      console.error('Failed to fetch token info:', err);
    } finally {
      setTokenInfoLoading(false);
    }
  }

  const fetchSettlements = async (contractAddress: string) => {
    // Salary contract settlements are temporarily disabled during backend migration
    // See SMARTTOKEN_MIGRATION.md for details
    alert('Salary management is coming soon! This feature is currently being upgraded.');
    setSettlementsData([]);
    setSettlementsLoading(false);
  }

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

    if (!tokenAddress) {
      setSaveError('Please deploy your smart token from the Fundraising tab before adding team members');
      return;
    }

    if (!newMember.kryptonId.trim()) {
      setSaveError('Please enter a Krypton ID for the team member');
      return;
    }

    setSaving(true);
    setSaveError(null);
    setSaveSuccess(null);

    try {
      // First, save the member to the marketplace
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
        ...response.data,
      };

      // Salary contract operations are temporarily disabled during backend migration
      // See SMARTTOKEN_MIGRATION.md for details
      // This includes: deploy, add_employee functionality
      alert('Salary management is coming soon! This feature is currently being upgraded.');
      setShowAddMemberModal(true);
      return;

      // Add member to team data
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
    setShowSavingFundraisingModal(true);
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

      if (!hasExistingAddress) {
        // Token deployment via deploy_ape is temporarily disabled during backend migration
        // See SMARTTOKEN_MIGRATION.md for details
        setShowSavingFundraisingModal(false);
        alert('Token deployment is coming soon! This feature is currently being upgraded.');
        throw new Error('Token deployment coming soon');
      }

      setSaveSuccess('Fundraising settings saved successfully!');
      setTimeout(() => setSaveSuccess(null), 3000);

      // Refresh token info if we have a token address
      if (tokenAddress) {
        await fetchTokenInfo(tokenAddress);
      }
    } catch (err: any) {
      console.error('Failed to save fundraising settings:', err);
      setSaveError(err.response?.data?.detail || 'Failed to save fundraising settings. Please try again.');
    } finally {
      setSaving(false);
      setShowSavingFundraisingModal(false);
      setShowTokenDeploymentModal(false);
    }
  };

  const handleSaveTeam = async () => {
    if (!existingBusinessId) {
      setSaveError('Please save your business details first before configuring team settings');
      return;
    }

    if (!tokenAddress) {
      setSaveError('Please deploy your smart token from the Fundraising tab before configuring team settings');
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

  const handleForcePayouts = async () => {
    // Force payout is temporarily disabled during backend migration
    // See SMARTTOKEN_MIGRATION.md for details
    alert('Salary management is coming soon! This feature is currently being upgraded.');
  }

  const handleSettlementsClick = async () => {
    if (!salaryContractAddress) {
      setSaveError('No salary contract found. Please add a team member first.');
      return;
    }

    setShowSettlementsModal(true);
    await fetchSettlements(salaryContractAddress);
  }

  const getEmployeeWalletAddress = async (kryptonId: string): Promise<string> => {
    try {
      // First get user by username
      const userResponse = await api.get(`/api/v1/resolve_username/${kryptonId}`);
      if (userResponse.data && userResponse.data.wallet_address) {
        return userResponse.data.wallet_address;
      }

      throw new Error(`No wallet found for user @${kryptonId}`);
    } catch (err: any) {
      console.error(`Failed to get wallet address for @${kryptonId}:`, err);
      throw new Error(`Failed to get wallet address for @${kryptonId}. Please ensure the user exists and has a wallet.`);
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
      <div className="min-h-screen w-full flex flex-col items-center justify-center bg-[#001C1B] p-8">
        <Loader2 className="h-12 w-12 text-cyan-400 animate-spin mb-4" />
        <p className="text-zinc-400 text-lg">Loading business management...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen w-full bg-[#001C1B]">
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
                  {/* {businessData.pitchVideo && (
                    <ExternalLink className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-cyan-300" />
                  )} */}
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
                      {/* {businessData.linkedin && (
                        <ExternalLink className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-cyan-300" />
                      )} */}
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
                      {/* {businessData.youtube && (
                        <ExternalLink className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-cyan-300" />
                      )} */}
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
                      {/* {businessData.x && (
                        <ExternalLink className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-cyan-300" />
                      )} */}
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
                  id="token-name"
                  type="text"
                  value={fundraisingData.tokenName}
                  onChange={(e) => handleFundraisingDataChange('tokenName', e.target.value)}
                  className="w-full px-5 py-4 bg-zinc-900/70 border border-zinc-600/40 rounded-xl text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-400/60 focus:border-transparent text-lg shadow-inner"
                  placeholder="Enter your token name (e.g., MYTOKEN)"
                  readOnly={hasExistingAddress}
                />
              </div>
              <div>
                <label className="block text-base font-semibold text-zinc-200 mb-2">Token Price (USDC) *</label>
                <div className="flex gap-3 items-center">
                  <input
                    id="token-price"
                    type="number"
                    step="0.01"
                    min="0"
                    value={priceInputValue}
                    onChange={(e) => {
                      const value = e.target.value;
                      setPriceInputValue(value);

                      // Update the actual price value
                      if (value === '' || value === '.') {
                        handleFundraisingDataChange('price', 0);
                      } else {
                        const parsed = parseFloat(value);
                        if (!isNaN(parsed) && parsed >= 0) {
                          handleFundraisingDataChange('price', parsed);
                        }
                      }
                    }}
                    className="w-full px-4 py-3 bg-zinc-900/70 border border-zinc-600/40 rounded-xl text-white placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-cyan-400/60 focus:border-transparent text-lg shadow-inner"
                    placeholder="0.00"
                    readOnly={hasExistingAddress}
                  />
                  <button
                    onClick={() => {
                      const price = parseFloat(priceInputValue) || 0;
                      if (price > 0) {
                        fetchTranchingDetails(price);
                      }
                    }}
                    disabled={!priceInputValue || parseFloat(priceInputValue) <= 0}
                    className="px-4 py-3 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-700 hover:to-blue-700 disabled:from-zinc-600 disabled:to-zinc-700 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all shadow-lg focus:outline-none focus:ring-2 focus:ring-cyan-400/60 text-base whitespace-nowrap"
                  >
                    Recalculate
                  </button>
                </div>
              </div>
              <section id="bonded-curve" >
                <Card className="bg-zinc-800/50 backdrop-blur-sm border border-zinc-700/50 shadow-2xl rounded-3xl">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-2xl flex items-center gap-2 text-white">Bonding Curve</CardTitle>
                    <CardDescription>
                      Illustrative bonding curve for given initial token price
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <ChartContainer config={chartConfig}>
                      <ComposedChart
                        accessibilityLayer
                        data={tranchingDetails}
                        margin={{
                          left: 12,
                          right: 12,
                          top: 12,
                          bottom: 20,
                        }}
                      >
                        <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.1)"/>
                        <XAxis
                          dataKey="minted"
                          tickLine={true}
                          axisLine={false}
                          tickMargin={8}
                          type="number"
                          domain={['dataMin', 'dataMax']}
                          ticks={[0, 100000, 200000, 300000, 400000, 500000, 600000, 700000, 800000, 900000, 1000000]}
                          tickFormatter={(value) => ((value / 1000000) * 100).toFixed(0) + '%'}
                          label={{ value: 'Tokens Minted', angle: 0, position: 'insideBottom', offset: -15, style: { textAnchor: 'middle', fill: '#98b8eb' } }}
                        />
                        <YAxis
                          yAxisId="left"
                          tickLine={true}
                          axisLine={false}
                          tickMargin={8}
                          orientation="left"
                          tickFormatter={(value) => (value / 1000000).toString()}
                          label={{ value: 'Funds Raised ($M)', angle: -90, position: 'insideLeft', style: { textAnchor: 'middle', fill: '#98b8eb' } }}
                        />
                        <YAxis
                          yAxisId="right"
                          tickLine={true}
                          axisLine={false}
                          tickMargin={8}
                          orientation="right"
                          tickFormatter={(value) => (10 ** value).toString()}
                          label={{ value: 'Token Price ($)', angle: 90, position: 'insideRight', style: { textAnchor: 'middle', fill: '#98b8eb' } }}
                        />
                        <ChartTooltip
                          cursor={true}
                          content={({ active, payload, label }) => {
                            if (!active || !payload?.length) return null;

                            const mintedValue = payload[0]?.payload?.minted;
                            const mintedPercentage = mintedValue ? ((mintedValue / 1000000) * 100).toFixed(1) : '0';

                            return (
                              <div className="bg-zinc-900/90 backdrop-blur-sm border border-zinc-700/50 rounded-lg p-3 shadow-xl min-w-[12rem]">
                                <div className="font-medium text-white mb-2 border-b border-zinc-600 pb-2">
                                  Bonding Curve Data
                                </div>
                                <div className="space-y-2">
                                  <div className="flex items-center gap-2">
                                    <div className="w-3 h-3 rounded-full bg-green-400"></div>
                                    <span className="text-zinc-300">Funds Raised ($):</span>
                                    <span className="text-white font-mono ml-auto">{typeof payload[0]?.value === 'number' ? payload[0].value.toFixed(3) : payload[0]?.value}</span>
                                  </div>
                                  <div className="flex items-center gap-2">
                                    <div className="w-3 h-3 rounded-full bg-blue-400"></div>
                                    <span className="text-zinc-300">Token Price ($):</span>
                                    <span className="text-white font-mono ml-auto">{typeof payload[1]?.value === 'number' ? (10 ** payload[1].value).toFixed(2) : payload[1]?.value}</span>
                                  </div>
                                  <div className="flex items-center gap-2 pt-2 border-t border-zinc-600">
                                    <span className="text-zinc-300">Tokens Minted:</span>
                                    <span className="text-white font-mono ml-auto">{mintedPercentage}%</span>
                                  </div>
                                </div>
                              </div>
                            );
                          }}
                        />
                        <Area
                          yAxisId="left"
                          dataKey="raised"
                          type="natural"
                          fill="rgba(120, 241, 150, 0.4)"
                          stroke="#78f196"
                          strokeWidth={2}
                        />
                        <Area
                          yAxisId="right"
                          dataKey="price"
                          type="natural"
                          fill="rgba(120, 241, 150, 0.0)"
                          stroke="#98b8eb"
                          strokeWidth={3}
                          // dot={{ r: 4, fill: "#98b8eb" }}
                        />
                      </ComposedChart>
                    </ChartContainer>
                  </CardContent>
                </Card>
              </section>
              <div className=" items-center justify-between p-6 bg-zinc-900/60 rounded-2xl border border-cyan-400/10 shadow-inner">
                <div>
                  <h3 className="text-xl font-semibold text-white mb-1">Token Minting</h3>
                  <p className="text-zinc-400 text-base">
                    {fundraisingData.isMintingActive
                      ? 'Minting is currently active and investors can purchase tokens'
                      : 'Minting is paused and no new tokens can be purchased'
                    }
                  </p>
                </div>
                <br/>
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
        <div className="p-4 sm:p-6 bg-gradient-to-r from-cyan-900/30 to-blue-900/30 border border-cyan-500/30 rounded-2xl shadow-inner">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg sm:text-xl font-semibold text-white">Fundraising Summary</h3>
            {tokenAddress && (
              tokenInfoLoading ? (
                <Loader2 className="h-6 w-6 text-cyan-400 animate-spin" />
              ) : (
                <button
                  onClick={() => fetchTokenInfo(tokenAddress)}
                  className="p-2 text-cyan-400 hover:text-cyan-300 hover:bg-cyan-400/10 rounded-lg transition-all duration-200 active:scale-95"
                  title="Refresh token info"
                >
                  <RefreshCw className="h-4 w-4" />
                </button>
              )
            )}
          </div>
          <div className={`grid gap-4 sm:gap-6 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`}>
            <div>
              <p className="text-zinc-400 text-sm sm:text-base">Token Name</p>
              <p className="text-white font-bold text-base sm:text-lg">{fundraisingData.tokenName}</p>
            </div>
            <div>
              <p className="text-zinc-400 text-sm sm:text-base">Token Price</p>
              <div className="flex items-center gap-2">
                <p className="text-white font-bold text-base sm:text-lg">
                  ${tokenInfo && tokenInfo.price ? Number(tokenInfo.price).toFixed(2) : fundraisingData.price.toFixed(2)} USDC
                </p>
                {tokenAddress && (
                  tokenInfoLoading ? (
                    <div className="h-4 w-4 bg-zinc-700/50 rounded animate-pulse"></div>
                  ) : tokenInfo && tokenInfo.initial_price ? (
                    <div className="flex items-center gap-1">
                      {(tokenInfo.price || fundraisingData.price) > tokenInfo.initial_price ? (
                        <TrendingUp className="h-4 w-4 text-green-400" />
                      ) : (tokenInfo.price || fundraisingData.price) < tokenInfo.initial_price ? (
                        <TrendingDown className="h-4 w-4 text-red-400" />
                      ) : null}
                      <span className={`text-xs font-medium ${
                        (tokenInfo.price || fundraisingData.price) > tokenInfo.initial_price
                          ? 'text-green-400'
                          : (tokenInfo.price || fundraisingData.price) < tokenInfo.initial_price
                          ? 'text-red-400'
                          : 'text-zinc-400'
                      }`}>
                        {tokenInfo.initial_price > 0
                          ? `${(((tokenInfo.price || fundraisingData.price) - tokenInfo.initial_price) / tokenInfo.initial_price * 100).toFixed(1)}%`
                          : '0.0%'
                        }
                      </span>
                    </div>
                  ) : null
                )}
              </div>
            </div>
            <div>
              <p className="text-zinc-400 text-sm sm:text-base">Minting Status</p>
              <p className={`font-bold text-base sm:text-lg ${fundraisingData.isMintingActive ? 'text-green-400' : 'text-red-400'}`}>{fundraisingData.isMintingActive ? 'Active' : 'Paused'}</p>
            </div>
            {tokenAddress && (
              <>
                <div>
                  <p className="text-zinc-400 text-sm sm:text-base">Total Raised</p>
                  {tokenInfoLoading ? (
                    <div className="h-6 bg-zinc-700/50 rounded animate-pulse"></div>
                  ) : tokenInfo ? (
                    <p className="text-white font-bold text-base sm:text-lg">
                      ${tokenInfo.total_raised ? Number(tokenInfo.total_raised).toFixed(2) : '0.00'} USDC
                    </p>
                  ) : (
                    <p className="text-zinc-500 text-sm">Not available</p>
                  )}
                </div>
                <div>
                  <p className="text-zinc-400 text-sm sm:text-base">Number of Investors</p>
                  {tokenInfoLoading ? (
                    <div className="h-6 bg-zinc-700/50 rounded animate-pulse"></div>
                  ) : tokenInfo ? (
                    <p className="text-white font-bold text-base sm:text-lg">
                      {tokenInfo.holders ? Object.keys(tokenInfo.holders).length : 0}
                    </p>
                  ) : (
                    <p className="text-zinc-500 text-sm">Not available</p>
                  )}
                </div>
              </>
            )}
            <div>
              <p className="text-zinc-400 text-sm sm:text-base">Marketplace Status</p>
              <p className="text-green-400 font-bold text-base sm:text-lg">Live</p>
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
              {salaryContractAddress && (
                <div className="text-sm text-zinc-400 bg-zinc-800/50 px-3 py-2 rounded-full">
                  Salary Contract: {salaryContractAddress.slice(0, 6)}...{salaryContractAddress.slice(-4)}
                </div>
              )}
            </div>
            <div className="flex flex-col sm:flex-row gap-4 mb-10">
              <button
                onClick={() => setShowAddMemberModal(true)}
                disabled={!tokenAddress}
                className={`flex items-center justify-center gap-2 px-6 py-3 rounded-2xl font-semibold text-lg shadow-lg transition-all duration-200 transform focus:outline-none focus:ring-2 focus:ring-cyan-400/60 border ${
                  tokenAddress
                    ? 'bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white hover:shadow-xl hover:scale-105 border-cyan-400/30'
                    : 'bg-zinc-600/80 text-zinc-400 cursor-not-allowed border-zinc-600/40'
                }`}
                title={!tokenAddress ? "Deploy your smart token first" : "Add a new team member"}
              >
                <UserPlus className="h-5 w-5 drop-shadow-[0_0_6px_rgba(34,211,238,0.7)]" />
                <span>Add Member</span>
              </button>
              <button
                onClick={handleSettlementsClick}
                className="flex items-center justify-center gap-2 px-6 py-3 rounded-2xl font-semibold text-lg shadow-md transition-all duration-200 transform border bg-zinc-800/80 hover:bg-zinc-700/80 text-white hover:shadow-lg hover:scale-105 border-zinc-600/40"
                title="View settlement history"
              >
                <History className="h-5 w-5 text-cyan-300 drop-shadow-[0_0_6px_rgba(34,211,238,0.4)]" />
                <span>Settlements</span>
              </button>
              <button
                onClick={handleForcePayouts}
                disabled={!salaryContractAddress || !tokenAddress}
                className="flex items-center justify-center gap-2 px-6 py-3 bg-gradient-to-r from-orange-500 to-red-600 hover:from-orange-600 hover:to-red-700 disabled:from-zinc-600 disabled:to-zinc-700 text-white rounded-2xl font-semibold text-lg shadow-md hover:shadow-lg transition-all duration-200 transform hover:scale-105 border border-orange-400/30 disabled:border-zinc-600/40 disabled:cursor-not-allowed"
                title={!tokenAddress ? "Deploy your smart token first" : !salaryContractAddress ? "Add a team member first" : "Execute force payouts for all employees"}
              >
                <Zap className="h-5 w-5 drop-shadow-[0_0_6px_rgba(255,165,0,0.7)]" />
                <span>Force Payouts</span>
              </button>
            </div>

            {/* Token Address Required Message */}
            {!tokenAddress && (
              <div className="mb-6 p-4 bg-gradient-to-r from-amber-900/30 to-orange-900/30 border border-amber-500/30 rounded-xl">
                <div className="flex items-center gap-3">
                  <AlertCircle className="h-5 w-5 text-amber-400" />
                  <div>
                    <p className="text-amber-200 font-medium">Smart Token Required</p>
                    <p className="text-amber-300 text-sm">
                      You need to deploy your smart token from the Fundraising tab before you can add team members or configure team settings.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Team Members - Mobile Friendly Cards */}
            <div className="space-y-6">
              {/* Employees */}
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-white">Employees</h3>
                  <span className="text-sm text-zinc-400 bg-zinc-800/50 px-3 py-1 rounded-full">
                    {getMembersByType('employee').length} member{getMembersByType('employee').length !== 1 ? 's' : ''}
                  </span>
                </div>
                {getMembersByType('employee').length > 0 ? (
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {getMembersByType('employee').map((member) => (
                      <div key={member.id} className="bg-zinc-900/50 rounded-xl p-4 border border-zinc-700/30 hover:border-cyan-400/30 transition-all duration-200 hover:shadow-lg hover:shadow-cyan-400/10 group">
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex-1 min-w-0">
                            <h4 className="text-white font-semibold text-base truncate">{member.name}</h4>
                            {member.kryptonId && (
                              <p className="text-zinc-400 text-sm truncate">@{member.kryptonId}</p>
                            )}
                          </div>
                          <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ml-2 flex-shrink-0 ${getTypeColor(member.type)}`}>
                            {member.schedule}
                          </span>
                        </div>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-zinc-400 text-sm">USDC Payment:</span>
                            <span className="text-white font-medium">${member.usdcPayment}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-zinc-400 text-sm">{fundraisingData.tokenName} Payment:</span>
                            <span className="text-white font-medium">{member.tokenPayment}</span>
                          </div>
                        </div>
                        <div className="mt-4 pt-3 border-t border-zinc-700/30 flex items-center justify-between">
                          <span className="text-xs text-zinc-500 capitalize">{member.type}</span>
                          <button className="text-cyan-400 hover:text-cyan-300 text-sm font-medium opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                            Edit
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="bg-zinc-900/30 rounded-xl p-8 text-center border-2 border-dashed border-zinc-700/50">
                    <div className="text-zinc-500 mb-2">
                      <UserPlus className="h-8 w-8 mx-auto mb-3 opacity-50" />
                    </div>
                    <p className="text-zinc-400 text-sm">No employees added yet</p>
                    <p className="text-zinc-500 text-xs mt-1">Click "Add Member" to get started</p>
                  </div>
                )}
              </div>

              {/* Interns */}
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-white">Interns</h3>
                  <span className="text-sm text-zinc-400 bg-zinc-800/50 px-3 py-1 rounded-full">
                    {getMembersByType('intern').length} member{getMembersByType('intern').length !== 1 ? 's' : ''}
                  </span>
                </div>
                {getMembersByType('intern').length > 0 ? (
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {getMembersByType('intern').map((member) => (
                      <div key={member.id} className="bg-zinc-900/50 rounded-xl p-4 border border-zinc-700/30 hover:border-cyan-400/30 transition-all duration-200 hover:shadow-lg hover:shadow-cyan-400/10 group">
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex-1 min-w-0">
                            <h4 className="text-white font-semibold text-base truncate">{member.name}</h4>
                            {member.kryptonId && (
                              <p className="text-zinc-400 text-sm truncate">@{member.kryptonId}</p>
                            )}
                          </div>
                          <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ml-2 flex-shrink-0 ${getTypeColor(member.type)}`}>
                            {member.schedule}
                          </span>
                        </div>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-zinc-400 text-sm">USDC Payment:</span>
                            <span className="text-white font-medium">${member.usdcPayment}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-zinc-400 text-sm">{fundraisingData.tokenName} Payment:</span>
                            <span className="text-white font-medium">{member.tokenPayment}</span>
                          </div>
                        </div>
                        <div className="mt-4 pt-3 border-t border-zinc-700/30 flex items-center justify-between">
                          <span className="text-xs text-zinc-500 capitalize">{member.type}</span>
                          <button className="text-cyan-400 hover:text-cyan-300 text-sm font-medium opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                            Edit
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="bg-zinc-900/30 rounded-xl p-8 text-center border-2 border-dashed border-zinc-700/50">
                    <div className="text-zinc-500 mb-2">
                      <UserPlus className="h-8 w-8 mx-auto mb-3 opacity-50" />
                    </div>
                    <p className="text-zinc-400 text-sm">No interns added yet</p>
                    <p className="text-zinc-500 text-xs mt-1">Click "Add Member" to get started</p>
                  </div>
                )}
              </div>

              {/* Vendors */}
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-white">Vendors</h3>
                  <span className="text-sm text-zinc-400 bg-zinc-800/50 px-3 py-1 rounded-full">
                    {getMembersByType('vendor').length} member{getMembersByType('vendor').length !== 1 ? 's' : ''}
                  </span>
                </div>
                {getMembersByType('vendor').length > 0 ? (
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {getMembersByType('vendor').map((member) => (
                      <div key={member.id} className="bg-zinc-900/50 rounded-xl p-4 border border-zinc-700/30 hover:border-cyan-400/30 transition-all duration-200 hover:shadow-lg hover:shadow-cyan-400/10 group">
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex-1 min-w-0">
                            <h4 className="text-white font-semibold text-base truncate">{member.name}</h4>
                            {member.kryptonId && (
                              <p className="text-zinc-400 text-sm truncate">@{member.kryptonId}</p>
                            )}
                          </div>
                          <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ml-2 flex-shrink-0 ${getTypeColor(member.type)}`}>
                            {member.schedule}
                          </span>
                        </div>
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <span className="text-zinc-400 text-sm">USDC Payment:</span>
                            <span className="text-white font-medium">${member.usdcPayment}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-zinc-400 text-sm">{fundraisingData.tokenName} Payment:</span>
                            <span className="text-white font-medium">{member.tokenPayment}</span>
                          </div>
                        </div>
                        <div className="mt-4 pt-3 border-t border-zinc-700/30 flex items-center justify-between">
                          <span className="text-xs text-zinc-500 capitalize">{member.type}</span>
                          <button className="text-cyan-400 hover:text-cyan-300 text-sm font-medium opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                            Edit
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="bg-zinc-900/30 rounded-xl p-8 text-center border-2 border-dashed border-zinc-700/50">
                    <div className="text-zinc-500 mb-2">
                      <UserPlus className="h-8 w-8 mx-auto mb-3 opacity-50" />
                    </div>
                    <p className="text-zinc-400 text-sm">No vendors added yet</p>
                    <p className="text-zinc-500 text-xs mt-1">Click "Add Member" to get started</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Saving Fundraising Loading Modal */}
        {showSavingFundraisingModal && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-2xl flex items-center justify-center z-50">
            <div className="bg-gradient-to-br from-zinc-900/90 via-zinc-800/80 to-cyan-900/60 border border-cyan-400/20 rounded-3xl p-10 w-full max-w-md mx-4 shadow-2xl ring-2 ring-cyan-400/10">
              <div className="flex flex-col items-center space-y-6">
                <div className="relative">
                  <Loader2 className="h-16 w-16 text-cyan-400 animate-spin" />
                  <div className="absolute inset-0 bg-cyan-400/20 rounded-full animate-pulse"></div>
                </div>
                <div className="text-center">
                  <h3 className="text-2xl font-extrabold text-white mb-2 tracking-tight drop-shadow-lg">
                    Saving Fundraising Settings
                  </h3>
                  <p className="text-zinc-300 text-lg">
                    Updating your fundraising configuration...
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Token Deployment Loading Modal */}
        {showTokenDeploymentModal && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-2xl flex items-center justify-center z-50">
            <div className="bg-gradient-to-br from-zinc-900/90 via-zinc-800/80 to-cyan-900/60 border border-cyan-400/20 rounded-3xl p-10 w-full max-w-md mx-4 shadow-2xl ring-2 ring-cyan-400/10">
              <div className="flex flex-col items-center space-y-6">
                <div className="relative">
                  <Loader2 className="h-16 w-16 text-cyan-400 animate-spin" />
                  <div className="absolute inset-0 bg-cyan-400/20 rounded-full animate-pulse"></div>
                </div>
                <div className="text-center">
                  <h3 className="text-2xl font-extrabold text-white mb-2 tracking-tight drop-shadow-lg">
                    Deploying Smart Token
                  </h3>
                  <p className="text-zinc-300 text-lg">
                    Creating your token contract on the blockchain...
                  </p>
                  <p className="text-zinc-400 text-sm mt-2">
                    This may take a few moments
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Salary Contract Deployment Loading Modal */}
        {showSalaryContractDeploymentModal && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-2xl flex items-center justify-center z-50">
            <div className="bg-gradient-to-br from-zinc-900/90 via-zinc-800/80 to-cyan-900/60 border border-cyan-400/20 rounded-3xl p-10 w-full max-w-md mx-4 shadow-2xl ring-2 ring-cyan-400/10">
              <div className="flex flex-col items-center space-y-6">
                <div className="relative">
                  <Loader2 className="h-16 w-16 text-cyan-400 animate-spin" />
                  <div className="absolute inset-0 bg-cyan-400/20 rounded-full animate-pulse"></div>
                </div>
                <div className="text-center">
                  <h3 className="text-2xl font-extrabold text-white mb-2 tracking-tight drop-shadow-lg">
                    Deploying Salary Contract
                  </h3>
                  <p className="text-zinc-300 text-lg">
                    Deploying your contract to the blockchain...
                  </p>
                  <p className="text-zinc-400 text-sm mt-2">
                    This may take a few moments
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Adding Employee Loading Modal */}
        {showAddingEmployeeModal && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-2xl flex items-center justify-center z-50">
            <div className="bg-gradient-to-br from-zinc-900/90 via-zinc-800/80 to-cyan-900/60 border border-cyan-400/20 rounded-3xl p-10 w-full max-w-md mx-4 shadow-2xl ring-2 ring-cyan-400/10">
              <div className="flex flex-col items-center space-y-6">
                <div className="relative">
                  <Loader2 className="h-16 w-16 text-cyan-400 animate-spin" />
                  <div className="absolute inset-0 bg-cyan-400/20 rounded-full animate-pulse"></div>
                </div>
                <div className="text-center">
                  <h3 className="text-2xl font-extrabold text-white mb-2 tracking-tight drop-shadow-lg">
                    Adding Employee
                  </h3>
                  <p className="text-zinc-300 text-lg">
                    Adding employee to salary contract...
                  </p>
                  <p className="text-zinc-400 text-sm mt-2">
                    This may take a few moments
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Force Payout Loading Modal */}
        {showForcePayoutModal && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-2xl flex items-center justify-center z-50">
            <div className="bg-gradient-to-br from-zinc-900/90 via-zinc-800/80 to-cyan-900/60 border border-cyan-400/20 rounded-3xl p-10 w-full max-w-md mx-4 shadow-2xl ring-2 ring-cyan-400/10">
              <div className="flex flex-col items-center space-y-6">
                <div className="relative">
                  <Loader2 className="h-16 w-16 text-cyan-400 animate-spin" />
                  <div className="absolute inset-0 bg-cyan-400/20 rounded-full animate-pulse"></div>
                </div>
                <div className="text-center">
                  <h3 className="text-2xl font-extrabold text-white mb-2 tracking-tight drop-shadow-lg">
                    Deploying Transaction
                  </h3>
                  <p className="text-zinc-300 text-lg">
                    Deploying transaction to blockchain...
                  </p>
                  <p className="text-zinc-400 text-sm mt-2">
                    This may take a few moments
                  </p>
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
                    onChange={(e) => handleNewMemberChange('schedule', e.target.value as 'monthly' | 'bi-weekly' | 'weekly' | 'custom')}
                    className="w-full px-5 py-4 bg-zinc-900/70 border border-zinc-600/40 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-cyan-400/60 focus:border-transparent text-lg shadow-inner"
                  >
                    <option value="monthly">Monthly</option>
                    <option value="bi-weekly">Bi-weekly</option>
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
          {/* Team Tab Token Address Warning */}
          {activeTab === 'team' && !tokenAddress && (
            <div className="flex-1 mr-4 p-4 bg-gradient-to-r from-amber-900/30 to-orange-900/30 border border-amber-500/30 rounded-xl">
              <div className="flex items-center gap-3">
                <AlertCircle className="h-5 w-5 text-amber-400" />
                <div>
                  <p className="text-amber-200 font-medium">Cannot Save Team Settings</p>
                  <p className="text-amber-300 text-sm">
                    You need to deploy your smart token from the Fundraising tab before you can save team settings.
                  </p>
                </div>
              </div>
            </div>
          )}

          <button
            onClick={handleSave}
            disabled={saving || (activeTab === 'team' && !tokenAddress)}
            className={`flex items-center space-x-2 px-8 py-3 font-medium rounded-lg transition-all ${
              activeTab === 'team' && !tokenAddress
                ? 'bg-zinc-600/80 text-zinc-400 cursor-not-allowed'
                : 'bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-600 hover:to-blue-700 text-white'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
            title={activeTab === 'team' && !tokenAddress ? "Deploy your smart token first" : "Save changes"}
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

      {/* Settlements Modal */}
      {showSettlementsModal && (
        <Dialog open={showSettlementsModal} onOpenChange={setShowSettlementsModal}>
          <DialogContent className="sm:max-w-4xl w-[95vw] max-h-[90vh] bg-zinc-900/95 backdrop-blur-lg border border-zinc-700 rounded-xl shadow-2xl">
            <DialogHeader className="px-4 sm:px-6">
              <DialogTitle className="text-xl sm:text-2xl text-white flex items-center gap-3">
                <History className="h-5 w-5 sm:h-6 sm:w-6 text-cyan-400" />
                Settlement History
              </DialogTitle>
              <DialogDescription className="text-sm sm:text-base text-zinc-400">
                View all payout transactions for your team members
              </DialogDescription>
            </DialogHeader>

            <div className="mt-4 sm:mt-6 px-4 sm:px-6 pb-4">
              {settlementsLoading ? (
                <div className="flex items-center justify-center py-8 sm:py-12">
                  <Loader2 className="h-6 w-6 sm:h-8 sm:w-8 animate-spin text-cyan-400" />
                  <span className="ml-3 text-sm sm:text-base text-zinc-400">Loading settlements and resolving usernames...</span>
                </div>
              ) : settlementsData.length > 0 ? (
                <div className="max-h-[60vh] sm:max-h-96 overflow-y-auto space-y-3 pr-1 sm:pr-2">
                  {settlementsData.map((payout, index) => (
                    <div
                      key={index}
                      className="bg-zinc-800/50 rounded-lg p-3 sm:p-4 border border-zinc-700/30 hover:border-cyan-400/30 transition-all duration-200"
                    >
                      {/* Mobile-first layout: Stack vertically on small screens */}
                      <div className="space-y-3 sm:space-y-0 sm:flex sm:items-start sm:justify-between">
                        {/* Employee and Date Section */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 sm:gap-3 mb-2">
                            <div className="w-2 h-2 bg-cyan-400 rounded-full flex-shrink-0"></div>
                            <span className="text-white font-medium truncate text-sm sm:text-base">
                              {payout.username ?
                                `@${payout.username}` :
                                payout.employee_wallet ?
                                  `${payout.employee_wallet.slice(0, 6)}...${payout.employee_wallet.slice(-4)}` :
                                  'Unknown Employee'
                              }
                            </span>
                            {!payout.username && payout.employee_wallet && (
                              <span className="text-xs text-zinc-500 bg-zinc-700/50 px-2 py-1 rounded-full flex-shrink-0">
                                No username
                              </span>
                            )}
                          </div>
                          <div className="text-xs sm:text-sm text-zinc-400">
                            {payout.timestamp ?
                              new Date(payout.timestamp).toLocaleDateString('en-US', {
                                year: 'numeric',
                                month: 'short',
                                day: 'numeric'
                              }) :
                              'Unknown Date'
                            }
                          </div>
                        </div>

                        {/* Amounts Section - Responsive layout */}
                        <div className="grid grid-cols-2 gap-3 sm:flex sm:items-center sm:gap-4 sm:ml-4">
                          <div className="text-center sm:text-right">
                            <div className="text-xs sm:text-sm text-zinc-400 mb-1">USDC Amount</div>
                            <div className="text-white font-semibold text-sm sm:text-base">
                              ${payout.usdc_amount ? payout.usdc_amount.toFixed(2) : '0.00'}
                            </div>
                          </div>
                          <div className="text-center sm:text-right">
                            <div className="text-xs sm:text-sm text-zinc-400 mb-1">{fundraisingData.tokenName || 'Token'} Amount</div>
                            <div className="text-white font-semibold text-sm sm:text-base">
                              {payout.custom_token_amount ? payout.custom_token_amount.toLocaleString() : '0'}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Payout Type Badge - Full width on mobile */}
                      {payout.payout_type && (
                        <div className="mt-3 pt-3 border-t border-zinc-700/30">
                          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-zinc-700/50 text-zinc-300">
                            {payout.payout_type.charAt(0).toUpperCase() + payout.payout_type.slice(1)} Payout
                          </span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 sm:py-12">
                  <History className="h-10 w-10 sm:h-12 sm:w-12 text-zinc-500 mx-auto mb-3 opacity-50" />
                  <p className="text-zinc-400 text-base sm:text-lg">No settlements found</p>
                  <p className="text-zinc-500 text-sm mt-1">
                    {salaryContractAddress ?
                      'No payout transactions have been recorded yet.' :
                      'Please add team members to start recording settlements.'
                    }
                  </p>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}