import type { AuthResponse } from "../types/api";

const ACCESS_TOKEN_KEY = "vocalBridge.accessToken";
const REFRESH_TOKEN_KEY = "vocalBridge.refreshToken";
const EXPIRES_AT_KEY = "vocalBridge.expiresAt";

export const tokenStore = {
  getAccessToken: () => localStorage.getItem(ACCESS_TOKEN_KEY),
  getRefreshToken: () => localStorage.getItem(REFRESH_TOKEN_KEY),
  setTokens: (auth: AuthResponse) => {
    localStorage.setItem(ACCESS_TOKEN_KEY, auth.accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, auth.refreshToken);
    localStorage.setItem(EXPIRES_AT_KEY, auth.expiresAt);
  },
  clear: () => {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(EXPIRES_AT_KEY);
  },
  isAuthenticated: () => Boolean(localStorage.getItem(ACCESS_TOKEN_KEY))
};
