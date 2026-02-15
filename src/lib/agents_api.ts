import axios, { type InternalAxiosRequestConfig } from 'axios';

// Extend axios config for retry count (avoids casting to any)
declare module 'axios' {
  interface InternalAxiosRequestConfig {
    __agentsRetryCount?: number;
  }
}

// Clark (agents) only. In the browser always use '' so Next.js rewrites proxy to Clark (avoids ERR_CONNECTION_REFUSED).
// Rewrite destination in next.config is NEXT_PUBLIC_AGENTS_API_URL || http://127.0.0.1:8000.
const AGENTS_API_BASE_URL =
  typeof window !== 'undefined' ? '' : (process.env.NEXT_PUBLIC_AGENTS_API_URL || 'http://127.0.0.1:8000');

// Create axios instance for Agents API
// Long timeout: Clark queries (backtest, multi-agent, etc.) can take 1–2+ minutes
const AGENTS_REQUEST_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes

// Retry on 5xx (cold start / Railway scale-up): max 2 retries with backoff
const AGENTS_RETRY_MAX = 2;
const AGENTS_RETRY_DELAYS_MS = [2000, 5000];

const agentsApi = axios.create({
  baseURL: AGENTS_API_BASE_URL,
  timeout: AGENTS_REQUEST_TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json',
  },
});

agentsApi.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (config.__agentsRetryCount === undefined) {
      config.__agentsRetryCount = 0;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

agentsApi.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      console.error('Unauthorized request to agents API');
    }
    const config = error.config as InternalAxiosRequestConfig | undefined;
    const status = error.response?.status;
    const isRetryable = status >= 500 && status <= 599;
    const retryCount = config?.__agentsRetryCount ?? 0;
    if (isRetryable && config && retryCount < AGENTS_RETRY_MAX) {
      config.__agentsRetryCount = retryCount + 1;
      const delayMs = AGENTS_RETRY_DELAYS_MS[retryCount] ?? 5000;
      await new Promise((r) => setTimeout(r, delayMs));
      return agentsApi.request(config);
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