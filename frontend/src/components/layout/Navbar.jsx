import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Bell, XCircle, Menu } from 'lucide-react';
import { Link } from 'react-router-dom';

const Navbar = ({ title = "Dashboard", onMenuClick }) => {
  const [isBackendOnline, setIsBackendOnline] = useState(false);
  const [notifyCount, setNotifyCount] = useState(0);
  const [userInitials, setUserInitials] = useState("U");
  
  // This tells the app: Use the Render URL from Vercel, 
  // but fall back to your laptop if the variable isn't found.
  const API_BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8001";

  // --- Extract User Initials Logic ---
  useEffect(() => {
    try {
      const storedUser = localStorage.getItem('user'); 
      let nameToUse = "User";

      if (storedUser) {
        const parsedUser = JSON.parse(storedUser);
        nameToUse = parsedUser.manager_name || parsedUser.name || parsedUser.email || "User";
      } else {
        const simpleName = localStorage.getItem('userName') || localStorage.getItem('manager_name');
        if (simpleName) nameToUse = simpleName;
      }

      const nameParts = nameToUse.trim().split(" ");
      if (nameParts.length >= 2) {
        setUserInitials((nameParts[0][0] + nameParts[1][0]).toUpperCase());
      } else {
        setUserInitials(nameToUse.substring(0, 2).toUpperCase());
      }
    } catch (error) {
      console.warn("Could not parse user details for avatar initials.");
    }
  }, []);

  // --- EXISTING LOGIC: Health & Notification Check ---
  useEffect(() => {
    const checkHealthAndNotifications = async () => {
      try {
        await axios.get(`${API_BASE_URL}/health`, { timeout: 2000 });
        setIsBackendOnline(true);
        
        // Fetch Notification Count
        const res = await axios.get(`${API_BASE_URL}/tenders/upcoming-prebid`);
        setNotifyCount(res.data.length);
      } catch (error) {
        setIsBackendOnline(false);
        setNotifyCount(0);
      }
    };

    checkHealthAndNotifications();
    const interval = setInterval(checkHealthAndNotifications, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-4 sm:px-6 shadow-sm shrink-0 w-full z-10 transition-all">
      
      {/* LEFT SECTION: Hamburger (Mobile) + Title */}
      <div className="flex items-center gap-2 sm:gap-4 flex-1 min-w-0">
        <button 
          onClick={onMenuClick}
          className="lg:hidden p-1.5 -ml-1.5 text-slate-500 hover:text-indigo-600 hover:bg-slate-100 rounded-md transition-colors"
          aria-label="Toggle Menu"
        >
          <Menu size={24} />
        </button>
        <h1 className="font-bold text-slate-800 text-lg sm:text-xl truncate tracking-tight">{title}</h1>
      </div>
      
      {/* RIGHT SECTION: Status, Notifications, Profile */}
      <div className="flex items-center gap-3 sm:gap-5 shrink-0">
        
        {/* Backend Status */}
        <div className={`hidden sm:flex items-center gap-2 text-[10px] sm:text-[11px] font-extrabold uppercase tracking-widest px-2 sm:px-3 py-1.5 rounded-full border transition-colors duration-300 shadow-sm ${
          isBackendOnline ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-rose-50 border-rose-200 text-rose-700'
        }`}>
          {isBackendOnline ? (
            <>
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span className="hidden md:inline">Backend Online</span>
              <span className="md:hidden">Online</span>
            </>
          ) : (
            <>
              <XCircle size={14} className="text-rose-500" />
              <span className="hidden md:inline">Backend Offline</span>
              <span className="md:hidden">Offline</span>
            </>
          )}
        </div>
        
        {/* CLICKABLE NOTIFICATION BELL */}
        <Link 
          to="/notifications" 
          className="relative text-slate-400 hover:text-indigo-600 transition-colors p-1"
        >
          <Bell size={20} className="sm:w-[22px] sm:h-[22px]" />
          {notifyCount > 0 && (
            <span className="absolute -top-1 -right-1 bg-rose-500 text-white text-[9px] sm:text-[10px] font-black w-4 h-4 sm:w-4 sm:h-4 flex items-center justify-center rounded-full shadow-md animate-bounce border-2 border-white">
              {notifyCount}
            </span>
          )}
        </Link>

        {/* USER AVATAR WITH INITIALS (No Dropdown) */}
        <div 
          className="w-8 h-8 sm:w-9 sm:h-9 bg-indigo-600 text-white font-bold text-xs sm:text-sm rounded-full flex items-center justify-center shadow-sm ring-2 ring-white select-none"
          title="User Profile"
        >
          {userInitials}
        </div>

      </div>
    </header>
  );
};

export default Navbar;