import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';
import Navbar from './components/layout/Navbar';
import MainDashboard from './pages/MainDashboard';
import AnalyticsDashboard from './pages/AnalyticsDashboard';
import NotificationPage from './pages/NotificationPage';
import SharedChat from './pages/SharedChat';

// Helper component for conditional rendering
const Layout = ({ children }) => {
  const location = useLocation();
  
  // HIDE Navbar on "/" (Dashboard with Sidebar) 
  // and HIDE Navbar on "/share" (Standalone shared view)
  const isSpecialPage = location.pathname === '/' || location.pathname.startsWith('/share/');

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      {!isSpecialPage && <Navbar />}
      <div className="flex-1 overflow-hidden">
        {children}
      </div>
    </div>
  );
};

function App() {
  // Lift the session state up to the App level so it persists 
  const [currentSessionId, setCurrentSessionId] = useState(null);

  return (
    <Router>
      <Layout>
        <Routes>
          {/* Main App Dashboard */}
          <Route 
            path="/" 
            element={
              <MainDashboard 
                currentSessionId={currentSessionId} 
                onSessionSelect={setCurrentSessionId} 
              />
            } 
          />
          
          {/* Internal Pages */}
          <Route path="/analytics" element={<AnalyticsDashboard />} />
          <Route path="/notifications" element={<NotificationPage />} />
          
          {/* NEW: Standalone Shared Chat View */}
          <Route path="/share/:id" element={<SharedChat />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;