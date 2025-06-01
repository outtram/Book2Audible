import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useWebSocket } from '../hooks/useWebSocket';
import { getJobStatus } from '../utils/api';
import { Loader2, CheckCircle, XCircle, Clock } from 'lucide-react';
import type { ConversionJob } from '../types';

export const ProcessingPage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const { status: wsStatus, isConnected } = useWebSocket(jobId || null);
  const [apiStatus, setApiStatus] = useState<ConversionJob | null>(null);
  const [loading, setLoading] = useState(true);

  // Use API status if available, otherwise fall back to WebSocket status
  const status = apiStatus || wsStatus;

  useEffect(() => {
    // Check API status on page load
    const checkApiStatus = async () => {
      if (!jobId) return;
      
      try {
        const apiResponse = await getJobStatus(jobId);
        setApiStatus(apiResponse);
      } catch (error) {
        console.error('Failed to get job status from API:', error);
      } finally {
        setLoading(false);
      }
    };

    checkApiStatus();
  }, [jobId]);

  useEffect(() => {
    if (status?.status === 'completed') {
      // Navigate to results page when completed
      setTimeout(() => navigate(`/results/${jobId}`), 2000);
    }
  }, [status?.status, jobId, navigate]);

  if (!jobId) {
    return <div>Invalid job ID</div>;
  }

  // Show loading state while checking API
  if (loading && !status) {
    return (
      <div className="px-40 flex flex-1 justify-center py-5">
        <div className="layout-content-container flex flex-col max-w-[960px] flex-1">
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            <span className="ml-3 text-primary-600">Loading job status...</span>
          </div>
        </div>
      </div>
    );
  }

  const formatTime = (dateString?: string) => {
    if (!dateString) return '';
    return new Date(dateString).toLocaleTimeString();
  };

  const getStatusIcon = () => {
    if (!status) return <Loader2 className="h-6 w-6 animate-spin text-primary-600" />;
    
    switch (status.status) {
      case 'completed':
        return <CheckCircle className="h-6 w-6 text-green-500" />;
      case 'failed':
        return <XCircle className="h-6 w-6 text-red-500" />;
      case 'processing':
        return <Loader2 className="h-6 w-6 animate-spin text-primary-600" />;
      default:
        return <Clock className="h-6 w-6 text-primary-500" />;
    }
  };

  const getStatusText = () => {
    if (!status) return 'Initializing...';
    
    switch (status.status) {
      case 'completed':
        return 'Conversion Complete!';
      case 'failed':
        return 'Conversion Failed';
      case 'processing':
        return 'Converting to Audio...';
      case 'pending':
        return 'Preparing Conversion...';
      default:
        return 'Unknown Status';
    }
  };

  const getProgressColor = () => {
    if (!status) return 'bg-primary-600';
    
    switch (status.status) {
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      default:
        return 'bg-primary-600';
    }
  };

  return (
    <div className="px-40 flex flex-1 justify-center py-5">
      <div className="layout-content-container flex flex-col max-w-[960px] flex-1">
        <div className="flex flex-wrap justify-between gap-3 p-4">
          <p className="text-primary-700 tracking-light text-[32px] font-bold leading-tight min-w-72">
            Converting Book
          </p>
        </div>

        {/* Progress Section */}
        <div className="flex flex-col gap-3 p-4">
          <div className="flex gap-6 justify-between items-center">
            <div className="flex items-center gap-3">
              {getStatusIcon()}
              <p className="text-primary-700 text-base font-medium leading-normal">
                {getStatusText()}
              </p>
            </div>
            {!isConnected && (
              <div className="flex items-center gap-2 text-amber-600 text-sm">
                <div className="w-2 h-2 bg-amber-600 rounded-full animate-pulse"></div>
                Connecting...
              </div>
            )}
          </div>

          {/* Progress Bar */}
          <div className="rounded bg-primary-200">
            <div 
              className={`h-2 rounded transition-all duration-500 ${getProgressColor()}`}
              style={{ width: `${(status?.progress || 0) * 100}%` }}
            ></div>
          </div>
          
          <p className="text-primary-500 text-sm font-normal leading-normal">
            {Math.round((status?.progress || 0) * 100)}%
          </p>
        </div>

        {/* Current Step */}
        <p className="text-primary-700 text-base font-normal leading-normal pb-3 pt-1 px-4">
          {status?.current_step || 'Preparing...'}
        </p>

        {/* Chapter Progress */}
        {status?.chapters && status.chapters.length > 0 && (
          <div className="px-4 pb-4">
            <h3 className="text-primary-700 text-lg font-bold leading-tight tracking-[-0.015em] pb-3">
              Chapter Progress
            </h3>
            <div className="space-y-2">
              {status.chapters.map((chapter, index) => (
                <div key={index} className="flex items-center justify-between p-3 bg-primary-50 rounded-lg">
                  <div className="flex items-center gap-3">
                    {chapter.audio_file ? (
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    ) : (
                      <div className="w-4 h-4 border-2 border-primary-300 rounded-full"></div>
                    )}
                    <span className="text-primary-700 text-sm">
                      Chapter {chapter.number}: {chapter.title}
                    </span>
                  </div>
                  {chapter.verification_passed && (
                    <span className="text-xs text-green-600 bg-green-100 px-2 py-1 rounded-full">
                      Verified
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Processing Details */}
        {status && (
          <div className="px-4 pb-4">
            <div className="bg-primary-50 rounded-lg p-4 text-sm text-primary-600">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="font-medium">Status:</span> {status.status}
                </div>
                <div>
                  <span className="font-medium">Job ID:</span> {status.job_id}
                </div>
                {status.start_time && (
                  <div>
                    <span className="font-medium">Started:</span> {formatTime(status.start_time)}
                  </div>
                )}
                {status.end_time && (
                  <div>
                    <span className="font-medium">Completed:</span> {formatTime(status.end_time)}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Error Message */}
        {status?.error_message && (
          <div className="mx-4 mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center gap-3">
              <XCircle className="h-5 w-5 text-red-500" />
              <div>
                <p className="font-medium text-red-700">Conversion Failed</p>
                <p className="text-red-600 text-sm">{status.error_message}</p>
              </div>
            </div>
          </div>
        )}

        {/* Success Message */}
        {status?.status === 'completed' && (
          <div className="mx-4 mb-4 p-4 bg-green-50 border border-green-200 rounded-lg">
            <div className="flex items-center gap-3">
              <CheckCircle className="h-5 w-5 text-green-500" />
              <div>
                <p className="font-medium text-green-700">Conversion Completed Successfully!</p>
                <p className="text-green-600 text-sm">
                  Redirecting to download page...
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};