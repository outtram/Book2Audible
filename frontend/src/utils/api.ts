import axios from 'axios';
import type { ConversionJob, UploadResponse, Provider, ConversionRequest } from '../types';

const API_BASE = '/api';

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000, // Increased timeout for conversion start
});

export const uploadFile = async (file: File): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  
  return response.data;
};

export const startConversion = async (
  jobId: string, 
  request: ConversionRequest
): Promise<{ job_id: string; status: string }> => {
  const response = await api.post(`/convert/${jobId}`, request);
  return response.data;
};

export const getJobStatus = async (jobId: string): Promise<ConversionJob> => {
  const response = await api.get(`/status/${jobId}`);
  return response.data;
};

export const getProviders = async (): Promise<{ providers: Provider[] }> => {
  const response = await api.get('/providers');
  return response.data;
};

export const getVoices = async (): Promise<{ fal: string[]; baseten: string[] }> => {
  const response = await api.get('/voices');
  return response.data;
};

export const testConnection = async (): Promise<{ fal: any; baseten: any }> => {
  const response = await api.get('/test-connection');
  return response.data;
};

export const getUploadInfo = async (jobId: string): Promise<any> => {
  const response = await api.get(`/upload/${jobId}`);
  return response.data;
};

export const getAllJobs = async (): Promise<{ jobs: any[] }> => {
  const response = await api.get('/all-jobs');
  return response.data;
};

export const downloadAllChapters = (jobId: string): string => {
  return `${API_BASE}/download/${jobId}`;
};