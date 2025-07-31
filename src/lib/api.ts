import axios from 'axios';

// Set the base URL for API requests
// const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.kryptonfund.com';
const API_BASE_URL = 'http://127.0.0.1:8000'

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

export default api; 