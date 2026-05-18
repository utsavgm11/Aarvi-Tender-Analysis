import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  LayoutGrid, FileText, BarChart2, X, Plus, 
  MessageSquare, Edit3, Share2, Trash2, Search, LogOut
} from 'lucide-react';

// --- Sub-component for individual chat items ---
const ChatItem = ({ chat, currentSessionId, onSelect, onRename, onDelete }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [newTitle, setNewTitle] = useState(chat.title);
  const isActive = currentSessionId === chat.session_id;

  const handleSave = async (e) => {
    e.stopPropagation();
    if (newTitle.trim() && newTitle !== chat.title) {
      await onRename(chat.session_id, newTitle);
    } else {
      setNewTitle(chat.title);
    }
    setIsEditing(false);
  };

  const handleShare = (e) => {
    e.stopPropagation();
    const shareUrl = `${window.location.origin}/share/${chat.session_id}`;
    navigator.clipboard.writeText(shareUrl);
    alert("Share link copied to clipboard!");
  };

  const handleDelete = (e) => {
    e.stopPropagation();
    if (window.confirm("Are you sure you want to delete this analysis? This cannot be undone.")) {
      onDelete(chat.session_id);
    }
  };

  return (
    <div 
      className={`group flex items-center justify-between p-3 rounded-xl cursor-pointer transition-all ${
        isActive ? 'bg-blue-600 text-white shadow-md' : 'hover:bg-slate-800 text-slate-300'
      }`}
      onClick={() => !isEditing && onSelect(chat.session_id)}
    >
      <div className="flex items-center gap-3 overflow-hidden w-full">
        <MessageSquare size={16} className={isActive ? "text-blue-200" : "text-slate-500"} />
        {isEditing ? (
          <input 
            autoFocus
            className="bg-slate-700 text-white text-sm p-1 rounded w-full outline-none border border-blue-400"
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onBlur={handleSave}
            onKeyDown={(e) => e.key === 'Enter' && handleSave(e)}
            onClick={(e) => e.stopPropagation()}
          />
        ) : (
          <span className="truncate text-sm font-medium pr-2">{chat.title}</span>
        )}
      </div>
      
      {!isEditing && (
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
          <button 
            onClick={handleShare}
            className={`p-1 rounded hover:bg-white/20 transition-colors ${isActive ? 'text-blue-200' : 'text-slate-500'}`}
            title="Share Analysis"
          >
            <Share2 size={14} />
          </button>
          
          <button 
            onClick={(e) => { e.stopPropagation(); setIsEditing(true); }}
            className={`p-1 rounded hover:bg-white/20 transition-colors ${isActive ? 'text-blue-200' : 'text-slate-500'}`}
            title="Rename"
          >
            <Edit3 size={14} />
          </button>

          <button 
            onClick={handleDelete} 
            className={`p-1 rounded hover:bg-rose-500/30 transition-colors ${isActive ? 'text-rose-200 hover:text-white' : 'text-slate-500 hover:text-rose-400'}`}
            title="Delete Analysis"
          >
            <Trash2 size={14} />
          </button>
        </div>
      )}
    </div>
  );
};

const API_BASE_URL = import.meta.env.VITE_API_URL || "https://aarvi-tender-api.onrender.com";

// --- Main Sidebar Component ---
const Sidebar = ({ isOpen, onClose, activeTab, setActiveTab, currentSessionId, onSessionSelect }) => {
  const [sessions, setSessions] = useState([]);
  const [searchQuery, setSearchQuery] = useState(''); 
  
  const userRole = localStorage.getItem('userRole');

  const handleLogout = () => {
    localStorage.removeItem('userRole');
    localStorage.removeItem('userEmail');
    window.location.href = "/"; 
  };

  const fetchSessions = async () => {
    try {
      const userEmail = localStorage.getItem('userEmail');
      if (!userEmail) return;

      const res = await axios.get(`${API_BASE_URL}/chats/sessions`, {
        params: { email: userEmail } 
      });

      // FIX 1: Reverse the array so the newest chats (bottom of DB) show at the top of the UI
      const newestFirst = [...res.data].reverse();
      setSessions(newestFirst);
    } catch (err) {
      console.error("Error fetching sessions:", err);
    }
  };

  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      fetchSessions();
    }, 300);

    return () => clearTimeout(delayDebounceFn);
  }, [currentSessionId, searchQuery]);

  // FIX 2: Global Event Listener to catch when the AI finishes naming the chat
  useEffect(() => {
    const handleTitleUpdate = () => fetchSessions();
    window.addEventListener('refresh-sidebar', handleTitleUpdate);
    return () => window.removeEventListener('refresh-sidebar', handleTitleUpdate);
  }, []);

  const handleRename = async (sessionId, newTitle) => {
    try {
      await axios.put(`${API_BASE_URL}/chats/sessions/${sessionId}`, { title: newTitle });
      fetchSessions();
    } catch (err) {
      console.error("Error renaming session:", err);
    }
  };

  const handleDelete = async (sessionId) => {
    try {
      await axios.delete(`${API_BASE_URL}/chats/sessions/${sessionId}`);
      if (currentSessionId === sessionId) {
        onSessionSelect(null);
      }
      fetchSessions();
    } catch (err) {
      console.error("Error deleting session:", err);
      alert("Failed to delete chat session.");
    }
  };

  const handleNewChat = () => {
    setActiveTab('analysis'); 
    onSessionSelect(null);    
    if (window.innerWidth < 768) onClose();
  };

  return (
    <>
      {isOpen && (
        <div className="md:hidden fixed inset-0 bg-black/50 z-40 backdrop-blur-sm" onClick={onClose}></div>
      )}

      <aside className={`
        fixed md:relative z-50 w-64 h-screen bg-slate-900 text-white flex flex-col shadow-2xl transition-transform duration-300
        ${isOpen ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0
      `}>
        
        <div className="p-6 border-b border-slate-800 flex justify-between items-center shrink-0">
          <div>
            <h2 className="text-xl font-black tracking-tighter text-blue-400">AARVI</h2>
            <p className="text-[10px] text-slate-400 uppercase tracking-widest font-bold">Tender Intelligence</p>
          </div>
          <button onClick={onClose} className="md:hidden text-slate-400 hover:text-white"><X size={24} /></button>
        </div>
        
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="p-4 space-y-2 border-b border-slate-800 shrink-0">
            <button 
              onClick={handleNewChat} 
              className="flex items-center gap-3 w-full p-3 mb-4 rounded-xl font-bold bg-white text-slate-900 hover:bg-slate-200 transition-all shadow-sm"
            >
              <Plus size={18} /> New Analysis
            </button>

            {(userRole === 'admin' || userRole === 'project_manager') && (
              <>
                <button 
                  onClick={() => { setActiveTab('dashboard'); if (window.innerWidth < 768) onClose(); }} 
                  className={`flex items-center gap-3 w-full p-3 rounded-xl font-bold transition-all ${
                    activeTab === 'dashboard' ? 'bg-blue-600 text-white' : 'hover:bg-slate-800 text-slate-300'
                  }`}
                >
                  <FileText size={18} /> Master Dashboard
                </button>

                <button 
                  onClick={() => { setActiveTab('analytics'); if (window.innerWidth < 768) onClose(); }} 
                  className={`flex items-center gap-3 w-full p-3 rounded-xl font-bold transition-all ${
                    activeTab === 'analytics' ? 'bg-blue-600 text-white' : 'hover:bg-slate-800 text-slate-300'
                  }`}
                >
                  <BarChart2 size={18} /> Analytics Dashboard
                </button>
              </>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
            
            <div className="mb-4">
              <div className="relative group">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-blue-400 transition-colors" />
                <input 
                  type="text"
                  placeholder="Search conversations..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-slate-800/50 border border-slate-700 text-xs text-white pl-9 pr-8 py-2 rounded-xl outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 transition-all placeholder:text-slate-500"
                />
                {searchQuery && (
                  <button 
                    onClick={() => setSearchQuery('')}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                  >
                    <X size={12} />
                  </button>
                )}
              </div>
            </div>

            <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-3 px-2">Recent Analyses</p>
            <div className="space-y-1">
              {sessions.length === 0 ? (
                <p className="text-xs text-slate-500 px-2 italic">
                  {searchQuery ? "No matches found." : "No recent chats."}
                </p>
              ) : (
                sessions.map(chat => (
                  <ChatItem 
                    key={chat.session_id} 
                    chat={chat} 
                    currentSessionId={activeTab === 'analysis' ? currentSessionId : null}
                    onSelect={(id) => {
                      setActiveTab('analysis');
                      onSessionSelect(id);
                      if (window.innerWidth < 768) onClose();
                    }}
                    onRename={handleRename}
                    onDelete={handleDelete}
                  />
                ))
              )}
            </div>
          </div>
        </div>

        <div className="p-4 border-t border-slate-800 shrink-0">
          <button 
            onClick={handleLogout}
            className="flex items-center gap-3 w-full p-3 rounded-xl font-bold text-red-400 hover:bg-red-500/10 transition-all"
          >
            <LogOut size={18} /> Secure Logout
          </button>
        </div>

      </aside>
    </>
  );
};

export default Sidebar;