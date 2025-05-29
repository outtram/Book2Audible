export interface ConversionJob {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  current_step: string;
  chapters: Chapter[];
  error_message?: string;
  start_time?: string;
  end_time?: string;
}

export interface Chapter {
  number: number;
  title: string;
  audio_file?: string;
  text_file?: string;
  verification_passed: boolean;
  duration_ms: number;
}

export interface UploadResponse {
  job_id: string;
  filename: string;
  file_size: number;
  character_count: number;
  word_count: number;
  estimated_cost_fal: number;
}

export interface Provider {
  id: string;
  name: string;
  description: string;
  pricing: string;
  voices: number;
  recommended: boolean;
}

export interface ConversionRequest {
  voice: string;
  provider: string;
  manual_chapters?: string[];
}