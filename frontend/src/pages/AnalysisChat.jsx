import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';
import { Send, FileUp, Loader2, Bot, User, CheckCircle2 } from 'lucide-react';
import DecisionCard from '../components/ui/DecisionCard';

const AnalysisChat = ({ currentSessionId, onSessionSelect, onChatUpdated }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeTender, setActiveTender] = useState(null);
  const [progress, setProgress] = useState(null);
  
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const pollingInterval = useRef(null);
  
  // --- NEW: THE LOCK ---
  // This prevents the history fetch from wiping the screen during an upload
  const isOperationActive = useRef(false);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading, progress]);

  // Fetch History
  useEffect(() => {
    // LOCK CHECK: If we are uploading, DO NOT fetch history and wipe the screen
    if (isOperationActive.current) return;

    if (currentSessionId) {
      setIsLoading(true);
      axios.get(`http://127.0.0.1:8001/chats/history/${currentSessionId}`)
        .then(res => {
          let restoredTender = null;
          const loadedMessages = res.data.map(m => {
            try {
              const parsed = JSON.parse(m.content); 
              if (parsed && parsed.isTenderResult) {
                restoredTender = parsed.data;
                return { type: m.role, result: parsed.data };
              }
            } catch (e) {}
            return { type: m.role, text: m.content };
          });
          setMessages(loadedMessages);
          setActiveTender(restoredTender); 
        })
        .catch(err => console.error("Error loading history:", err))
        .finally(() => setIsLoading(false));
    } else {
      setMessages([{ type: 'ai', text: 'Welcome! Please upload your tender document(s) to begin the strategic analysis.' }]);
      setActiveTender(null);
    }
  }, [currentSessionId]);

  const persistMessage = async (sessionId, role, content, title = null) => {
  try {
    // 1. Get the logged-in user's email
    const userEmail = localStorage.getItem('userEmail');

    // 2. Format the content (keeping your logic for tender results)
    const contentStr = typeof content === 'object' 
      ? JSON.stringify({ isTenderResult: true, data: content }) 
      : content;

    // 3. Dynamic API URL (Better than hardcoding)
    const API_BASE_URL = import.meta.env.VITE_API_URL || "https://aarvi-tender-api.onrender.com";

    await axios.post(`${API_BASE_URL}/chats/message`, {
      session_id: sessionId,
      role: role,
      content: contentStr,
      title: title,
      user_email: userEmail // ✅ CRITICAL: Linking the message to the user
    });

    if (onChatUpdated) onChatUpdated(); 
  } catch (e) {
    console.error("❌ Failed to save message to DB:", e);
    // If you see 'Network Error' here, ensure your Python terminal is running
  }
};

  const handleFileUpload = async (event) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    // --- ACTIVATE LOCK ---
    isOperationActive.current = true;

    let sid = currentSessionId;
    let isNewSession = false;
    if (!sid) {
      sid = uuidv4();
      isNewSession = true;
      onSessionSelect(sid);
    }

    const fileNames = Array.from(files).map(f => f.name).join(', ');
    const userMsg = `📄 Uploading ${files.length} file(s): ${fileNames}`;
    
    // Functional update to preserve state
    setMessages(prev => [...prev, { type: 'user', text: userMsg }]);
    setIsLoading(true);

    const taskId = `task_${uuidv4()}`;
    // Initialize UI progress so the bar appears immediately
    setProgress({ current: 0, total: 100 }); 

    const formData = new FormData();
    formData.append('task_id', taskId); // TASK ID FIRST
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }

    // --- POLLING LOGIC ---
    pollingInterval.current = setInterval(async () => {
      try {
        const res = await axios.get(`http://127.0.0.1:8001/progress/${taskId}`);
        if (res.data && res.data.total > 0) {
          setProgress(res.data);
          if (res.data.current === res.data.total) {
            clearInterval(pollingInterval.current);
          }
        }
      } catch (err) {
        // Silently handle 404s until backend starts the task
      }
    }, 1000);

    try {
      const response = await axios.post('http://127.0.0.1:8001/analyze-tender', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      const tenderData = response.data.aarvi_intelligence;
      if (tenderData) {
        setActiveTender(tenderData);
        setMessages(prev => [...prev, { type: 'ai', result: tenderData }]);
        await persistMessage(sid, 'ai', tenderData);
      }
    } catch (e) {
      const errorText = `Analysis failed: ${e.response?.data?.detail || e.message}`;
      setMessages(prev => [...prev, { type: 'ai', text: errorText }]);
    } finally {
      // --- CLEANUP AND UNLOCK ---
      setIsLoading(false);
      setProgress(null);
      isOperationActive.current = false; // RELEASE THE LOCK
      clearInterval(pollingInterval.current);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleChat = async () => {
    if (!input.trim()) return;
    isOperationActive.current = true; // LOCK
    
    let sid = currentSessionId;
    if (!sid) {
      sid = uuidv4();
      onSessionSelect(sid);
    }

    const userQuery = input;
    setMessages(prev => [...prev, { type: 'user', text: userQuery }]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await axios.post('http://127.0.0.1:8001/chat/', { 
        query: userQuery,
        context: activeTender || {},
        full_text: activeTender?.full_text || "" 
      });
      
      setMessages(prev => [...prev, { type: 'ai', text: response.data.reply }]);
      await persistMessage(sid, 'ai', response.data.reply);
    } catch (e) {
      setMessages(prev => [...prev, { type: 'ai', text: "Strategic memory error." }]);
    } finally {
      setIsLoading(false);
      isOperationActive.current = false; // UNLOCK
    }
  };

  const API_BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8001";

  return (
    <div className="flex flex-col h-full bg-slate-50 relative">
      {activeTender && (
        <div className="bg-blue-900 text-white px-4 py-2 flex items-center justify-between text-xs font-medium shrink-0 shadow-md z-10">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} className="text-emerald-400" />
            <span>Consulting on: {activeTender.tender_no || "Active Tender"}</span>
          </div>
          <span className="opacity-60 truncate max-w-[200px]">{activeTender.client_name}</span>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.type === 'user' ? 'justify-end' : 'justify-start'}`}>
            {m.result ? (
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
        
        {isLoading && (
          <div className="flex justify-start my-4">
            {progress ? (
              <div className="w-full max-w-2xl bg-indigo-50 border border-indigo-100 p-5 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-4 shadow-sm animate-pulse ml-12">
                <div className="flex items-center gap-3">
                  <Loader2 className="animate-spin text-indigo-600" size={20} />
                  <span className="text-indigo-900 font-bold text-sm tracking-wide uppercase">AI Engine Scanning Document...</span>
                </div>
                <div className="flex-1 w-full mx-4">
                  <div className="h-2.5 bg-indigo-200 rounded-full overflow-hidden">
                    <div 
                      className="bg-indigo-600 h-full transition-all duration-300 ease-out" 
                      style={{ width: `${(progress.current / progress.total) * 100}%` }}
                    ></div>
                  </div>
                </div>
                <span className="text-indigo-700 font-black text-sm">
                  Pages ({progress.current}/{progress.total})
                </span>
              </div>
            ) : (
              <div className="flex items-center gap-3 text-slate-400 animate-pulse text-sm ml-12">
                <Loader2 size={16} className="animate-spin" />
                Strategic Consultant is thinking...
              </div>
            )}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input section remains the same... */}
      <div className="p-4 bg-white border-t shrink-0">
        <div className="max-w-4xl mx-auto flex items-center gap-2 bg-slate-100 rounded-2xl p-1.5 border focus-within:border-blue-400 transition-all">
          <label className="cursor-pointer p-2.5 hover:bg-white rounded-xl text-slate-500 transition-colors">
            <FileUp size={22} />
            <input 
              type="file" 
              className="hidden" 
              ref={fileInputRef} 
              onChange={handleFileUpload} 
              accept=".pdf,.doc,.docx" 
              multiple 
            />
          </label>
          <input 
            value={input} 
            onChange={(e) => setInput(e.target.value)} 
            onKeyDown={(e) => e.key === 'Enter' && handleChat()} 
            className="flex-1 bg-transparent p-2.5 outline-none text-sm" 
            placeholder={activeTender ? "Ask about margins, risks, or technicals..." : "Upload your tender files..."} 
          />
          <button 
            onClick={handleChat} 
            disabled={!input.trim()}
            className={`p-2.5 rounded-xl transition-all ${input.trim() ? 'bg-blue-600 text-white shadow-md hover:bg-blue-700' : 'text-slate-400'}`}
          >
            <Send size={20} />
          </button>
        </div>
      </div>
    </div>
  );
};

export default AnalysisChat;