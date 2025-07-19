import { jwtDecode } from 'jwt-decode';

interface TokenPayload {
  sub: string;
  email: string;
  google_id: string;
  exp: number;
  type: string;
}

interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

class AuthManager {
  private static instance: AuthManager;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;

  private constructor() {
    // Load tokens from localStorage on initialization
    this.loadTokens();
  }

  public static getInstance(): AuthManager {
    if (!AuthManager.instance) {
      AuthManager.instance = new AuthManager();
    }
    return AuthManager.instance;
  }

  private loadTokens(): void {
    if (typeof window !== 'undefined') {
      this.accessToken = localStorage.getItem('access_token');
      this.refreshToken = localStorage.getItem('refresh_token');
    }
  }

  private saveTokens(tokens: AuthTokens): void {
    if (typeof window !== 'undefined') {
      localStorage.setItem('access_token', tokens.access_token);
      localStorage.setItem('refresh_token', tokens.refresh_token);
      this.accessToken = tokens.access_token;
      this.refreshToken = tokens.refresh_token;
    }
  }

  private clearTokens(): void {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('userData');
      this.accessToken = null;
      this.refreshToken = null;
    }
  }

  public getAccessToken(): string | null {
    return this.accessToken;
  }

  public isTokenExpired(token: string): boolean {
    try {
      const decoded = jwtDecode<TokenPayload>(token);
      const currentTime = Date.now() / 1000;
      return decoded.exp < currentTime;
    } catch {
      return true;
    }
  }

  public async refreshAccessToken(): Promise<string | null> {
    if (!this.refreshToken) {
      return null;
    }

    try {
      const response = await fetch('/api/v1/auth/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          refresh_token: this.refreshToken,
        }),
      });

      if (response.ok) {
        const tokens = await response.json();
        this.saveTokens(tokens);
        return tokens.access_token;
      } else {
        this.clearTokens();
        return null;
      }
    } catch (error) {
      console.error('Error refreshing token:', error);
      this.clearTokens();
      return null;
    }
  }

  public async getValidToken(): Promise<string | null> {
    if (!this.accessToken) {
      return null;
    }

    if (this.isTokenExpired(this.accessToken)) {
      const newToken = await this.refreshAccessToken();
      return newToken;
    }

    return this.accessToken;
  }

  public setTokens(tokens: AuthTokens): void {
    this.saveTokens(tokens);
  }

  public logout(): void {
    this.clearTokens();
  }

  public isAuthenticated(): boolean {
    return !!this.accessToken && !this.isTokenExpired(this.accessToken);
  }
}

export const authManager = AuthManager.getInstance(); 