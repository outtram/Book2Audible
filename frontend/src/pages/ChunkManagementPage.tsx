import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Settings, RefreshCcw, Plus, X, Check, AlertTriangle, Volume2, Play, Pause, FileText, ExternalLink, Music } from 'lucide-react';
// Import both players - SimpleSyncPlayer for fallback, SynchronizedAudioPlayer for full features
import { SimpleSyncPlayer } from '../components/SimpleSyncPlayer';
import { SynchronizedAudioPlayer } from '../components/SynchronizedAudioPlayer';

interface Chunk {
  chunk_id: number;
  chunk_number: number;
  status: string;
  verification_score: number | null;
  processing_time: number | null;
  error_message: string | null;
  has_audio: boolean;
  text_length: number;
  word_count: number;
  needs_attention: boolean;
}

interface ChapterStatus {
  chapter_id: number;
  chapter_number: number;
  chapter_title: string;
  chunks_directory: string;
  summary: {
    total_chunks: number;
    completed_chunks: number;
    failed_chunks: number;
    reprocess_chunks: number;
    avg_verification_score: number;
    total_processing_time: number;
  };
  chunks: Chunk[];
}

const api = {
  getChapterStatus: async (chapterId: number): Promise<ChapterStatus> => {
    const response = await fetch(`/api/chapters/${chapterId}/status`);
    if (!response.ok) throw new Error('Failed to fetch chapter status');
    return response.json();
  },

  reprocessChunk: async (chunkId: number) => {
    const response = await fetch(`/api/chunks/${chunkId}/reprocess`, { method: 'POST' });
    if (!response.ok) throw new Error('Failed to reprocess chunk');
    return response.json();
  },

  reprocessFailed: async (chapterId: number) => {
    const response = await fetch(`/api/chapters/${chapterId}/reprocess-failed`, { method: 'POST' });
    if (!response.ok) throw new Error('Failed to reprocess failed chunks');
    return response.json();
  },

  restitchChapter: async (chapterId: number, excludeChunks?: number[]) => {
    const url = `/api/chapters/${chapterId}/restitch`;
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ exclude_chunks: excludeChunks })
    });
    if (!response.ok) throw new Error('Failed to restitch chapter');
    return response.json();
  },

  getCandidates: async (chapterId: number) => {
    const response = await fetch(`/api/chapters/${chapterId}/candidates`);
    if (!response.ok) throw new Error('Failed to get candidates');
    return response.json();
  },

  getChunkText: async (chunkId: number) => {
    const response = await fetch(`/api/chunks/${chunkId}/text`);
    if (!response.ok) throw new Error('Failed to get chunk text');
    return response.json();
  },

  openChunkFile: async (chunkId: number) => {
    const response = await fetch(`/api/chunks/${chunkId}/open-file`);
    if (!response.ok) throw new Error('Failed to open chunk file');
    return response.json();
  },

  getOrpheusParams: async (chunkId: number) => {
    const response = await fetch(`/api/chunks/${chunkId}/orpheus-params`);
    if (!response.ok) throw new Error('Failed to get Orpheus parameters');
    return response.json();
  }
};

export const ChunkManagementPage: React.FC = () => {
  const { chapterId } = useParams<{ chapterId: string }>();
  const [chapterStatus, setChapterStatus] = useState<ChapterStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState<Set<number>>(new Set());
  const [selectedChunks, setSelectedChunks] = useState<Set<number>>(new Set());
  const [playingChunk, setPlayingChunk] = useState<number | null>(null);
  const [textPreview, setTextPreview] = useState<{ chunkId: number; text: string } | null>(null);
  const [audioElements, setAudioElements] = useState<Map<number, HTMLAudioElement>>(new Map());
  const [showSyncPlayer, setShowSyncPlayer] = useState(false);
  const [useFullSyncPlayer, setUseFullSyncPlayer] = useState(true); // Toggle between Simple and Full player
  const [orpheusParams, setOrpheusParams] = useState<{ chunkId: number; params: any } | null>(null);

  useEffect(() => {
    if (chapterId) {
      loadChapterStatus();
    }
  }, [chapterId]);

  const loadChapterStatus = async () => {
    try {
      setLoading(true);
      const status = await api.getChapterStatus(parseInt(chapterId!));
      setChapterStatus(status);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReprocessChunk = async (chunkId: number) => {
    try {
      setProcessing(prev => new Set(prev).add(chunkId));
      await api.reprocessChunk(chunkId);
      // Reload after a delay to see updated status
      setTimeout(loadChapterStatus, 2000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setProcessing(prev => {
        const newSet = new Set(prev);
        newSet.delete(chunkId);
        return newSet;
      });
    }
  };

  const handleReprocessFailed = async () => {
    try {
      setLoading(true);
      await api.reprocessFailed(chapterStatus!.chapter_id);
      setTimeout(loadChapterStatus, 3000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRestitch = async () => {
    try {
      setLoading(true);
      const excludeList = Array.from(selectedChunks);
      await api.restitchChapter(chapterStatus!.chapter_id, excludeList.length > 0 ? excludeList : undefined);
      setSelectedChunks(new Set());
      setTimeout(loadChapterStatus, 2000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleChunkSelection = (chunkId: number) => {
    setSelectedChunks(prev => {
      const newSet = new Set(prev);
      if (newSet.has(chunkId)) {
        newSet.delete(chunkId);
      } else {
        newSet.add(chunkId);
      }
      return newSet;
    });
  };

  const playAudio = async (chunkId: number) => {
    try {
      // Stop currently playing audio
      if (playingChunk && audioElements.has(playingChunk)) {
        const currentAudio = audioElements.get(playingChunk)!;
        currentAudio.pause();
        currentAudio.currentTime = 0;
      }

      if (playingChunk === chunkId) {
        setPlayingChunk(null);
        return;
      }

      // Create or get audio element
      let audio = audioElements.get(chunkId);
      if (!audio) {
        audio = new Audio(`/api/chunks/${chunkId}/audio`);
        audio.addEventListener('ended', () => setPlayingChunk(null));
        audio.addEventListener('error', () => {
          setError('Failed to load audio');
          setPlayingChunk(null);
        });
        setAudioElements(prev => new Map(prev).set(chunkId, audio!));
      }

      setPlayingChunk(chunkId);
      await audio.play();
    } catch (err) {
      setError('Failed to play audio');
      setPlayingChunk(null);
    }
  };

  const showTextPreview = async (chunkId: number) => {
    try {
      const response = await api.getChunkText(chunkId);
      setTextPreview({ chunkId, text: response.text });
    } catch (err: any) {
      setError(err.message);
    }
  };

  const openTextFile = async (chunkId: number) => {
    try {
      await api.openChunkFile(chunkId);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const showOrpheusParams = async (chunkId: number) => {
    try {
      const params = await api.getOrpheusParams(chunkId);
      setOrpheusParams({ chunkId, params });
    } catch (err: any) {
      setError(err.message);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'text-green-600 bg-green-100';
      case 'failed': return 'text-red-600 bg-red-100';
      case 'processing': return 'text-blue-600 bg-blue-100';
      case 'needs_reprocess': return 'text-yellow-600 bg-yellow-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusIcon = (chunk: Chunk) => {
    if (processing.has(chunk.chunk_id)) {
      return <RefreshCcw className="h-4 w-4 animate-spin" />;
    }
    
    switch (chunk.status) {
      case 'completed': return chunk.needs_attention ? <AlertTriangle className="h-4 w-4" /> : <Check className="h-4 w-4" />;
      case 'failed': return <X className="h-4 w-4" />;
      case 'processing': return <RefreshCcw className="h-4 w-4 animate-spin" />;
      default: return <Settings className="h-4 w-4" />;
    }
  };

  if (loading && !chapterStatus) {
    return (
      <div className="px-40 flex flex-1 justify-center py-5">
        <div className="layout-content-container flex flex-col w-[960px] max-w-[960px] py-5">
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            <span className="ml-3 text-primary-600">Loading chunk details...</span>
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
              onClick={loadChapterStatus}
              className="mt-4 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!chapterStatus) {
    return <div>Chapter not found</div>;
  }

  const summary = chapterStatus.summary;
  const needsAttention = chapterStatus.chunks.filter(c => c.needs_attention);

  return (
    <div className="px-40 flex flex-1 justify-center py-5">
      <div className="layout-content-container flex flex-col w-[960px] max-w-[960px] py-5">
        {/* Header */}
        <div className="flex flex-wrap justify-between gap-3 p-4">
          <div className="flex min-w-72 flex-col gap-3">
            <p className="text-primary-700 tracking-light text-[32px] font-bold leading-tight">
              Chapter {chapterStatus.chapter_number}: {chapterStatus.chapter_title}
            </p>
            <p className="text-primary-500 text-sm font-normal leading-normal">
              Manage individual chunks for cost-effective reprocessing
            </p>
          </div>
        </div>

        {/* Summary Stats */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 p-4 mb-6">
          <div className="bg-white border border-primary-200 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-primary-700">{summary.total_chunks}</div>
            <div className="text-sm text-primary-500">Total Chunks</div>
          </div>
          <div className="bg-white border border-primary-200 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-green-600">{summary.completed_chunks}</div>
            <div className="text-sm text-primary-500">Completed</div>
          </div>
          <div className="bg-white border border-primary-200 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-red-600">{summary.failed_chunks}</div>
            <div className="text-sm text-primary-500">Failed</div>
          </div>
          <div className="bg-white border border-primary-200 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-yellow-600">{needsAttention.length}</div>
            <div className="text-sm text-primary-500">Need Attention</div>
          </div>
          <div className="bg-white border border-primary-200 rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-primary-600">
              {summary.avg_verification_score ? `${(summary.avg_verification_score * 100).toFixed(1)}%` : 'N/A'}
            </div>
            <div className="text-sm text-primary-500">Avg Accuracy</div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3 p-4 mb-6">
          <button
            onClick={handleReprocessFailed}
            disabled={loading || needsAttention.length === 0}
            className="flex items-center gap-2 px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCcw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Reprocess Failed ({needsAttention.length})
          </button>
          
          <button
            onClick={handleRestitch}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Volume2 className="h-4 w-4" />
            Restitch Audio {selectedChunks.size > 0 && `(Exclude ${selectedChunks.size})`}
          </button>
          
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSyncPlayer(true)}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Music className="h-4 w-4" />
              Synchronized Player {useFullSyncPlayer ? '(Full)' : '(Preview)'}
            </button>
            
            <button
              onClick={() => setUseFullSyncPlayer(!useFullSyncPlayer)}
              className="px-3 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 text-sm"
              title={`Switch to ${useFullSyncPlayer ? 'Preview' : 'Full'} player`}
            >
              {useFullSyncPlayer ? '📊' : '🔧'}
            </button>
          </div>
          
          <button
            onClick={loadChapterStatus}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCcw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Chunks List */}
        <div className="bg-white border border-primary-200 rounded-lg overflow-hidden">
          <div className="bg-primary-50 px-4 py-3 border-b border-primary-200">
            <h3 className="text-lg font-medium text-primary-700">Chunks ({chapterStatus.chunks.length})</h3>
          </div>
          
          <div className="divide-y divide-primary-100">
            {chapterStatus.chunks.map((chunk, arrayIndex) => (
              <div 
                key={chunk.chunk_id} 
                className={`flex items-center justify-between p-4 hover:bg-primary-25 ${
                  selectedChunks.has(chunk.chunk_id) ? 'bg-red-50' : ''
                }`}
              >
                <div className="flex items-center gap-4">
                  <input
                    type="checkbox"
                    checked={selectedChunks.has(chunk.chunk_id)}
                    onChange={() => toggleChunkSelection(chunk.chunk_id)}
                    className="rounded border-primary-300"
                    title="Select to exclude from stitching"
                  />
                  
                  <div className="flex items-center gap-2 min-w-[120px]">
                    <span className="font-medium text-primary-700">Chunk {chunk.chunk_number}</span>
                    <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(chunk.status)}`}>
                      {getStatusIcon(chunk)}
                      {chunk.status}
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-6 text-sm text-primary-600">
                    <span>{chunk.word_count} words</span>
                    {chunk.verification_score && (
                      <span className={chunk.verification_score < 0.85 ? 'text-red-600 font-medium' : ''}>
                        {(chunk.verification_score * 100).toFixed(1)}% accuracy
                      </span>
                    )}
                    {chunk.has_audio && <Volume2 className="h-4 w-4 text-green-600" />}
                  </div>
                </div>
                
                <div className="flex items-center gap-2">
                  {chunk.needs_attention && (
                    <span className="text-xs px-2 py-1 bg-yellow-100 text-yellow-800 rounded">
                      Needs attention
                    </span>
                  )}
                  
                  {/* Audio playback button */}
                  {chunk.has_audio && (
                    <button
                      onClick={() => playAudio(chunk.chunk_id)}
                      className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                      title="Play audio"
                    >
                      {playingChunk === chunk.chunk_id ? (
                        <Pause className="h-4 w-4" />
                      ) : (
                        <Play className="h-4 w-4" />
                      )}
                    </button>
                  )}
                  
                  {/* Text preview button */}
                  <button
                    onClick={() => showTextPreview(chunk.chunk_id)}
                    className="p-2 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                    title="Preview text"
                  >
                    <FileText className="h-4 w-4" />
                  </button>
                  
                  {/* Open file button */}
                  <button
                    onClick={() => openTextFile(chunk.chunk_id)}
                    className="p-2 text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                    title="Open text file in editor"
                  >
                    <ExternalLink className="h-4 w-4" />
                  </button>
                  
                  {/* Orpheus parameters button */}
                  <button
                    onClick={() => showOrpheusParams(chunk.chunk_id)}
                    className="p-2 text-orange-600 hover:bg-orange-50 rounded-lg transition-colors"
                    title="View Orpheus TTS parameters"
                  >
                    <Settings className="h-4 w-4" />
                  </button>
                  
                  <button
                    onClick={() => handleReprocessChunk(chunk.chunk_id)}
                    disabled={processing.has(chunk.chunk_id)}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm bg-primary-100 text-primary-700 rounded-lg hover:bg-primary-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <RefreshCcw className={`h-3 w-3 ${processing.has(chunk.chunk_id) ? 'animate-spin' : ''}`} />
                    Reprocess
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Help Text */}
        <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <h4 className="font-medium text-blue-900 mb-2">💡 Cost-Effective Reprocessing Tips</h4>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>• Select individual chunks to reprocess only problematic audio (saves ~94% cost)</li>
            <li>• Use "Reprocess Failed" to fix all chunks with issues at once</li>
            <li>• Check chunks to exclude them from final stitching if they can't be fixed</li>
            <li>• Chunks with accuracy &lt; 85% are automatically flagged for attention</li>
            <li>• 🎵 Play button: Listen to chunk audio directly in browser</li>
            <li>• 📄 Text button: Preview chunk text content</li>
            <li>• 🔗 External button: Open text file in your default editor</li>
            <li>• ⚙️ Settings button: View Orpheus TTS parameters (voice, temperature, speed)</li>
            <li>• 🎼 Synchronized Player: Word-level audio-text synchronization (click 📊/🔧 to toggle Full/Preview mode)</li>
          </ul>
        </div>
      </div>

      {/* Text Preview Modal */}
      {textPreview && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-primary-700">
                Chunk {chapterStatus.chunks.find(c => c.chunk_id === textPreview.chunkId)?.chunk_number || textPreview.chunkId} Text Content
              </h3>
              <button
                onClick={() => setTextPreview(null)}
                className="p-2 text-gray-400 hover:text-gray-600 rounded-lg"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="bg-gray-50 p-4 rounded-lg border">
              <pre className="whitespace-pre-wrap text-sm text-gray-700">
                {textPreview.text}
              </pre>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => openTextFile(textPreview.chunkId)}
                className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
              >
                <ExternalLink className="h-4 w-4" />
                Open in Editor
              </button>
              <button
                onClick={() => setTextPreview(null)}
                className="px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Orpheus Parameters Modal */}
      {orpheusParams && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-primary-700">
                Chunk {chapterStatus.chunks.find(c => c.chunk_id === orpheusParams.chunkId)?.chunk_number || orpheusParams.chunkId} - Orpheus Parameters
              </h3>
              <button
                onClick={() => setOrpheusParams(null)}
                className="p-2 text-gray-400 hover:text-gray-600 rounded-lg"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Voice</label>
                  <div className="px-3 py-2 bg-gray-50 border rounded-md text-sm">
                    {orpheusParams.params.voice || 'tara'}
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Temperature</label>
                  <div className="px-3 py-2 bg-gray-50 border rounded-md text-sm">
                    {orpheusParams.params.temperature || 0.7}
                  </div>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Speed</label>
                <div className="px-3 py-2 bg-gray-50 border rounded-md text-sm">
                  {orpheusParams.params.speed || 1.0}
                </div>
              </div>
              {orpheusParams.params.additional && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Additional Parameters</label>
                  <div className="px-3 py-2 bg-gray-50 border rounded-md text-sm">
                    <pre className="text-xs">{JSON.stringify(orpheusParams.params.additional, null, 2)}</pre>
                  </div>
                </div>
              )}
            </div>
            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setOrpheusParams(null)}
                className="px-4 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Synchronized Audio Player Modal */}
      {showSyncPlayer && chapterStatus && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="w-full max-w-6xl h-full max-h-[90vh] overflow-y-auto">
            {useFullSyncPlayer ? (
              <SynchronizedAudioPlayer 
                chapterId={chapterStatus.chapter_id}
                onClose={() => setShowSyncPlayer(false)}
              />
            ) : (
              <SimpleSyncPlayer 
                chapterId={chapterStatus.chapter_id}
                onClose={() => setShowSyncPlayer(false)}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
};