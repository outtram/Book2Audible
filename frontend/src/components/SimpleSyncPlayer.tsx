import React from 'react';
import { X } from 'lucide-react';

interface SimpleSyncPlayerProps {
  chapterId: number;
  onClose: () => void;
}

export const SimpleSyncPlayer: React.FC<SimpleSyncPlayerProps> = ({ 
  chapterId, 
  onClose 
}) => {
  return (
    <div className="max-w-6xl mx-auto bg-white rounded-lg shadow-lg overflow-hidden">
      {/* Header */}
      <div className="bg-primary-600 text-white p-4 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">Synchronized Audio Player</h2>
          <p className="text-primary-100">Chapter {chapterId}</p>
        </div>
        <button
          onClick={onClose}
          className="p-2 hover:bg-primary-700 rounded-lg transition-colors"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="p-6">
        <div className="text-center text-gray-600">
          <h3 className="text-lg font-medium mb-4">Coming Soon!</h3>
          <p className="mb-4">
            The synchronized audio-text player is being finalized and will include:
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div className="bg-blue-50 p-4 rounded-lg">
              <h4 className="font-medium text-blue-900 mb-2">📄 Text Features</h4>
              <ul className="text-blue-700 space-y-1 text-left">
                <li>• Real-time word highlighting</li>
                <li>• Click any word to jump to audio position</li>
                <li>• Visual chunk boundary indicators</li>
                <li>• Scrolling text that follows audio</li>
              </ul>
            </div>
            
            <div className="bg-green-50 p-4 rounded-lg">
              <h4 className="font-medium text-green-900 mb-2">🎵 Audio Features</h4>
              <ul className="text-green-700 space-y-1 text-left">
                <li>• Full audio playback controls</li>
                <li>• Variable playback speed</li>
                <li>• Skip forward/backward by 10 seconds</li>
                <li>• Chapter audio stitching</li>
              </ul>
            </div>
            
            <div className="bg-purple-50 p-4 rounded-lg">
              <h4 className="font-medium text-purple-900 mb-2">⚙️ Technical Features</h4>
              <ul className="text-purple-700 space-y-1 text-left">
                <li>• Display Orpheus TTS parameters</li>
                <li>• Show chunk processing details</li>
                <li>• Audio version history</li>
                <li>• Reprocessing timeline</li>
              </ul>
            </div>
            
            <div className="bg-orange-50 p-4 rounded-lg">
              <h4 className="font-medium text-orange-900 mb-2">🔧 Management Features</h4>
              <ul className="text-orange-700 space-y-1 text-left">
                <li>• Identify problematic chunks visually</li>
                <li>• Quality assessment indicators</li>
                <li>• Cost-effective reprocessing tools</li>
                <li>• Integration with chunk management</li>
              </ul>
            </div>
          </div>
          
          <div className="mt-6 p-4 bg-gray-50 rounded-lg border">
            <p className="text-sm text-gray-700">
              <strong>💡 Current Status:</strong> All backend infrastructure is ready including 
              word-level timing extraction, audio version tracking, and the database schema. 
              The React component is being optimized to ensure fast frontend compilation.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};