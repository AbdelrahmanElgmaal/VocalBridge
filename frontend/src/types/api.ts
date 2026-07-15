export type TranslationStatus = "Queued" | "Processing" | "Completed" | "Failed" | "Cancelled" | string | number;
export type InputType = "Video" | "Audio" | string | number;
export type OutputType = "Video" | "Audio" | string | number;

export interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  expiresAt: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
}

export interface VideoDto {
  id: string;
  fileName: string;
  sourceType: string;
  fileSize?: number | null;
  uploadedAt: string;
  url?: string | null;
}

export interface AudioDto {
  id: string;
  fileName: string;
  sourceType: string;
  durationSeconds: number;
  fileSize?: number | null;
  createdAt: string;
  url?: string | null;
}

export interface TranslationDto {
  id: string;
  userId: string;
  inputType: InputType;
  outputType: OutputType;
  status: TranslationStatus;
  progress: number;
  translatedVideoUrl?: string | null;
  translatedAudioUrl?: string | null;
  errorMessage?: string | null;
  currentStage?: string | null;
  transcript?: string | null;
  translatedText?: string | null;
  createdAt: string;
  completedAt?: string | null;
  voiceCloning?: boolean | null;
  burnSubtitles?: boolean | null;
  enableLipsync?: boolean | null;
  voiceGender?: string | null;
  voiceAge?: string | null;
  voicePitch?: string | null;
  voiceStyle?: string | null;
  video?: VideoDto | null;
  audio?: AudioDto | null;
}

export interface CreateTranslationRequest {
  videoId?: string;
  videoUrl?: string;
  audioId?: string;
  inputType?: InputType;
  voiceCloning?: boolean;
  burnSubtitles?: boolean;
  enableLipsync?: boolean;
  voiceGender?: string;
  voiceAge?: string;
  voicePitch?: string;
  voiceStyle?: string;
}
