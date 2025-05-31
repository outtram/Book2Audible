import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { startConversion, getProviders, getVoices, testConnection, getUploadInfo } from '../utils/api';
import { Settings, Mic, Zap, AlertCircle, CheckCircle } from 'lucide-react';
import type { Provider } from '../types';

export const ConfigurePage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  
  const [providers, setProviders] = useState<Provider[]>([]);
  const [voices, setVoices] = useState<{ fal: string[]; baseten: string[] }>({ fal: [], baseten: [] });
  const [selectedProvider, setSelectedProvider] = useState('fal');
  const [selectedVoice, setSelectedVoice] = useState('tara');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<{ fal: any; baseten: any } | null>(null);
  const [testingConnection, setTestingConnection] = useState(false);
  const [uploadInfo, setUploadInfo] = useState<any>(null);
  const [loadingUploadInfo, setLoadingUploadInfo] = useState(true);

  useEffect(() => {
    loadConfiguration();
    testConnections();
    loadUploadInfo();
  }, []);

  const loadUploadInfo = async () => {
    if (!jobId) return;
    
    try {
      setLoadingUploadInfo(true);
      const info = await getUploadInfo(jobId);
      setUploadInfo(info);
    } catch (err: any) {
      console.error('Failed to load upload info:', err);
    } finally {
      setLoadingUploadInfo(false);
    }
  };

  const loadConfiguration = async () => {
    try {
      const [providersResponse, voicesResponse] = await Promise.all([
        getProviders(),
        getVoices()
      ]);
      
      setProviders(providersResponse.providers);
      setVoices(voicesResponse);
    } catch (err: any) {
      setError('Failed to load configuration options');
    }
  };

  const testConnections = async () => {
    setTestingConnection(true);
    try {
      const status = await testConnection();
      setConnectionStatus(status);
    } catch (err) {
      console.error('Connection test failed:', err);
    } finally {
      setTestingConnection(false);
    }
  };

  const handleStartConversion = async () => {
    if (!jobId) return;
    
    setLoading(true);
    setError(null);
    
    try {
      await startConversion(jobId, {
        voice: selectedVoice,
        provider: selectedProvider,
        manual_chapters: [] // Could add manual chapter input later
      });
      
      navigate(`/processing/${jobId}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start conversion');
    } finally {
      setLoading(false);
    }
  };

  const availableVoices = selectedProvider === 'fal' ? voices.fal : voices.baseten;
  const selectedProviderInfo = providers.find(p => p.id === selectedProvider);

  const getConnectionIcon = (status: any) => {
    if (testingConnection) {
      return <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary-600"></div>;
    }
    if (status?.status === 'success') {
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    }
    return <AlertCircle className="h-4 w-4 text-red-500" />;
  };

  return (
    <div className="px-40 flex flex-1 justify-center py-5">
      <div className="layout-content-container flex flex-col w-[512px] max-w-[512px] py-5 max-w-[960px] flex-1">
        <h2 className="text-primary-700 tracking-light text-[28px] font-bold leading-tight px-4 text-center pb-3 pt-5">
          Customize your audiobook
        </h2>

        {/* Book Information */}
        {!loadingUploadInfo && uploadInfo && (
          <div className="flex flex-col p-4 mb-4">
            <div className="bg-primary-50 rounded-lg border border-primary-200 p-4">
              <h3 className="text-sm font-medium text-primary-700 mb-3 flex items-center gap-2">
                <Settings className="h-4 w-4" />
                Book Information
              </h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-primary-600">File:</span>
                  <span className="text-primary-700 font-medium">{uploadInfo.filename}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-primary-600">Size:</span>
                  <span className="text-primary-700">{(uploadInfo.file_size / 1024).toFixed(1)} KB</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-primary-600">Characters:</span>
                  <span className="text-primary-700">{uploadInfo.character_count.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-primary-600">Words:</span>
                  <span className="text-primary-700">{uploadInfo.word_count.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-primary-600">Estimated Cost:</span>
                  <span className="text-primary-700 font-medium">${uploadInfo.estimated_cost_fal}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Provider Selection */}
        <div className="flex flex-col p-4">
          <label className="flex flex-col min-w-40 flex-1 mb-4">
            <p className="text-primary-700 text-base font-medium leading-normal pb-2">TTS Provider</p>
            <div className="space-y-3">
              {providers.map((provider) => (
                <div
                  key={provider.id}
                  className={`border rounded-lg p-4 cursor-pointer transition-colors ${
                    selectedProvider === provider.id
                      ? 'border-primary-600 bg-primary-50'
                      : 'border-primary-200 hover:border-primary-400'
                  }`}
                  onClick={() => {
                    setSelectedProvider(provider.id);
                    if (provider.id === 'fal' && voices.fal.length > 0) {
                      setSelectedVoice(voices.fal[0]);
                    } else if (provider.id === 'baseten' && voices.baseten.length > 0) {
                      setSelectedVoice(voices.baseten[0]);
                    }
                  }}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`w-4 h-4 rounded-full border-2 ${
                        selectedProvider === provider.id
                          ? 'border-primary-600 bg-primary-600'
                          : 'border-gray-300'
                      }`}>
                        {selectedProvider === provider.id && (
                          <div className="w-full h-full rounded-full bg-white scale-50"></div>
                        )}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="font-medium text-primary-700">{provider.name}</h3>
                          {provider.recommended && (
                            <span className="px-2 py-1 text-xs bg-primary-600 text-white rounded-full">
                              Recommended
                            </span>
                          )}
                          {connectionStatus && getConnectionIcon(connectionStatus[provider.id])}
                        </div>
                        <p className="text-sm text-primary-500">{provider.description}</p>
                        <p className="text-xs text-primary-400">
                          {provider.pricing} • {provider.voices} voices
                        </p>
                      </div>
                    </div>
                    {provider.id === 'fal' && <Zap className="h-5 w-5 text-yellow-500" />}
                  </div>
                </div>
              ))}
            </div>
          </label>

          {/* Voice Selection */}
          <label className="flex flex-col min-w-40 flex-1 mb-6">
            <p className="text-primary-700 text-base font-medium leading-normal pb-2">Voice</p>
            <div className="relative">
              <select
                value={selectedVoice}
                onChange={(e) => setSelectedVoice(e.target.value)}
                className="form-input flex w-full min-w-0 flex-1 resize-none overflow-hidden rounded-lg text-primary-700 focus:outline-0 focus:ring-0 border border-primary-200 bg-primary-50 focus:border-primary-600 h-14 placeholder:text-primary-500 p-[15px] text-base font-normal leading-normal appearance-none"
                style={{
                  backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' width='24px' height='24px' fill='rgb(70,160,128)' viewBox='0 0 256 256'%3e%3cpath d='M181.66,170.34a8,8,0,0,1,0,11.32l-48,48a8,8,0,0,1-11.32,0l-48-48a8,8,0,0,1,11.32-11.32L128,212.69l42.34-42.35A8,8,0,0,1,181.66,170.34Zm-96-84.68L128,43.31l42.34,42.35a8,8,0,0,0,11.32-11.32l-48-48a8,8,0,0,0-11.32,0l-48,48A8,8,0,0,0,85.66,85.66Z'%3e%3c/path%3e%3c/svg%3e")`,
                  backgroundPosition: 'right 15px center',
                  backgroundRepeat: 'no-repeat',
                }}
              >
                {availableVoices.map((voice) => (
                  <option key={voice} value={voice}>
                    {voice.charAt(0).toUpperCase() + voice.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            {selectedProviderInfo && (
              <p className="text-xs text-primary-400 mt-2">
                Cost estimate: {selectedProviderInfo.pricing}
              </p>
            )}
          </label>

          {/* Connection Status */}
          {connectionStatus && (
            <div className="mb-6 p-3 bg-primary-50 rounded-lg border border-primary-200">
              <h4 className="text-sm font-medium text-primary-700 mb-2 flex items-center gap-2">
                <Settings className="h-4 w-4" />
                Connection Status
              </h4>
              <div className="space-y-2 text-xs">
                <div className="flex items-start justify-between">
                  <span>Fal.ai:</span>
                  <div className="flex flex-col items-end gap-1">
                    <div className="flex items-center gap-1">
                      {getConnectionIcon(connectionStatus.fal)}
                      <span className={connectionStatus.fal?.status === 'success' ? 'text-green-600' : 'text-red-600'}>
                        {connectionStatus.fal?.status || 'unknown'}
                      </span>
                    </div>
                    {connectionStatus.fal?.message && (
                      <div className="text-right text-red-600 max-w-xs">
                        <p className="break-words">{connectionStatus.fal.message}</p>
                        {connectionStatus.fal.message.includes('Exhausted balance') && (
                          <p className="mt-1 text-blue-600">
                            <a href="https://fal.ai/dashboard/billing" target="_blank" rel="noopener noreferrer" className="underline">
                              Top up balance →
                            </a>
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3">
              <AlertCircle className="h-5 w-5 text-red-500" />
              <span className="text-red-700 text-sm">{error}</span>
            </div>
          )}

          <div className="flex px-4 py-3 justify-center">
            <button
              onClick={handleStartConversion}
              disabled={loading || !selectedVoice}
              className="flex min-w-[84px] max-w-[480px] cursor-pointer items-center justify-center overflow-hidden rounded-lg h-10 px-4 bg-primary-600 text-primary-50 text-sm font-bold leading-normal tracking-[0.015em] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <div className="flex items-center gap-2">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  <span>Starting...</span>
                </div>
              ) : (
                <span className="truncate">Convert to Audio</span>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};