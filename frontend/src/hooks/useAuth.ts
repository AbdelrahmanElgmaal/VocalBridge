import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { tokenStore } from "../lib/auth";
import type { AuthResponse, LoginRequest, RegisterRequest } from "../types/api";

export function useLogin() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: LoginRequest) => {
      const { data } = await api.post<AuthResponse>("/api/auth/login", payload);
      return data;
    },
    onSuccess: (data) => {
      tokenStore.setTokens(data);
      queryClient.invalidateQueries();
      navigate("/dashboard");
    }
  });
}

export function useRegister() {
  const navigate = useNavigate();

  return useMutation({
    mutationFn: async (payload: RegisterRequest) => {
      const { data } = await api.post<AuthResponse>("/api/auth/register", payload);
      return data;
    },
    onSuccess: (data) => {
      tokenStore.setTokens(data);
      navigate("/dashboard");
    }
  });
}

export function useLogout() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  return () => {
    tokenStore.clear();
    queryClient.clear();
    navigate("/login");
  };
}
