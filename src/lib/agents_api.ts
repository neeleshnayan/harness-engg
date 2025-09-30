import axios from 'axios';

// Set the base URL for Agents API requests
const AGENTS_API_BASE_URL = process.env.NEXT_PUBLIC_AGENTS_API_URL || 'https://agent.kryptonfund.com/';
// const AGENTS_API_BASE_URL = 'http://127.0.0.1:8000';

// Create axios instance for Agents API
const agentsApi = axios.create({
  baseURL: AGENTS_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for authentication if needed
agentsApi.interceptors.request.use(
  (config) => {
    // You can add auth headers here if needed
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling
agentsApi.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // Handle common errors here
    if (error.response?.status === 401) {
      // Handle unauthorized
      console.error('Unauthorized request to agents API');
    }
    return Promise.reject(error);
  }
);

// Agents API functions
export const processNaturalLanguageQuery = async (query: string, userId?: string) => {
  try {
    const response = await agentsApi.post('/api/v1/agents/query', {
      query,
      user_id: userId
    });
    return response.data;
  } catch (error) {
    console.error('Error processing natural language query:', error);
    throw error;
  }
};

export const getLangChainCapabilities = async () => {
  try {
    const response = await agentsApi.get('/api/v1/capabilities');
    return response.data;
  } catch (error) {
    console.error('Error getting LangChain capabilities:', error);
    throw error;
  }
};

export const checkLangChainHealth = async () => {
  try {
    const response = await agentsApi.get('/api/v1/health');
    return response.data;
  } catch (error) {
    console.error('Error checking LangChain health:', error);
    throw error;
  }
};

export default agentsApi;
