import axios from 'axios';

// Set the base URL for API requests
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.kryptonfund.com';
// const API_BASE_URL = 'http://127.0.0.1:8000'

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

export default api; 
