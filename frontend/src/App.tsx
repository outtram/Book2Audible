import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Header } from './components/Header';
import { HomePage } from './pages/HomePage';
import { UploadPage } from './pages/UploadPage';
import { ConfigurePage } from './pages/ConfigurePage';
import { ProcessingPage } from './pages/ProcessingPage';
import { ResultsPage } from './pages/ResultsPage';
import { ChaptersPage } from './pages/ChaptersPage';
import { HelpPage } from './pages/HelpPage';

function App() {
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
                <Route path="/help" element={<HelpPage />} />
              </Routes>
            </div>
          </main>
        </div>
      </div>
    </Router>
  );
}

export default App;