import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { AudioDto } from "../types/api";

export function useAudios() {
  return useQuery({
    queryKey: ["audios"],
    queryFn: async () => {
      const { data } = await api.get<AudioDto[]>("/api/audios");
      return data ?? [];
    }
  });
}

export function useAudio(id?: string) {
  return useQuery({
    queryKey: ["audios", id],
    enabled: Boolean(id),
    queryFn: async () => {
      const { data } = await api.get<AudioDto>(`/api/audios/${id}`);
      return data;
    }
  });
}

export function useUploadAudio(onProgress?: (progress: number) => void) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ file, sourceType = "Uploaded" }: { file: File; sourceType?: "Recorded" | "Uploaded" }) => {
      const form = new FormData();
      form.append("file", file);
      form.append("sourceType", sourceType);
      const { data } = await api.post<AudioDto>("/api/audios/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (event) => {
          if (!event.total) return;
          onProgress?.(Math.round((event.loaded / event.total) * 100));
        }
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["audios"] });
    }
  });
}

export function useDeleteAudio() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/api/audios/${id}`);
      return id;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["audios"] });
      queryClient.invalidateQueries({ queryKey: ["translations"] });
    }
  });
}
