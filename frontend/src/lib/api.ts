import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import { tokenStore } from "./auth";
import type { AuthResponse } from "../types/api";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5031";

export const api = axios.create({
  baseURL,
  headers: {
    "Content-Type": "application/json"
  }
});

let refreshPromise: Promise<AuthResponse> | null = null;

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = tokenStore.getAccessToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  console.info("[TRACE] Axios request", {
    method: config.method?.toUpperCase(),
    url: `${config.baseURL ?? ""}${config.url ?? ""}`,
    data: config.data
  });
  return config;
});

api.interceptors.response.use(
  (response) => {
    console.info("[TRACE] Axios response", {
      method: response.config.method?.toUpperCase(),
      url: `${response.config.baseURL ?? ""}${response.config.url ?? ""}`,
      status: response.status,
      data: response.data
    });
    return response;
  },
  async (error: AxiosError) => {
    console.error("[TRACE] Axios error response", {
      method: error.config?.method?.toUpperCase(),
      url: `${error.config?.baseURL ?? ""}${error.config?.url ?? ""}`,
      status: error.response?.status,
      data: error.response?.data,
      message: error.message
    });
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
    const refreshToken = tokenStore.getRefreshToken();

    if (error.response?.status !== 401 || !original || original._retry || !refreshToken) {
      return Promise.reject(error);
    }

    original._retry = true;

    refreshPromise ??= axios
      .post<AuthResponse>(`${baseURL}/api/auth/refresh`, { refreshToken })
      .then((response) => {
        tokenStore.setTokens(response.data);
        return response.data;
      })
      .finally(() => {
        refreshPromise = null;
      });

    const auth = await refreshPromise;
    original.headers.Authorization = `Bearer ${auth.accessToken}`;
    return api(original);
  }
);

export function getApiError(error: unknown) {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { error?: string; title?: string } | undefined;
    return data?.error ?? data?.title ?? error.message;
  }
  return "Something went wrong.";
}
