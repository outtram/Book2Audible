import React, { useState, useEffect, useRef, useCallback } from 'react';
import { X, Play, Pause, SkipBack, SkipForward, Volume2, Settings, RefreshCcw } from 'lucide-react';

interface WordTiming {
  word_index: number;
  word_text: string;
  start_time: number;
  end_time: number;
  confidence: number;
}

interface ChunkBoundary {
  chunk_id: number;
  chunk_number: number;
  title: string;
  start_char: number;
  end_char: number;
  start_time: number;
  end_time: number;
  orpheus_params: {
    voice: string;
    temperature: number;
    speed: number;
  };
}

interface AudioSyncData {
  chapter_id: number;
  chapter_title: string;
  audio_url: string;
  full_text: string;
  word_timings: WordTiming[];
  chunk_boundaries: ChunkBoundary[];
  reprocessing_history: any[];
  total_chunks: number;
  total_duration: number;
}

interface SynchronizedAudioPlayerProps {
  chapterId: number;
  onClose: () => void;
}

export const SynchronizedAudioPlayer: React.FC<SynchronizedAudioPlayerProps> = ({ 
  chapterId, 
  onClose 
}) => {
  const [syncData, setSyncData] = useState<AudioSyncData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [currentWordIndex, setCurrentWordIndex] = useState(-1);
  const [currentChunkId, setCurrentChunkId] = useState<number | null>(null);
  const [playbackRate, setPlaybackRate] = useState(1.0);
  const [selectedChunk, setSelectedChunk] = useState<ChunkBoundary | null>(null);

  const audioRef = useRef<HTMLAudioElement>(null);
  const textContainerRef = useRef<HTMLDivElement>(null);

  // Load sync data
  useEffect(() => {
    const loadSyncData = async () => {
      try {
        setLoading(true);
        const response = await fetch(`/api/chapters/${chapterId}/audio-sync-data`);
        if (!response.ok) throw new Error('Failed to load sync data');
        const data = await response.json();
        setSyncData(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    loadSyncData();
  }, [chapterId]);

  // Audio event handlers
  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration);
    }
  };

  const handleTimeUpdate = useCallback(() => {
    if (audioRef.current) {
      const time = audioRef.current.currentTime;
      setCurrentTime(time);

      // Find current word
      if (syncData?.word_timings) {
        const wordIndex = syncData.word_timings.findIndex(
          (word, index) => {
            const nextWord = syncData.word_timings[index + 1];
            return time >= word.start_time && (!nextWord || time < nextWord.start_time);
          }
        );
        setCurrentWordIndex(wordIndex);

        // Auto-scroll to current word
        if (wordIndex >= 0 && textContainerRef.current) {
          const wordElement = textContainerRef.current.querySelector(
            `[data-word-index="${wordIndex}"]`
          );
          if (wordElement) {
            wordElement.scrollIntoView({ 
              behavior: 'smooth', 
              block: 'center',
              inline: 'nearest'
            });
          }
        }
      }

      // Find current chunk
      if (syncData?.chunk_boundaries) {
        const chunk = syncData.chunk_boundaries.find(
          chunk => time >= chunk.start_time && time <= chunk.end_time
        );
        setCurrentChunkId(chunk?.chunk_id || null);
      }
    }
  }, [syncData]);

  const togglePlayPause = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const seekTo = (time: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  const skip = (seconds: number) => {
    if (audioRef.current) {
      const newTime = Math.max(0, Math.min(duration, currentTime + seconds));
      seekTo(newTime);
    }
  };

  const jumpToWord = (wordIndex: number) => {
    if (syncData?.word_timings[wordIndex]) {
      seekTo(syncData.word_timings[wordIndex].start_time);
    }
  };

  const jumpToChunk = (chunk: ChunkBoundary) => {
    seekTo(chunk.start_time);
    setSelectedChunk(chunk);
  };

  const changePlaybackRate = (rate: number) => {
    setPlaybackRate(rate);
    if (audioRef.current) {
      audioRef.current.playbackRate = rate;
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const renderText = () => {
    if (!syncData?.full_text) return (
      <div className="p-4 h-96 overflow-y-auto bg-gray-50 border rounded-lg">
        <div className="text-center text-gray-500">No text data available</div>
      </div>
    );

    const text = syncData.full_text;
    const words = text.split(/\s+/);
    
    return (
      <div ref={textContainerRef} className="text-container p-4 h-96 overflow-y-auto bg-gray-50 border rounded-lg">
        <div className="text-lg leading-relaxed">
          {words.map((word, index) => {
            const isCurrentWord = index === currentWordIndex;
            const isHighlighted = index <= currentWordIndex;
            
            return (
              <span
                key={index}
                data-word-index={index}
                onClick={() => jumpToWord(index)}
                className={`cursor-pointer px-1 py-0.5 rounded transition-colors ${
                  isCurrentWord 
                    ? 'bg-blue-500 text-white' 
                    : isHighlighted 
                    ? 'bg-blue-100 text-blue-900' 
                    : 'hover:bg-gray-200'
                }`}
              >
                {word}{' '}
              </span>
            );
          })}
        </div>
        <div className="text-xs text-gray-500 mt-2">
          Total words: {words.length} | Current: {currentWordIndex + 1}
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto bg-white rounded-lg shadow-lg overflow-hidden">
        <div className="bg-primary-600 text-white p-4 flex items-center justify-between">
          <h2 className="text-xl font-bold">Loading Synchronized Player...</h2>
          <button onClick={onClose} className="p-2 hover:bg-primary-700 rounded-lg">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="p-6 flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
          <span className="ml-3 text-primary-600">Loading audio and timing data...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-6xl mx-auto bg-white rounded-lg shadow-lg overflow-hidden">
        <div className="bg-red-600 text-white p-4 flex items-center justify-between">
          <h2 className="text-xl font-bold">Error Loading Player</h2>
          <button onClick={onClose} className="p-2 hover:bg-red-700 rounded-lg">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="p-6 text-center text-red-600">
          <p>{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto bg-white rounded-lg shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-primary-600 text-white p-4 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">Synchronized Audio Player</h2>
          <p className="text-primary-100">
            {syncData?.chapter_title} • {syncData?.total_chunks} chunks
          </p>
        </div>
        <button
          onClick={onClose}
          className="p-2 hover:bg-primary-700 rounded-lg transition-colors"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="p-6">
        {/* Audio Element */}
        <audio
          ref={audioRef}
          src={syncData?.audio_url}
          onLoadedMetadata={handleLoadedMetadata}
          onTimeUpdate={handleTimeUpdate}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onEnded={() => setIsPlaying(false)}
        />

        {/* Audio Controls */}
        <div className="bg-gray-100 p-4 rounded-lg mb-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-4">
              <button
                onClick={() => skip(-10)}
                className="p-2 bg-gray-200 hover:bg-gray-300 rounded-lg"
                title="Skip back 10 seconds"
              >
                <SkipBack className="h-5 w-5" />
              </button>
              
              <button
                onClick={togglePlayPause}
                className="p-3 bg-primary-600 hover:bg-primary-700 text-white rounded-lg"
              >
                {isPlaying ? <Pause className="h-6 w-6" /> : <Play className="h-6 w-6" />}
              </button>
              
              <button
                onClick={() => skip(10)}
                className="p-2 bg-gray-200 hover:bg-gray-300 rounded-lg"
                title="Skip forward 10 seconds"
              >
                <SkipForward className="h-5 w-5" />
              </button>
            </div>

            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-600">
                {formatTime(currentTime)} / {formatTime(duration)}
              </span>
              
              <select
                value={playbackRate}
                onChange={(e) => changePlaybackRate(parseFloat(e.target.value))}
                className="px-2 py-1 border rounded text-sm"
              >
                <option value="0.5">0.5x</option>
                <option value="0.75">0.75x</option>
                <option value="1">1x</option>
                <option value="1.25">1.25x</option>
                <option value="1.5">1.5x</option>
                <option value="2">2x</option>
              </select>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="relative">
            <div className="w-full bg-gray-300 rounded-full h-2">
              <div
                className="bg-primary-600 h-2 rounded-full transition-all duration-200"
                style={{ width: `${(currentTime / duration) * 100}%` }}
              />
            </div>
            <input
              type="range"
              min="0"
              max={duration}
              value={currentTime}
              onChange={(e) => seekTo(parseFloat(e.target.value))}
              className="absolute inset-0 w-full h-2 opacity-0 cursor-pointer"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Text Display with Word Highlighting */}
          <div className="lg:col-span-2">
            <h3 className="text-lg font-semibold mb-3">
              📄 Text (Click any word to jump to audio position)
            </h3>
            {renderText()}
          </div>

          {/* Chunk Information Panel */}
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-semibold mb-3">🎵 Chunks</h3>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {syncData?.chunk_boundaries.map((chunk) => (
                  <div
                    key={chunk.chunk_id}
                    onClick={() => jumpToChunk(chunk)}
                    className={`p-3 border rounded-lg cursor-pointer transition-all ${
                      currentChunkId === chunk.chunk_id
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-gray-300 hover:border-primary-300 hover:bg-gray-50'
                    }`}
                  >
                    <div className="font-medium">Chunk {chunk.chunk_number}</div>
                    <div className="text-sm text-gray-600">
                      {formatTime(chunk.start_time)} - {formatTime(chunk.end_time)}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Current Chunk Details */}
            {selectedChunk && (
              <div className="border-t pt-4">
                <h4 className="font-semibold mb-2">⚙️ Current Chunk Settings</h4>
                <div className="space-y-2 text-sm">
                  <div>
                    <span className="font-medium">Voice:</span> {selectedChunk.orpheus_params.voice}
                  </div>
                  <div>
                    <span className="font-medium">Temperature:</span> {selectedChunk.orpheus_params.temperature}
                  </div>
                  <div>
                    <span className="font-medium">Speed:</span> {selectedChunk.orpheus_params.speed}
                  </div>
                </div>
              </div>
            )}

            {/* Stats */}
            <div className="border-t pt-4">
              <h4 className="font-semibold mb-2">📊 Statistics</h4>
              <div className="space-y-1 text-sm">
                <div>Total Words: {syncData?.word_timings.length || 0}</div>
                <div>Current Word: {currentWordIndex + 1}</div>
                <div>Current Chunk: {currentChunkId || 'None'}</div>
                <div>Duration: {formatTime(duration)}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer Info */}
        <div className="mt-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
          <h4 className="font-medium text-blue-900 mb-2">💡 How to Use</h4>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>• <strong>Click any word</strong> in the text to jump to that audio position</li>
            <li>• <strong>Click chunk panels</strong> to jump to specific chunks</li>
            <li>• <strong>Use playback controls</strong> for standard audio playback</li>
            <li>• <strong>Change speed</strong> to adjust playback rate</li>
            <li>• <strong>Words are highlighted</strong> in real-time as audio plays</li>
          </ul>
        </div>
      </div>
    </div>
  );
};