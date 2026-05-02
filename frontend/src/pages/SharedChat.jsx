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
      <div className="h-screen flex flex-col items-center justify-center bg-slate-50 gap-3">
        <Loader2 size={32} className="animate-spin text-blue-600" />
        <p className="text-sm text-slate-500 font-medium">Loading secure analysis...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 py-10 px-4">
      <div className="max-w-4xl mx-auto">
        
        {/* Header Bar */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 mb-6 flex flex-col md:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-3">
            <ShieldCheck className="text-emerald-500" size={32} />
            <div>
              <h1 className="font-black text-slate-800 text-lg">Shared Tender Analysis</h1>
              <p className="text-xs text-slate-500">Read-only view provided by Aarvi Intelligence</p>
            </div>
          </div>
          
          <button 
            onClick={handleImportChat}
            disabled={isCloning}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-xl font-bold text-sm shadow-lg shadow-blue-200 transition-all flex items-center gap-2 disabled:opacity-50"
          >
            {isCloning ? <Loader2 size={18} className="animate-spin" /> : <Plus size={18} />}
            {isCloning ? "Importing..." : "Continue this Chat"}
          </button>
        </div>

        {/* Message Feed */}
        <div className="space-y-6">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.type === 'user' ? 'justify-end' : 'justify-start'}`}>
              {m.type === 'ai' && m.result ? (
                <DecisionCard result={m.result} onClose={() => {}} />
              ) : (
                <div className={`flex items-start gap-3 max-w-[85%] md:max-w-2xl ${m.type === 'user' ? 'flex-row-reverse' : ''}`}>
                  <div className={`p-2 rounded-lg shrink-0 ${m.type === 'user' ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-600'}`}>
                    {m.type === 'ai' ? <Bot size={18} /> : <User size={18} />}
                  </div>
                  <div className={`p-4 rounded-2xl shadow-sm text-sm leading-relaxed whitespace-pre-wrap ${
                    m.type === 'user' ? 'bg-blue-600 text-white rounded-tr-none' : 'bg-white border rounded-tl-none text-slate-800'
                  }`}>
                    {m.text}
                  </div>
                </div>
              )}
            </div>
          ))}

          {messages.length === 0 && (
            <div className="text-center p-10 text-slate-400">
              This shared session contains no messages.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SharedChat;