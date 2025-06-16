import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Header } from './components/Header';
import { HomePage } from './pages/HomePage';
import { UploadPage } from './pages/UploadPage';
import { ConfigurePage } from './pages/ConfigurePage';
import { ProcessingPage } from './pages/ProcessingPage';
import { ResultsPage } from './pages/ResultsPage';
import { ChaptersPage } from './pages/ChaptersPage';
import { ChunkManagementPage } from './pages/ChunkManagementPage';
import { HelpPage } from './pages/HelpPage';
import { VERSION } from './version';

function App() {
  const [backendVersion, setBackendVersion] = useState({
    backend_version: 'N/A',
    build_date: 'N/A',
    timestamp: 'N/A'
  });

  useEffect(() => {
    const fetchBackendVersion = async () => {
      try {
        const response = await fetch('/api/version');
        if (response.ok) {
          const data = await response.json();
          setBackendVersion(data);
        }
      } catch (error) {
        console.error('Failed to fetch backend version:', error);
      }
    };
    fetchBackendVersion();
  }, []);

  return (
    <Router>
      <div className="relative flex size-full min-h-screen flex-col bg-primary-50 overflow-x-hidden"
           style={{ fontFamily: 'Inter, "Noto Sans", sans-serif' }}>
        <div className="layout-container flex h-full grow flex-col">
          <Header />
          
          <main className="flex flex-1 justify-center">
            <div className="layout-content-container flex flex-col max-w-[960px] flex-1">
              <Routes>
                <Route path="/" element={<HomePage />} />
                <Route path="/upload" element={<UploadPage />} />
                <Route path="/configure/:jobId" element={<ConfigurePage />} />
                <Route path="/processing/:jobId" element={<ProcessingPage />} />
                <Route path="/results/:jobId" element={<ResultsPage />} />
                <Route path="/chapters" element={<ChaptersPage />} />
                <Route path="/chunks/:chapterId" element={<ChunkManagementPage />} />
                <Route path="/help" element={<HelpPage />} />
              </Routes>
            </div>
          </main>
          <footer className="bg-gray-200 text-gray-600 text-xs p-2 text-center">
            Frontend v{VERSION.frontend} ({VERSION.buildDate}) | Backend v{backendVersion.backend_version} ({backendVersion.build_date})
          </footer>
        </div>
      </div>
    </Router>
  );
}

export default App;