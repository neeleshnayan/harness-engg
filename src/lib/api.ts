import axios from 'axios';
import http from 'http';
import https from 'https';

// Set the base URL for API requests
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
const KRYPTON_WEB3_API_BASE_URL = process.env.NEXT_PUBLIC_KRYPTON_WEB3_API_URL || 'http://127.0.0.1:8001';

const httpAgent = new http.Agent({
  keepAlive: true,
});

const httpsAgent = new https.Agent({
  keepAlive: true,
});

export const kryptonWeb3Api = axios.create({
  baseURL: KRYPTON_WEB3_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  httpAgent: httpAgent,
  httpsAgent: httpsAgent,
  timeout: 600000,
});

// Subgraph API client for Krypton liquidity pools
const SUBGRAPH_API_BASE_URL = process.env.NEXT_PUBLIC_SUBGRAPH_API_URL || 'https://api.studio.thegraph.com/query/1714038/krypton-liquidity-pools-sepolia/version/latest';

export const kryptonPoolsSubgraphApi = axios.create({
  baseURL: SUBGRAPH_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Hedge Fund API Client
const HEDGE_FUND_API_BASE_URL = process.env.NEXT_PUBLIC_HEDGE_FUND_API_URL || 'http://127.0.0.1:8001';

export const hedgeFundApi = axios.create({
  baseURL: HEDGE_FUND_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Create axios instance with base URL
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for authentication if needed
api.interceptors.request.use(
  (config) => {
    // You can add auth headers here if needed
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // Handle common errors here
    if (error.response?.status === 401) {
      // Handle unauthorized
      console.error('Unauthorized request');
    }
    return Promise.reject(error);
  }
);

// Helper function to check KYC status
export const checkKycStatus = async (userId: string) => {
  try {
    const response = await api.post(`/api/v1/kyc/check-status/${userId}`);
    return response.data;
  } catch (error) {
    console.error('Error checking KYC status:', error);
    throw error;
  }
};

// Helper function to get user info
export const getUserInfo = async (userId: string) => {
  try {
    const response = await api.get(`/api/v1/user/${userId}`);
    return response.data;
  } catch (error) {
    console.error('Error getting user info:', error);
    throw error;
  }
};

// Helper function to get token info
export const getTokenInfo = async (tokenAddress: string) => {
  try {
    const response = await api.get(`/api/v1/smarttoken/token_info/${tokenAddress}`);
    return response.data;
  } catch (error) {
    console.error('Error getting token info:', error);
    throw error;
  }
};


export default api;
