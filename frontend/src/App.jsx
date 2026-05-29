import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useLocation, Navigate } from 'react-router-dom';
import Navbar from './components/layout/Navbar';
import MainDashboard from './pages/MainDashboard';
import AnalyticsDashboard from './pages/AnalyticsDashboard';
import NotificationPage from './pages/NotificationPage';
import SharedChat from './pages/SharedChat';
import LandingPage from './pages/LandingPage'; 

// --- 🆕 IMPORT THE NEW ADMIN WORKSPACE ---
import AdminControlWorkspace from './pages/AdminControlWorkspace'; 

const Layout = ({ children }) => {
  const location = useLocation();
  
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
  const [currentSessionId, setCurrentSessionId] = useState(null);
  
  // --- 1. SIMPLE AUTH STATE ---
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userRole, setUserRole] = useState(null);

  // --- 2. CHECK STORAGE ON LOAD ---
  useEffect(() => {
    const role = localStorage.getItem('userRole');
    if (role && role !== 'undefined' && role !== 'null') {
      setIsAuthenticated(true);
      setUserRole(role.toLowerCase()); // Ensure lowercase for strict matching
    }
  }, []);

  // --- 3. THE UNLOCK FUNCTION ---
  // LandingPage calls this when the backend says "Success"
  const handleLoginSuccess = (role) => {
    setIsAuthenticated(true);
    setUserRole(role.toLowerCase());
  };

  // --- 4. THE GATE ---
  // If not logged in, stop here and ONLY show the Landing Page
  if (!isAuthenticated) {
    return <LandingPage onLoginSuccess={handleLoginSuccess} />;
  }

  // --- 5. YOUR ORIGINAL WORKING APP ---
  return (
    <Router>
      <Layout>
        <Routes>
          <Route 
            path="/" 
            element={
              <MainDashboard 
                currentSessionId={currentSessionId} 
                onSessionSelect={setCurrentSessionId} 
              />
            } 
          />
          
          {/* Protected Analytics Route */}
          <Route 
            path="/analytics" 
            element={
              userRole === 'admin' 
                ? <AnalyticsDashboard /> 
                : <Navigate to="/" replace /> 
            } 
          />

          {/* 🆕 Protected Admin Workspace Route */}
          <Route 
            path="/admin-control" 
            element={
              userRole === 'admin' 
                ? <AdminControlWorkspace /> 
                : <Navigate to="/" replace /> 
            } 
          />
          
          <Route path="/notifications" element={<NotificationPage />} />
          <Route path="/share/:id" element={<SharedChat />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;