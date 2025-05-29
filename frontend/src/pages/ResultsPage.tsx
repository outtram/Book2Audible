import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { getJobStatus, downloadAllChapters } from '../utils/api';
import { Download, Play, Pause, Volume2, CheckCircle, XCircle, FileText } from 'lucide-react';
import type { ConversionJob } from '../types';

export const ResultsPage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const [job, setJob] = useState<ConversionJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [playingChapter, setPlayingChapter] = useState<number | null>(null);
  const [audioElements, setAudioElements] = useState<{ [key: number]: HTMLAudioElement }>({});

  useEffect(() => {
    if (jobId) {
      loadJobStatus();
    }
  }, [jobId]);

  const loadJobStatus = async () => {
    if (!jobId) return;
    
    try {
      const jobData = await getJobStatus(jobId);
      setJob(jobData);
      
      if (jobData.status !== 'completed') {
        setError('Conversion is not yet completed');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load conversion results');
    } finally {
      setLoading(false);
    }
  };

  const handlePlayPause = (chapterNumber: number, audioUrl: string) => {
    // Stop any currently playing audio
    Object.values(audioElements).forEach(audio => {
      if (!audio.paused) {
        audio.pause();
      }
    });

    if (playingChapter === chapterNumber) {
      // Pause current chapter
      setPlayingChapter(null);
    } else {
      // Play new chapter
      let audio = audioElements[chapterNumber];
      
      if (!audio) {
        // Create new audio element
        audio = new Audio(audioUrl);
        audio.onended = () => setPlayingChapter(null);
        audio.onerror = () => {
          console.error('Audio playback error');
          setPlayingChapter(null);
        };
        
        setAudioElements(prev => ({ ...prev, [chapterNumber]: audio }));
      }
      
      audio.play();
      setPlayingChapter(chapterNumber);
    }
  };

  const handleDownloadAll = () => {
    if (!jobId) return;
    
    const downloadUrl = downloadAllChapters(jobId);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `audiobook_${jobId}.zip`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const formatDuration = (ms: number) => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="px-40 flex flex-1 justify-center py-5">
        <div className="layout-content-container flex flex-col max-w-[960px] flex-1">
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3">
            <XCircle className="h-5 w-5 text-red-500" />
            <span className="text-red-700">{error}</span>
          </div>
        </div>
      </div>
    );
  }

  if (!job || job.status !== 'completed') {
    return (
      <div className="px-40 flex flex-1 justify-center py-5">
        <div className="layout-content-container flex flex-col max-w-[960px] flex-1">
          <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
            <p className="text-amber-700">Conversion is not yet completed</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="px-40 flex flex-1 justify-center py-5">
      <div className="layout-content-container flex flex-col max-w-[960px] flex-1">
        <div className="flex flex-wrap justify-between gap-3 p-4">
          <div className="flex min-w-72 flex-col gap-3">
            <p className="text-primary-700 tracking-light text-[32px] font-bold leading-tight">
              Audiobook Conversion Complete
            </p>
            <p className="text-primary-500 text-sm font-normal leading-normal">
              Your book has been successfully converted to audio. You can now download the audio files organized by chapter.
            </p>
          </div>
        </div>

        {/* Summary Stats */}
        <div className="px-4 pb-4">
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-primary-50 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-primary-700">{job.chapters.length}</div>
              <div className="text-sm text-primary-500">Chapters</div>
            </div>
            <div className="bg-primary-50 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-primary-700">
                {job.chapters.filter(c => c.verification_passed).length}
              </div>
              <div className="text-sm text-primary-500">Verified</div>
            </div>
            <div className="bg-primary-50 rounded-lg p-4 text-center">
              <div className="text-2xl font-bold text-primary-700">
                {Math.round(job.progress * 100)}%
              </div>
              <div className="text-sm text-primary-500">Complete</div>
            </div>
          </div>
        </div>

        {/* Chapter List */}
        {job.chapters.map((chapter) => (
          <div key={chapter.number} className="mb-4">
            <h3 className="text-primary-700 text-lg font-bold leading-tight tracking-[-0.015em] px-4 pb-2 pt-4">
              Chapter {chapter.number}: {chapter.title}
            </h3>
            
            <div className="flex items-center gap-4 bg-primary-50 px-4 min-h-14 justify-between">
              <div className="flex items-center gap-3 flex-1">
                {chapter.audio_file && (
                  <button
                    onClick={() => handlePlayPause(chapter.number, chapter.audio_file!)}
                    className="flex items-center justify-center w-8 h-8 rounded-full bg-primary-600 text-white hover:bg-primary-700 transition-colors"
                  >
                    {playingChapter === chapter.number ? (
                      <Pause className="h-4 w-4" />
                    ) : (
                      <Play className="h-4 w-4 ml-0.5" />
                    )}
                  </button>
                )}
                
                <div className="flex items-center gap-2">
                  <Volume2 className="h-4 w-4 text-primary-500" />
                  <p className="text-primary-700 text-base font-normal leading-normal truncate">
                    Chapter {chapter.number}.wav
                  </p>
                </div>
                
                {chapter.verification_passed ? (
                  <CheckCircle className="h-4 w-4 text-green-500" />
                ) : (
                  <XCircle className="h-4 w-4 text-red-500" />
                )}
                
                {chapter.duration_ms > 0 && (
                  <span className="text-xs text-primary-500">
                    {formatDuration(chapter.duration_ms)}
                  </span>
                )}
              </div>
              
              <div className="shrink-0 flex gap-2">
                {chapter.text_file && (
                  <a
                    href={chapter.text_file}
                    download
                    className="flex items-center justify-center w-8 h-8 rounded bg-primary-100 text-primary-700 hover:bg-primary-200 transition-colors"
                    title="Download text file"
                  >
                    <FileText className="h-4 w-4" />
                  </a>
                )}
                
                {chapter.audio_file && (
                  <a
                    href={chapter.audio_file}
                    download
                    className="flex min-w-[84px] max-w-[480px] cursor-pointer items-center justify-center overflow-hidden rounded-lg h-8 px-4 bg-primary-100 text-primary-700 text-sm font-medium leading-normal hover:bg-primary-200 transition-colors"
                  >
                    <Download className="h-4 w-4 mr-2" />
                    <span className="truncate">Download</span>
                  </a>
                )}
              </div>
            </div>
          </div>
        ))}

        {/* Download All Button */}
        <div className="flex px-4 py-3 justify-end">
          <button
            onClick={handleDownloadAll}
            className="flex min-w-[84px] max-w-[480px] cursor-pointer items-center justify-center overflow-hidden rounded-lg h-10 px-4 bg-primary-600 text-primary-50 text-sm font-bold leading-normal tracking-[0.015em] hover:bg-primary-700 transition-colors"
          >
            <Download className="h-4 w-4 mr-2" />
            <span className="truncate">Download All Chapters (ZIP)</span>
          </button>
        </div>

        {/* Processing Details */}
        <div className="px-4 py-4">
          <details className="bg-primary-50 rounded-lg">
            <summary className="p-4 cursor-pointer text-primary-700 font-medium">
              View Processing Details
            </summary>
            <div className="px-4 pb-4 text-sm text-primary-600">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="font-medium">Job ID:</span> {job.job_id}
                </div>
                <div>
                  <span className="font-medium">Status:</span> {job.status}
                </div>
                {job.start_time && (
                  <div>
                    <span className="font-medium">Started:</span> {new Date(job.start_time).toLocaleString()}
                  </div>
                )}
                {job.end_time && (
                  <div>
                    <span className="font-medium">Completed:</span> {new Date(job.end_time).toLocaleString()}
                  </div>
                )}
              </div>
            </div>
          </details>
        </div>
      </div>
    </div>
  );
};