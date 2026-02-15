import axios from 'axios';

// Clark (agents) only. In the browser always use '' so Next.js rewrites proxy to Clark (avoids ERR_CONNECTION_REFUSED).
// Rewrite destination in next.config is NEXT_PUBLIC_AGENTS_API_URL || http://127.0.0.1:8000.
const AGENTS_API_BASE_URL =
  typeof window !== 'undefined' ? '' : (process.env.NEXT_PUBLIC_AGENTS_API_URL || 'http://127.0.0.1:8000');

// Create axios instance for Agents API
// Long timeout: Clark queries (backtest, multi-agent, etc.) can take 1–2+ minutes
const AGENTS_REQUEST_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes

const agentsApi = axios.create({
  baseURL: AGENTS_API_BASE_URL,
  timeout: AGENTS_REQUEST_TIMEOUT_MS,
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
export const processNaturalLanguageQuery = async (query: string, userId?: string, username?: string, sessionId?: string) => {
  try {
    const response = await agentsApi.post('/api/v1/agents/query', {
      query,
      user_id: userId,
      username: username,
      session_id: sessionId
    });
    return response.data;
  } catch (error) {
    console.error('Error processing natural language query:', error);
    throw error;
  }
};

export default agentsApi;