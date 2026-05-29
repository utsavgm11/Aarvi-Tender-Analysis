import React, { useRef, useEffect, useState } from 'react';
import AnalysisChat from './AnalysisChat';
import MasterDashboard from './MasterDashboard'; 
import AnalyticsDashboard from './AnalyticsDashboard'; 
import AdminControlWorkspace from './AdminControlWorkspace'; // 🆕 IMPORT ADMIN WORKSPACE

// Importing layout components
import Navbar from '../components/layout/Navbar';
import Sidebar from '../components/layout/Sidebar';
import Footer from '../components/layout/Footer';

// ACCEPT PROPS FROM App.jsx
const MainDashboard = ({ currentSessionId, onSessionSelect }) => {
  const dashboardSectionRef = useRef(null);
  
  // Tabs: 'analysis' (Chat), 'dashboard' (Table), 'analytics' (Charts), 'admin-control'
  const [activeTab, setActiveTab] = useState('dashboard'); 
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  // Force scroll to top on refresh for landing page effect
  useEffect(() => {
    if ('scrollRestoration' in window.history) {
      window.history.scrollRestoration = 'manual';
    }
    window.scrollTo(0, 0);
  }, []);

  const handleStart = () => {
    dashboardSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  // Dynamic Navbar Title
  const getNavbarTitle = () => {
    switch(activeTab) {
      case 'analysis': return "AI Analysis Chat";
      case 'analytics': return "Executive Analytics Dashboard";
      case 'admin-control': return "System Administration"; // 🆕 NEW TITLE
      default: return "Master Tender Dashboard";
    }
  };

  return (
    <div className="w-full bg-[#0f172a]">
      
      {/* SECTION 2: THE MAIN APPLICATION INTERFACE */}
      <section 
        ref={dashboardSectionRef}
        // Swapped h-screen to h-[100dvh] for perfect iOS/Mobile viewport sizing
        className="relative z-10 h-[100dvh] w-full bg-slate-50 flex shadow-[0_-20px_50px_rgba(0,0,0,0.5)]"
      >
        {/* Sidebar with Navigation Props AND Chat Session Props */}
        <Sidebar 
          isOpen={isSidebarOpen} 
          onClose={() => setIsSidebarOpen(false)} 
          activeTab={activeTab} 
          setActiveTab={setActiveTab} 
          currentSessionId={currentSessionId}
          onSessionSelect={onSessionSelect}
        />

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col h-full overflow-hidden min-w-0">
          {/* Navbar with Hamburger toggle */}
          <Navbar 
            title={getNavbarTitle()}
            onMenuClick={() => setIsSidebarOpen(true)} 
          />
          
          {/* Dynamic Content Area - Switching between Chat, Table, Charts, and Admin */}
          <main className="flex-1 overflow-auto relative bg-white">
            {activeTab === 'analysis' && (
              <AnalysisChat 
                currentSessionId={currentSessionId} 
                onSessionSelect={onSessionSelect} 
              />
            )}
            {activeTab === 'dashboard' && <MasterDashboard />}
            {activeTab === 'analytics' && <AnalyticsDashboard />}
            {activeTab === 'admin-control' && <AdminControlWorkspace />} {/* 🆕 RENDER ADMIN UI */}
          </main>
          
          <Footer />
        </div>
      </section>

      {/* CUSTOM CSS FOR THE VERTICAL STACK */}
      <style jsx global>{`
        body { overflow-x: hidden; background-color: #0f172a; }
        section { scroll-snap-align: start; }
        /* Ensure smooth scrolling for snap sections */
        html { scroll-behavior: smooth; }
      `}</style>
    </div>
  );
};

export default MainDashboard;