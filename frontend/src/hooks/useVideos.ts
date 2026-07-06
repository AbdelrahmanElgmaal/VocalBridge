import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { VideoDto } from "../types/api";

export function useVideos() {
  return useQuery({
    queryKey: ["videos"],
    queryFn: async () => {
      const { data } = await api.get<VideoDto[]>("/api/videos");
      return data ?? [];
    }
  });
}

export function useVideo(id?: string) {
  return useQuery({
    queryKey: ["videos", id],
    enabled: Boolean(id),
    queryFn: async () => {
      const { data } = await api.get<VideoDto>(`/api/videos/${id}`);
      return data;
    }
  });
}

export function useUploadVideo(onProgress?: (progress: number) => void) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post<VideoDto>("/api/videos/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (event) => {
          if (!event.total) return;
          onProgress?.(Math.round((event.loaded / event.total) * 100));
        }
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["videos"] });
    }
  });
}

export function useDeleteVideo() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/api/videos/${id}`);
      return id;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["videos"] });
      queryClient.invalidateQueries({ queryKey: ["translations"] });
    }
  });
}
