import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getAllJobs } from '../utils/api';
import { BookOpen, Clock, CheckCircle, Download, Eye } from 'lucide-react';

interface Job {
  job_id: string;
  processing_date: string;
  total_chapters: number;
  successful_chapters: number;
  total_words: number;
  processing_time: number;
  audio_files_count: number;
  status: string;
}

export const ChaptersPage: React.FC = () => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadJobs();
  }, []);

  const loadJobs = async () => {
    try {
      setLoading(true);
      const response = await getAllJobs();
      setJobs(response.jobs);
    } catch (err: any) {
      setError('Failed to load processed chapters');
      console.error('Failed to load jobs:', err);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateString;
    }
  };

  const formatDuration = (seconds: number) => {
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
  };

  if (loading) {
    return (
      <div className="px-40 flex flex-1 justify-center py-5">
        <div className="layout-content-container flex flex-col w-[960px] max-w-[960px] py-5">
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            <span className="ml-3 text-primary-600">Loading processed chapters...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="px-40 flex flex-1 justify-center py-5">
        <div className="layout-content-container flex flex-col w-[960px] max-w-[960px] py-5">
          <div className="text-center text-red-600">
            <p>{error}</p>
            <button 
              onClick={loadJobs}
              className="mt-4 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="px-40 flex flex-1 justify-center py-5">
      <div className="layout-content-container flex flex-col w-[960px] max-w-[960px] py-5">
        <div className="flex flex-wrap justify-between gap-3 p-4">
          <div className="flex min-w-72 flex-col gap-3">
            <p className="text-primary-700 tracking-light text-[32px] font-bold leading-tight">
              Processed Chapters
            </p>
            <p className="text-primary-500 text-sm font-normal leading-normal">
              View and manage your converted audiobook chapters
            </p>
          </div>
        </div>

        {jobs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <BookOpen className="h-16 w-16 text-primary-300 mb-4" />
            <h3 className="text-lg font-medium text-primary-700 mb-2">No chapters processed yet</h3>
            <p className="text-primary-500 mb-6">Start by uploading a book to convert to audio</p>
            <Link 
              to="/"
              className="px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
            >
              Upload a Book
            </Link>
          </div>
        ) : (
          <div className="grid gap-4 p-4">
            {jobs.map((job) => (
              <div key={job.job_id} className="bg-white border border-primary-200 rounded-lg p-6 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold text-primary-700">
                        Conversion {job.job_id.slice(0, 8)}...
                      </h3>
                      <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
                        job.status === 'completed' 
                          ? 'bg-green-100 text-green-800' 
                          : 'bg-red-100 text-red-800'
                      }`}>
                        <CheckCircle className="h-3 w-3" />
                        {job.status}
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4 text-sm">
                      <div>
                        <span className="text-primary-500">Chapters:</span>
                        <span className="ml-1 font-medium">{job.successful_chapters}/{job.total_chapters}</span>
                      </div>
                      <div>
                        <span className="text-primary-500">Words:</span>
                        <span className="ml-1 font-medium">{job.total_words.toLocaleString()}</span>
                      </div>
                      <div>
                        <span className="text-primary-500">Duration:</span>
                        <span className="ml-1 font-medium">{formatDuration(job.processing_time)}</span>
                      </div>
                      <div>
                        <span className="text-primary-500">Audio Files:</span>
                        <span className="ml-1 font-medium">{job.audio_files_count}</span>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-2 text-xs text-primary-500">
                      <Clock className="h-3 w-3" />
                      Processed: {formatDate(job.processing_date)}
                    </div>
                  </div>
                  
                  <div className="flex gap-2 ml-4">
                    <a
                      href={`http://localhost:8000/results/${job.job_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 px-3 py-1.5 bg-primary-100 text-primary-700 rounded-lg hover:bg-primary-200 transition-colors text-sm"
                    >
                      <Eye className="h-4 w-4" />
                      View Details
                    </a>
                    <a
                      href={`/api/download/${job.job_id}`}
                      className="flex items-center gap-1 px-3 py-1.5 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition-colors text-sm"
                    >
                      <Download className="h-4 w-4" />
                      Download
                    </a>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};