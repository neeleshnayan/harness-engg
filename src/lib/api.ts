import axios, { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse } from 'axios';
import { authManager } from './auth';

// Set the base URL for API requests
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://kryptonpaybackend-production.up.railway.app';

// Create axios instance with base URL
const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for authentication
api.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    // Get valid token (refresh if needed)
    const token = await authManager.getValidToken();
    
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor for handling auth errors
api.interceptors.response.use(
  (response: AxiosResponse) => {
    return response;
  },
  async (error) => {
    const originalRequest = error.config;
    
    // If we get a 401 and haven't already tried to refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      // Try to refresh the token
      const newToken = await authManager.refreshAccessToken();
      
      if (newToken) {
        // Retry the original request with new token
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return api(originalRequest);
      } else {
        // Refresh failed, redirect to login
        authManager.logout();
        if (typeof window !== 'undefined') {
          window.location.href = '/';
        }
      }
    }
    
    return Promise.reject(error);
  }
);

export default api; 