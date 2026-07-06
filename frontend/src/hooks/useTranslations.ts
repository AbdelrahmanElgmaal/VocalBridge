import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { CreateTranslationRequest, TranslationDto } from "../types/api";

export function useTranslations(refetch = false) {
  return useQuery({
    queryKey: ["translations"],
    queryFn: async () => {
      const { data } = await api.get<TranslationDto[]>("/api/translations");
      return data ?? [];
    },
    refetchInterval: refetch ? 5000 : false
  });
}

export function useTranslation(id?: string, refetch = false) {
  return useQuery({
    queryKey: ["translations", id],
    enabled: Boolean(id),
    refetchInterval: refetch ? 4000 : false,
    queryFn: async () => {
      const { data } = await api.get<TranslationDto>(`/api/translations/${id}`);
      return data;
    }
  });
}

export function useCreateTranslation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: CreateTranslationRequest) => {
      console.info("[TRACE] POST /api/translations starting", payload);
      const { data } = await api.post<TranslationDto>("/api/translations", payload);
      console.info("[TRACE] POST /api/translations succeeded", data);
      return data;
    },
    onError: (error) => {
      console.error("[TRACE] POST /api/translations failed", error);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["translations"] });
    }
  });
}

export function useCancelTranslation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post<{ message: string }>(`/api/translations/${id}/cancel`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["translations"] });
    }
  });
}

export function useRetryTranslation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, options }: { id: string; options: CreateTranslationRequest }) => {
      const { data } = await api.post<TranslationDto>(`/api/translations/${id}/retry`, options);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["translations"] });
    }
  });
}
