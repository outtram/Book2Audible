import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import { uploadFile } from '../utils/api';
import { Upload, FileText, AlertCircle } from 'lucide-react';
import type { UploadResponse } from '../types';

export const UploadPage: React.FC = () => {
  const navigate = useNavigate();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);

  const { getRootProps, getInputProps, isDragActive, acceptedFiles } = useDropzone({
    accept: {
      'text/plain': ['.txt'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx']
    },
    maxFiles: 1,
    maxSize: 10 * 1024 * 1024, // 10MB
    onDrop: handleFileDrop
  });

  async function handleFileDrop(files: File[]) {
    if (files.length === 0) return;
    
    const file = files[0];
    setUploading(true);
    setError(null);
    
    try {
      const result = await uploadFile(file);
      setUploadResult(result);
      
      // Navigate to configuration page after successful upload
      setTimeout(() => {
        navigate(`/configure/${result.job_id}`);
      }, 1500);
      
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="px-40 flex flex-1 justify-center py-5">
      <div className="layout-content-container flex flex-col max-w-[960px] flex-1">
        <div className="flex flex-wrap justify-between gap-3 p-4">
          <p className="text-primary-700 tracking-light text-[32px] font-bold leading-tight min-w-72">
            Upload Your Book
          </p>
        </div>
        
        <p className="text-primary-700 text-base font-normal leading-normal pb-3 pt-1 px-4">
          Drag and drop your book file here or click to select a file. Accepted formats: TXT, DOCX. Maximum file size: 10MB.
        </p>
        
        <div className="flex flex-col p-4">
          {!uploadResult ? (
            <div
              {...getRootProps()}
              className={`flex flex-col items-center gap-6 rounded-lg border-2 border-dashed px-6 py-14 cursor-pointer transition-colors ${
                isDragActive 
                  ? 'border-primary-600 bg-primary-50' 
                  : 'border-primary-200 hover:border-primary-400'
              }`}
            >
              <input {...getInputProps()} />
              
              <div className="flex flex-col items-center gap-4">
                {uploading ? (
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
                ) : (
                  <Upload className="h-12 w-12 text-primary-500" />
                )}
                
                <div className="flex max-w-[480px] flex-col items-center gap-2">
                  <p className="text-primary-700 text-lg font-bold leading-tight tracking-[-0.015em] max-w-[480px] text-center">
                    {uploading ? 'Uploading...' : isDragActive ? 'Drop your file here' : 'Drag and drop your file here'}
                  </p>
                  {!uploading && (
                    <p className="text-primary-700 text-sm font-normal leading-normal max-w-[480px] text-center">
                      Or
                    </p>
                  )}
                </div>
                
                {!uploading && (
                  <button
                    type="button"
                    className="flex min-w-[84px] max-w-[480px] cursor-pointer items-center justify-center overflow-hidden rounded-lg h-10 px-4 bg-primary-100 text-primary-700 text-sm font-bold leading-normal tracking-[0.015em]"
                  >
                    <span className="truncate">Browse Files</span>
                  </button>
                )}
              </div>
              
              {acceptedFiles.length > 0 && (
                <div className="flex items-center gap-3 p-3 bg-primary-50 rounded-lg">
                  <FileText className="h-5 w-5 text-primary-600" />
                  <span className="text-primary-700 text-sm">
                    {acceptedFiles[0].name} ({formatFileSize(acceptedFiles[0].size)})
                  </span>
                </div>
              )}
            </div>
          ) : (
            // Upload success state
            <div className="flex flex-col items-center gap-6 rounded-lg border-2 border-solid border-green-200 bg-green-50 px-6 py-14">
              <div className="flex items-center justify-center w-12 h-12 bg-green-100 rounded-full">
                <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              
              <div className="text-center">
                <h3 className="text-lg font-bold text-primary-700 mb-2">Upload Successful!</h3>
                <div className="text-sm text-primary-600 space-y-1">
                  <p><strong>File:</strong> {uploadResult.filename}</p>
                  <p><strong>Size:</strong> {formatFileSize(uploadResult.file_size)}</p>
                  <p><strong>Words:</strong> {uploadResult.word_count.toLocaleString()}</p>
                  <p><strong>Characters:</strong> {uploadResult.character_count.toLocaleString()}</p>
                  <p><strong>Estimated Cost (Fal.ai):</strong> ${uploadResult.estimated_cost_fal}</p>
                </div>
                <p className="text-sm text-primary-500 mt-3">Redirecting to configuration...</p>
              </div>
            </div>
          )}
          
          {error && (
            <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3">
              <AlertCircle className="h-5 w-5 text-red-500" />
              <span className="text-red-700 text-sm">{error}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};