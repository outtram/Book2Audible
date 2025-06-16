import React, { useState, useEffect, useRef, useCallback } from 'react';
import { X, Play, Pause, SkipBack, SkipForward, Volume2, Settings, RefreshCcw } from 'lucide-react';
import { VERSION } from '../version';

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
  audio_file_path?: string;
  audio_filename?: string;
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
  stitched_audio_filename?: string;
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
  const [manualChunkSelection, setManualChunkSelection] = useState<{chunkId: number, timestamp: number} | null>(null);

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
        // Use API duration instead of HTML5 audio duration for accuracy
        if (data.total_duration) {
          setDuration(data.total_duration);
        }
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
    // Only use HTML5 audio duration if we don't have API duration
    if (audioRef.current && (!syncData || !syncData.total_duration)) {
      setDuration(audioRef.current.duration);
    }
  };

  const handleTimeUpdate = useCallback(() => {
    if (audioRef.current) {
      const time = audioRef.current.currentTime;
      setCurrentTime(time);

      // Find current word with improved synchronization
      if (syncData?.word_timings) {
        // Use chunk boundaries as synchronization checkpoints to reduce drift
        const currentChunk = syncData.chunk_boundaries.find(
          chunk => time >= chunk.start_time && time <= chunk.end_time
        );
        
        let wordIndex = -1;
        
        if (currentChunk) {
          // Calculate word position within the current chunk for better accuracy
          const chunkProgress = (time - currentChunk.start_time) / (currentChunk.end_time - currentChunk.start_time);
          const chunkStartChar = currentChunk.start_char;
          const chunkEndChar = currentChunk.end_char;
          const chunkLength = chunkEndChar - chunkStartChar;
          const estimatedCharPosition = chunkStartChar + (chunkProgress * chunkLength);
          
          // Find the word closest to this character position
          const text = syncData.full_text;
          let charCount = 0;
          const words = text.split(/\s+/);
          
          for (let i = 0; i < words.length; i++) {
            charCount += words[i].length + 1; // +1 for space
            if (charCount >= estimatedCharPosition) {
              wordIndex = i;
              break;
            }
          }
          
          // Fallback to time-based calculation if character-based fails
          if (wordIndex === -1) {
            wordIndex = syncData.word_timings.findIndex(
              (word, index) => {
                const nextWord = syncData.word_timings[index + 1];
                return time >= word.start_time && (!nextWord || time < nextWord.start_time);
              }
            );
          }
        } else {
          // Fallback to original time-based method
          wordIndex = syncData.word_timings.findIndex(
            (word, index) => {
              const nextWord = syncData.word_timings[index + 1];
              return time >= word.start_time && (!nextWord || time < nextWord.start_time);
            }
          );
        }
        
        // Log timing drift every 10 seconds for debugging
        if (Math.floor(time) % 10 === 0 && Math.floor(time) !== Math.floor(currentTime)) {
          const expectedWordAtTime = Math.floor((time / (syncData.total_duration || 1)) * syncData.word_timings.length);
          const actualWordIndex = wordIndex >= 0 ? wordIndex : -1;
          const drift = actualWordIndex - expectedWordAtTime;
          
          console.log('⏱️ TIMING SYNC DEBUG:', {
            current_time: time.toFixed(2),
            expected_word_index: expectedWordAtTime,
            actual_word_index: actualWordIndex,
            drift_words: drift,
            total_words: syncData.word_timings.length,
            total_duration: syncData.total_duration,
            current_chunk: currentChunk?.chunk_number || 'none'
          });
        }
        
        // Check if we should respect manual selection for word updates too
        const now = Date.now();
        const shouldRespectManualWordSelection = manualChunkSelection &&
          (now - manualChunkSelection.timestamp < 5000);
        
        if (!shouldRespectManualWordSelection) {
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
        } else {
          console.log('🚫 BLOCKING WORD UPDATE - Respecting manual chunk selection', {
            current_word_index: currentWordIndex,
            would_set_to: wordIndex,
            manual_selection_age_ms: now - manualChunkSelection.timestamp
          });
        }
      }

      // Find current chunk
      if (syncData?.chunk_boundaries) {
        const chunk = syncData.chunk_boundaries.find(
          chunk => time >= chunk.start_time && time <= chunk.end_time
        );
        const newChunkId = chunk?.chunk_id || null;
        
        // Check if we should respect manual selection (within 5 seconds of manual click)
        const now = Date.now();
        const timeSinceManualSelection = manualChunkSelection ? now - manualChunkSelection.timestamp : 0;
        const shouldRespectManualSelection = manualChunkSelection &&
          (timeSinceManualSelection < 5000) &&
          manualChunkSelection.chunkId === currentChunkId;
        
        // Debug the blocking logic
        if (manualChunkSelection && newChunkId !== currentChunkId) {
          console.log('🔍 CHUNK BLOCKING ANALYSIS:', {
            has_manual_selection: !!manualChunkSelection,
            manual_chunk_id: manualChunkSelection?.chunkId,
            current_chunk_id: currentChunkId,
            new_chunk_id: newChunkId,
            time_since_manual_ms: timeSinceManualSelection,
            within_time_limit: timeSinceManualSelection < 5000,
            chunk_ids_match: manualChunkSelection?.chunkId === currentChunkId,
            should_respect: shouldRespectManualSelection,
            audio_time: time.toFixed(2)
          });
        }
        
        // Clear manual selection if audio has moved significantly beyond the selected chunk
        if (manualChunkSelection && currentChunkId) {
          const currentChunk = syncData.chunk_boundaries.find(c => c.chunk_id === currentChunkId);
          if (currentChunk && (time < currentChunk.start_time - 1 || time > currentChunk.end_time + 1)) {
            console.log('🧹 CLEARING MANUAL SELECTION - Audio moved beyond selected chunk');
            setManualChunkSelection(null);
          }
        }
        
        // Log chunk changes to detect conflicts with manual selection
        if (newChunkId !== currentChunkId) {
          console.log('🔄 AUTO CHUNK UPDATE v2.1.3:', {
            audio_time: time.toFixed(2),
            old_chunk_id: currentChunkId,
            new_chunk_id: newChunkId,
            new_chunk_number: chunk?.chunk_number || 'none',
            old_chunk_number: syncData.chunk_boundaries.find(c => c.chunk_id === currentChunkId)?.chunk_number || 'none',
            manual_selection_active: shouldRespectManualSelection,
            manual_selection_age_ms: manualChunkSelection ? now - manualChunkSelection.timestamp : 'none',
            trigger: 'handleTimeUpdate',
            will_update: !shouldRespectManualSelection
          });
        }
        
        // Only update if not respecting manual selection
        if (!shouldRespectManualSelection) {
          setCurrentChunkId(newChunkId);
          
          // Log current WAV file information for debugging
          if (newChunkId && syncData?.chunk_boundaries) {
            const currentChunk = syncData.chunk_boundaries.find(c => c.chunk_id === newChunkId);
            if (currentChunk) {
              console.log('🎧 CURRENT WAV FILE DEBUG:', {
                chunk_id: newChunkId,
                chunk_number: currentChunk.chunk_number,
                actual_audio_file_path: currentChunk.audio_file_path,
                audio_filename: currentChunk.audio_filename,
                audio_time: time.toFixed(2),
                chunk_start: currentChunk.start_time,
                chunk_end: currentChunk.end_time
              });
            }
          }
        } else {
          console.log('🚫 BLOCKING AUTO UPDATE - Respecting manual selection');
        }
      }
    }
  }, [syncData, currentTime]);

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
    console.log('🔧 CHUNK CLICK DEBUG v2.1.3:', {
      clicked_chunk_number: chunk.chunk_number,
      clicked_chunk_id: chunk.chunk_id,
      current_chunk_id_before: currentChunkId,
      will_set_to: chunk.chunk_id,
      chunk_start_time: chunk.start_time,
      chunk_end_time: chunk.end_time,
      current_audio_time: audioRef.current?.currentTime || 0
    });
    
    // Log all chunks for comparison
    if (syncData?.chunk_boundaries) {
      console.log('📋 ALL CHUNKS COMPARISON:', syncData.chunk_boundaries.map((c, idx) => ({
        array_index: idx,
        chunk_number: c.chunk_number,
        chunk_id: c.chunk_id,
        is_current: currentChunkId === c.chunk_id,
        start_time: c.start_time,
        end_time: c.end_time
      })));
    }
    
    // Track manual selection to prevent automatic override
    const now = Date.now();
    setManualChunkSelection({ chunkId: chunk.chunk_id, timestamp: now });
    
    // Seek to slightly after the chunk start to avoid boundary conflicts
    const seekTime = chunk.start_time + 0.1; // Add 100ms to ensure we're clearly in the target chunk
    seekTo(seekTime);
    setSelectedChunk(chunk);
    setCurrentChunkId(chunk.chunk_id);
    
    // Immediately update word highlighting to match the chunk start
    if (syncData?.word_timings && syncData?.full_text) {
      // Find the word that corresponds to the chunk start time
      let targetWordIndex = -1;
      
      // Method 1: Use character position mapping
      const chunkStartChar = chunk.start_char;
      const text = syncData.full_text;
      const words = text.split(/\s+/);
      let charCount = 0;
      
      for (let i = 0; i < words.length; i++) {
        if (charCount >= chunkStartChar) {
          targetWordIndex = i;
          break;
        }
        charCount += words[i].length + 1; // +1 for space
      }
      
      // Method 2: Fallback to time-based if character method fails
      if (targetWordIndex === -1) {
        targetWordIndex = syncData.word_timings.findIndex(
          (word, index) => {
            const nextWord = syncData.word_timings[index + 1];
            return chunk.start_time >= word.start_time && (!nextWord || chunk.start_time < nextWord.start_time);
          }
        );
      }
      
      if (targetWordIndex >= 0) {
        console.log('🎯 SETTING WORD INDEX:', {
          old_word_index: currentWordIndex,
          new_word_index: targetWordIndex,
          target_word: words[targetWordIndex]
        });
        
        setCurrentWordIndex(targetWordIndex);
        
        // Scroll to the target word
        setTimeout(() => {
          if (textContainerRef.current) {
            const wordElement = textContainerRef.current.querySelector(
              `[data-word-index="${targetWordIndex}"]`
            );
            console.log('🔍 WORD ELEMENT SEARCH:', {
              target_index: targetWordIndex,
              element_found: !!wordElement,
              element_text: wordElement?.textContent?.trim()
            });
            
            if (wordElement) {
              wordElement.scrollIntoView({
                behavior: 'smooth',
                block: 'center',
                inline: 'nearest'
              });
              console.log('📜 SCROLLED TO WORD:', targetWordIndex);
            }
          }
        }, 100); // Small delay to ensure DOM is updated
      }
      
      console.log('📝 WORD SYNC ON CHUNK CLICK:', {
        chunk_start_char: chunkStartChar,
        target_word_index: targetWordIndex,
        target_word: targetWordIndex >= 0 ? words[targetWordIndex] : 'not found',
        method_used: targetWordIndex >= 0 ? (charCount >= chunkStartChar ? 'character_mapping' : 'time_based') : 'failed'
      });
    }
    
    console.log('✅ CHUNK SET COMPLETE v2.1.3:', {
      chunk_number: chunk.chunk_number,
      new_current_chunk_id: chunk.chunk_id,
      audio_time_after_seek: chunk.start_time,
      manual_selection_timestamp: now
    });
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
            {syncData?.chapter_title} • {syncData?.total_chunks} chunks • v{VERSION.frontend}
          </p>
          <p className="text-primary-200 text-sm">
            🆔 Chapter ID: {chapterId} | 🎵 Stitched Audio: {syncData?.stitched_audio_filename || 'Loading...'}
          </p>
          {currentChunkId && syncData?.chunk_boundaries && (
            <p className="text-primary-200 text-xs font-mono break-all">
              🎧 Current WAV: {(() => {
                const currentChunk = syncData.chunk_boundaries.find(c => c.chunk_id === currentChunkId);
                return currentChunk?.audio_file_path || `chunk_${currentChunk?.chunk_number || 'unknown'}.wav`;
              })()}
            </p>
          )}
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
                {syncData?.chunk_boundaries.map((chunk, arrayIndex) => (
                  <div
                    key={chunk.chunk_id}
                    onClick={() => jumpToChunk(chunk)}
                    className={`p-3 border rounded-lg cursor-pointer transition-all ${
                      currentChunkId === chunk.chunk_id
                        ? 'border-primary-500 bg-primary-50'
                        : 'border-gray-300 hover:border-primary-300 hover:bg-gray-50'
                    }`}
                  >
                    <div className="font-medium">
                      Chunk {chunk.chunk_number}
                      <span className="text-xs text-gray-400 ml-2">
                        (ID: {chunk.chunk_id}, Idx: {arrayIndex})
                      </span>
                    </div>
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
                {currentChunkId && syncData?.chunk_boundaries && (
                  <div className="text-blue-600 font-medium">
                    <div className="font-semibold">🎧 Currently Playing:</div>
                    <div className="text-xs font-mono break-all mt-1 text-blue-800">
                      {(() => {
                        const currentChunk = syncData.chunk_boundaries.find(c => c.chunk_id === currentChunkId);
                        return currentChunk?.audio_file_path || `chunk_${currentChunk?.chunk_number || 'unknown'}.wav`;
                      })()}
                    </div>
                  </div>
                )}
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