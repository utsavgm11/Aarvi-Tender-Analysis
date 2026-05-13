import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { User, Bell, XCircle } from 'lucide-react';
import { Link } from 'react-router-dom'; // Import Link from react-router-dom

const Navbar = ({ title = "Dashboard" }) => {
  const [isBackendOnline, setIsBackendOnline] = useState(false);
  const [notifyCount, setNotifyCount] = useState(0);
  
  // This tells the app: Use the Render URL from Vercel, 
// but fall back to your laptop if the variable isn't found.
  const API_BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8001";

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
    <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-6 shadow-sm shrink-0 w-full z-10">
      <h1 className="font-bold text-slate-800 text-xl truncate tracking-tight">{title}</h1>
      
      <div className="flex items-center gap-5">
        <div className={`hidden sm:flex items-center gap-2 text-[11px] font-extrabold uppercase tracking-widest px-3 py-1.5 rounded-full border transition-colors duration-300 shadow-sm ${
          isBackendOnline ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-rose-50 border-rose-200 text-rose-700'
        }`}>
          {isBackendOnline ? (
            <>
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span>Backend Online</span>
            </>
          ) : (
            <><XCircle size={14} className="text-rose-500" /><span>Backend Offline</span></>
          )}
        </div>
        
        {/* CLICKABLE NOTIFICATION BELL */}
        <Link 
          to="/notifications" 
          className="relative text-slate-400 hover:text-indigo-600 transition-colors p-1"
        >
          <Bell size={22} />
          {notifyCount > 0 && (
            <span className="absolute -top-1 -right-1 bg-rose-500 text-white text-[10px] font-black w-4 h-4 flex items-center justify-center rounded-full shadow-md animate-bounce border-2 border-white">
              {notifyCount}
            </span>
          )}
        </Link>

        <div className="w-9 h-9 bg-indigo-50 text-indigo-600 rounded-full flex items-center justify-center border border-indigo-200 cursor-pointer hover:bg-indigo-100 transition-all">
          <User size={18} />
        </div>
      </div>
    </header>
  );
};

export default Navbar;