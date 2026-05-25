import React, { useState } from 'react';
import Navbar from './Navbar'; // Adjust paths if necessary
import Sidebar from './Sidebar';
import Footer from './Footer';

const AppLayout = ({ 
  children, 
  // Passing these through in case your main router feeds them here
  activeTab, 
  setActiveTab, 
  currentSessionId, 
  onSessionSelect 
}) => {
  
  // --- NEW: State to control mobile sidebar toggle ---
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  return (
    // Changed h-screen to h-[100dvh] for perfect iOS/Mobile viewport sizing
    <div className="flex flex-col h-[100dvh] bg-slate-50 w-full overflow-hidden">
      
      {/* Pass the function to open the sidebar when the hamburger is clicked */}
      <Navbar onMenuClick={() => setIsSidebarOpen(true)} />
      
      <div className="flex flex-1 overflow-hidden relative">
        
        {/* Pass the open state and close function to the Sidebar */}
        <Sidebar 
          isOpen={isSidebarOpen} 
          onClose={() => setIsSidebarOpen(false)}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          currentSessionId={currentSessionId}
          onSessionSelect={onSessionSelect}
        />
        
        <main className="flex-1 overflow-auto bg-slate-50">
          {children} 
        </main>
      </div>
      
      <Footer />
    </div>
  );
};

export default AppLayout;