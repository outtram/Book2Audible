import React, { useState, useEffect } from 'react';
import { RefreshCw, Copy, CheckCircle, XCircle, AlertCircle, Info, Download, Server, HardDrive, Cpu, Activity, Terminal } from 'lucide-react';

interface SystemStatus {
  timestamp: string;
  system: {
    disk_usage: {
      total_gb: number;
      used_gb: number;
      free_gb: number;
      percent_used: number;
    };
    memory: {
      total_gb: number;
      used_gb: number;
      available_gb: number;
      percent_used: number;
    };
  };
  application: {
    log_file_size_mb: number;
    active_jobs: number;
    processing_jobs: number;
    tts_connection: any;
  };
  directories: {
    data_dir_exists: boolean;
    output_dir_exists: boolean;
    logs_dir_exists: boolean;
  };
}

interface LogEntry {
  timestamp: string;
  logger: string;
  level: string;
  message: string;
  raw: string;
}

interface LogResponse {
  logs: LogEntry[];
  total_lines: number;
  file_path: string;
  error?: string;
}

export const HelpPage: React.FC = () => {
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [logs, setLogs] = useState<LogResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logLines, setLogLines] = useState(100);
  const [copiedText, setCopiedText] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const fetchSystemStatus = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/system-status');
      if (response.ok) {
        const data = await response.json();
        setSystemStatus(data);
      }
    } catch (error) {
      console.error('Failed to fetch system status:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchLogs = async () => {
    try {
      setLogsLoading(true);
      const response = await fetch(`/api/logs?lines=${logLines}`);
      if (response.ok) {
        const data = await response.json();
        setLogs(data);
      }
    } catch (error) {
      console.error('Failed to fetch logs:', error);
    } finally {
      setLogsLoading(false);
    }
  };

  const copyToClipboard = async (text: string, type: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedText(type);
      setTimeout(() => setCopiedText(null), 2000);
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="h-4 w-4 text-green-600" />;
      case 'failed':
      case 'error':
        return <XCircle className="h-4 w-4 text-red-600" />;
      default:
        return <AlertCircle className="h-4 w-4 text-yellow-600" />;
    }
  };

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'ERROR':
        return 'text-red-600';
      case 'WARNING':
        return 'text-yellow-600';
      case 'INFO':
        return 'text-blue-600';
      case 'DEBUG':
        return 'text-gray-600';
      default:
        return 'text-gray-800';
    }
  };

  const formatErrorsForClaude = () => {
    if (!logs?.logs) return '';
    
    const errorLogs = logs.logs.filter(log => 
      log.level === 'ERROR' || log.message.toLowerCase().includes('error') || 
      log.message.toLowerCase().includes('failed') || log.message.toLowerCase().includes('exception')
    );
    
    if (errorLogs.length === 0) return 'No errors found in recent logs.';
    
    let formatted = `Book2Audible Error Report - ${new Date().toISOString()}\n`;
    formatted += `=================================================\n\n`;
    
    if (systemStatus) {
      formatted += `System Status:\n`;
      formatted += `- Memory: ${systemStatus.system.memory.percent_used}% used (${systemStatus.system.memory.used_gb}GB / ${systemStatus.system.memory.total_gb}GB)\n`;
      formatted += `- Disk: ${systemStatus.system.disk_usage.percent_used}% used (${systemStatus.system.disk_usage.free_gb}GB free)\n`;
      formatted += `- Active Jobs: ${systemStatus.application.active_jobs}\n`;
      formatted += `- Processing Jobs: ${systemStatus.application.processing_jobs}\n`;
      formatted += `- TTS Connection: ${systemStatus.application.tts_connection?.fal?.status || 'unknown'}\n\n`;
    }
    
    formatted += `Recent Errors (${errorLogs.length} found):\n`;
    formatted += `-`.repeat(50) + `\n\n`;
    
    errorLogs.forEach((log, index) => {
      formatted += `${index + 1}. [${log.timestamp}] ${log.level}\n`;
      formatted += `   Logger: ${log.logger}\n`;
      formatted += `   Message: ${log.message}\n\n`;
    });
    
    return formatted;
  };

  useEffect(() => {
    fetchSystemStatus();
    fetchLogs();
  }, []);

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        fetchSystemStatus();
        fetchLogs();
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  return (
    <div className="flex flex-col gap-6 px-4 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-primary-700 text-2xl font-bold">System Help & Diagnostics</h1>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            Auto-refresh (5s)
          </label>
          <button
            onClick={() => {
              fetchSystemStatus();
              fetchLogs();
            }}
            disabled={loading || logsLoading}
            className="flex items-center gap-2 px-3 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${(loading || logsLoading) ? 'animate-spin' : ''}`} />
            Refresh All
          </button>
        </div>
      </div>

      {/* System Status Section */}
      <div className="bg-white rounded-lg border border-primary-200 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Server className="h-5 w-5 text-primary-600" />
          <h2 className="text-lg font-semibold text-primary-700">System Status</h2>
          {loading && <RefreshCw className="h-4 w-4 animate-spin text-primary-600" />}
        </div>

        {systemStatus ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Memory Usage */}
            <div className="bg-primary-50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Cpu className="h-4 w-4 text-primary-600" />
                <h3 className="font-medium text-primary-700">Memory Usage</h3>
              </div>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span>Used:</span>
                  <span className={systemStatus.system.memory.percent_used > 80 ? 'text-red-600 font-medium' : 'text-gray-700'}>
                    {systemStatus.system.memory.percent_used}%
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Available:</span>
                  <span>{systemStatus.system.memory.available_gb}GB</span>
                </div>
                <div className="flex justify-between">
                  <span>Total:</span>
                  <span>{systemStatus.system.memory.total_gb}GB</span>
                </div>
              </div>
            </div>

            {/* Disk Usage */}
            <div className="bg-primary-50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <HardDrive className="h-4 w-4 text-primary-600" />
                <h3 className="font-medium text-primary-700">Disk Usage</h3>
              </div>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span>Used:</span>
                  <span className={systemStatus.system.disk_usage.percent_used > 90 ? 'text-red-600 font-medium' : 'text-gray-700'}>
                    {systemStatus.system.disk_usage.percent_used}%
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Free:</span>
                  <span>{systemStatus.system.disk_usage.free_gb}GB</span>
                </div>
                <div className="flex justify-between">
                  <span>Total:</span>
                  <span>{systemStatus.system.disk_usage.total_gb}GB</span>
                </div>
              </div>
            </div>

            {/* Application Status */}
            <div className="bg-primary-50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="h-4 w-4 text-primary-600" />
                <h3 className="font-medium text-primary-700">Application</h3>
              </div>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span>Active Jobs:</span>
                  <span className={systemStatus.application.processing_jobs > 0 ? 'text-green-600 font-medium' : 'text-gray-700'}>
                    {systemStatus.application.active_jobs}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Processing:</span>
                  <span className={systemStatus.application.processing_jobs > 0 ? 'text-blue-600 font-medium' : 'text-gray-700'}>
                    {systemStatus.application.processing_jobs}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Log Size:</span>
                  <span>{systemStatus.application.log_file_size_mb}MB</span>
                </div>
              </div>
            </div>

            {/* TTS Connection */}
            <div className="bg-primary-50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Server className="h-4 w-4 text-primary-600" />
                <h3 className="font-medium text-primary-700">TTS Connection</h3>
              </div>
              <div className="space-y-1 text-sm">
                <div className="flex items-center justify-between">
                  <span>Fal.ai:</span>
                  <div className="flex items-center gap-1">
                    {getStatusIcon(systemStatus.application.tts_connection?.fal?.status)}
                    <span className="text-gray-700">
                      {systemStatus.application.tts_connection?.fal?.status || 'unknown'}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Directory Status */}
            <div className="bg-primary-50 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <Terminal className="h-4 w-4 text-primary-600" />
                <h3 className="font-medium text-primary-700">Directories</h3>
              </div>
              <div className="space-y-1 text-sm">
                <div className="flex items-center justify-between">
                  <span>Data Dir:</span>
                  {getStatusIcon(systemStatus.directories.data_dir_exists ? 'success' : 'error')}
                </div>
                <div className="flex items-center justify-between">
                  <span>Output Dir:</span>
                  {getStatusIcon(systemStatus.directories.output_dir_exists ? 'success' : 'error')}
                </div>
                <div className="flex items-center justify-between">
                  <span>Logs Dir:</span>
                  {getStatusIcon(systemStatus.directories.logs_dir_exists ? 'success' : 'error')}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            {loading ? 'Loading system status...' : 'Failed to load system status'}
          </div>
        )}

        {systemStatus && (
          <div className="mt-4 pt-4 border-t border-primary-200">
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500">
                Last updated: {new Date(systemStatus.timestamp).toLocaleString()}
              </span>
              <button
                onClick={() => copyToClipboard(JSON.stringify(systemStatus, null, 2), 'status')}
                className="flex items-center gap-1 text-xs text-primary-600 hover:text-primary-700"
              >
                <Copy className="h-3 w-3" />
                {copiedText === 'status' ? 'Copied!' : 'Copy Status'}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Error Summary for Claude */}
      <div className="bg-white rounded-lg border border-primary-200 p-6">
        <div className="flex items-center gap-2 mb-4">
          <AlertCircle className="h-5 w-5 text-red-600" />
          <h2 className="text-lg font-semibold text-primary-700">Error Report for Claude Code</h2>
        </div>
        
        <p className="text-sm text-gray-600 mb-4">
          Copy this report and paste it into Claude Code to help diagnose and fix issues:
        </p>
        
        <div className="bg-gray-50 rounded border p-4">
          <pre className="text-xs text-gray-700 whitespace-pre-wrap max-h-48 overflow-y-auto">
            {formatErrorsForClaude()}
          </pre>
        </div>
        
        <button
          onClick={() => copyToClipboard(formatErrorsForClaude(), 'errors')}
          className="mt-3 flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
        >
          <Copy className="h-4 w-4" />
          {copiedText === 'errors' ? 'Copied Error Report!' : 'Copy Error Report for Claude'}
        </button>
      </div>

      {/* Logs Section */}
      <div className="bg-white rounded-lg border border-primary-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Terminal className="h-5 w-5 text-primary-600" />
            <h2 className="text-lg font-semibold text-primary-700">System Logs</h2>
            {logsLoading && <RefreshCw className="h-4 w-4 animate-spin text-primary-600" />}
          </div>
          
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-600">Lines:</label>
              <select
                value={logLines}
                onChange={(e) => setLogLines(Number(e.target.value))}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
              >
                <option value={50}>50</option>
                <option value={100}>100</option>
                <option value={200}>200</option>
                <option value={500}>500</option>
              </select>
            </div>
            <button
              onClick={fetchLogs}
              disabled={logsLoading}
              className="flex items-center gap-2 px-3 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${logsLoading ? 'animate-spin' : ''}`} />
              Refresh Logs
            </button>
          </div>
        </div>

        {logs ? (
          <>
            <div className="mb-4 text-sm text-gray-600">
              Showing {logs.total_lines} recent log entries from: {logs.file_path}
            </div>
            
            <div className="bg-black rounded-lg p-4 max-h-96 overflow-y-auto font-mono text-sm">
              {logs.logs.length > 0 ? (
                logs.logs.map((log, index) => (
                  <div key={index} className="mb-1">
                    <span className="text-gray-400">{log.timestamp}</span>
                    <span className="text-blue-400 ml-2">{log.logger}</span>
                    <span className={`ml-2 font-medium ${getLevelColor(log.level)}`}>
                      [{log.level}]
                    </span>
                    <span className="text-gray-100 ml-2">{log.message}</span>
                  </div>
                ))
              ) : (
                <div className="text-gray-400">No logs found</div>
              )}
            </div>
            
            <div className="mt-4 flex items-center gap-3">
              <button
                onClick={() => copyToClipboard(logs.logs.map(log => log.raw).join('\n'), 'logs')}
                className="flex items-center gap-2 px-3 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
              >
                <Copy className="h-4 w-4" />
                {copiedText === 'logs' ? 'Copied!' : 'Copy All Logs'}
              </button>
              
              <button
                onClick={() => {
                  const errorLogs = logs.logs.filter(log => 
                    log.level === 'ERROR' || log.message.toLowerCase().includes('error')
                  );
                  copyToClipboard(errorLogs.map(log => log.raw).join('\n'), 'error-logs');
                }}
                className="flex items-center gap-2 px-3 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
              >
                <Copy className="h-4 w-4" />
                {copiedText === 'error-logs' ? 'Copied!' : 'Copy Error Logs Only'}
              </button>
            </div>
          </>
        ) : (
          <div className="text-center py-8 text-gray-500">
            {logsLoading ? 'Loading logs...' : 'Failed to load logs'}
          </div>
        )}
      </div>

      {/* Usage Instructions */}
      <div className="bg-white rounded-lg border border-primary-200 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Info className="h-5 w-5 text-blue-600" />
          <h2 className="text-lg font-semibold text-primary-700">Usage Instructions</h2>
        </div>
        
        <div className="space-y-4 text-sm text-gray-700">
          <div>
            <h3 className="font-medium text-primary-700 mb-2">System Monitoring:</h3>
            <ul className="list-disc pl-5 space-y-1">
              <li>Monitor memory and disk usage to ensure system health</li>
              <li>Check TTS connection status before starting conversions</li>
              <li>Active jobs show current conversion workload</li>
            </ul>
          </div>
          
          <div>
            <h3 className="font-medium text-primary-700 mb-2">Troubleshooting:</h3>
            <ul className="list-disc pl-5 space-y-1">
              <li>Use the "Error Report for Claude Code" section to copy issues for diagnosis</li>
              <li>Check recent logs for conversion errors or failures</li>
              <li>Copy specific error messages to share with Claude for fixes</li>
            </ul>
          </div>
          
          <div>
            <h3 className="font-medium text-primary-700 mb-2">Log Levels:</h3>
            <ul className="list-disc pl-5 space-y-1">
              <li><span className="text-red-600 font-medium">ERROR</span> - Critical issues requiring attention</li>
              <li><span className="text-yellow-600 font-medium">WARNING</span> - Potential problems</li>
              <li><span className="text-blue-600 font-medium">INFO</span> - Normal operation status</li>
              <li><span className="text-gray-600 font-medium">DEBUG</span> - Detailed diagnostic information</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};