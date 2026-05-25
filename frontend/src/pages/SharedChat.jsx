import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Bot, User, Loader2, ShieldCheck, Plus } from 'lucide-react';
import DecisionCard from '../components/ui/DecisionCard';

const SharedChat = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isCloning, setIsCloning] = useState(false);

  useEffect(() => {
    // Fetch the read-only history
    axios.get(`http://127.0.0.1:8001/chats/history/${id}`)
      .then(res => {
        const loadedMessages = res.data.map(m => {
          try {
            const parsed = JSON.parse(m.content); 
            if (parsed && parsed.isTenderResult) {
              return { type: m.role, result: parsed.data };
            }
          } catch (e) {}
          return { type: m.role, text: m.content };
        });
        setMessages(loadedMessages);
      })
      .catch(err => console.error("Error loading shared history:", err))
      .finally(() => setLoading(false));
  }, [id]);

  // Handler to clone the chat and redirect the user
  const handleImportChat = async () => {
    setIsCloning(true);
    try {
      const res = await axios.post(`http://127.0.0.1:8001/chats/clone/${id}`);
      const newId = res.data.new_session_id;
      
      // Redirect to main dashboard, passing the new cloned ID in the state
      navigate('/', { state: { importedSessionId: newId } });
    } catch (err) {
      console.error(err);
      alert("Failed to import chat. Ensure the backend is online.");
      setIsCloning(false);
    }
  };

  if (loading) {
    return (
      <div className="h-[100dvh] flex flex-col items-center justify-center bg-slate-50 gap-3">
        <Loader2 size={32} className="animate-spin text-blue-600" />
        <p className="text-sm text-slate-500 font-medium animate-pulse">Loading secure analysis...</p>
      </div>
    );
  }

  return (
    <div className="min-h-[100dvh] bg-slate-50 py-6 sm:py-10 px-3 sm:px-6">
      <div className="max-w-4xl lg:max-w-5xl mx-auto">
        
        {/* Header Bar */}
        <div className="bg-white p-4 sm:p-6 rounded-2xl shadow-sm border border-slate-200 mb-6 flex flex-col sm:flex-row justify-between items-center gap-4 sm:gap-6 text-center sm:text-left">
          <div className="flex flex-col sm:flex-row items-center gap-3">
            <ShieldCheck className="text-emerald-500 w-10 h-10 sm:w-8 sm:h-8 shrink-0" />
            <div>
              <h1 className="font-black text-slate-800 text-lg sm:text-xl leading-tight">Shared Tender Analysis</h1>
              <p className="text-[11px] sm:text-xs text-slate-500 mt-0.5">Read-only view provided by Aarvi Intelligence</p>
            </div>
          </div>
          
          <button 
            onClick={handleImportChat}
            disabled={isCloning}
            className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700 text-white px-5 sm:px-6 py-3 sm:py-2.5 rounded-xl font-bold text-sm shadow-lg shadow-blue-200 transition-all active:scale-95 flex items-center justify-center gap-2 disabled:opacity-50 shrink-0"
          >
            {isCloning ? <Loader2 size={18} className="animate-spin" /> : <Plus size={18} />}
            {isCloning ? "Importing..." : "Continue this Chat"}
          </button>
        </div>

        {/* Message Feed */}
        <div className="space-y-6">
          {messages.map((m, i) => (
            // Added w-full here so the container spans the whole screen width
            <div key={i} className={`flex w-full ${m.type === 'user' ? 'justify-end' : 'justify-start'}`}>
              
              {m.type === 'ai' && m.result ? (
                // Added a w-full wrapper to prevent the DecisionCard from shrinking
                <div className="w-full">
                  <DecisionCard result={m.result} onClose={() => {}} />
                </div>
              ) : (
                
                <div className={`flex items-start gap-2 sm:gap-3 max-w-[92%] sm:max-w-[85%] md:max-w-2xl ${m.type === 'user' ? 'flex-row-reverse' : ''}`}>
                  <div className={`p-1.5 sm:p-2 rounded-lg shrink-0 ${m.type === 'user' ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-600'}`}>
                    {m.type === 'ai' ? <Bot size={16} className="sm:w-[18px] sm:h-[18px]"/> : <User size={16} className="sm:w-[18px] sm:h-[18px]"/>}
                  </div>
                  <div className={`p-3 sm:p-4 rounded-xl sm:rounded-2xl shadow-sm text-xs sm:text-sm leading-relaxed whitespace-pre-wrap break-words ${
                    m.type === 'user' ? 'bg-blue-600 text-white rounded-tr-none' : 'bg-white border rounded-tl-none text-slate-800'
                  }`}>
                    {m.text}
                  </div>
                </div>
                
              )}
            </div>
          ))}

          {messages.length === 0 && (
            <div className="text-center p-10 text-slate-400 text-sm sm:text-base">
              This shared session contains no messages.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SharedChat;