import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';
import { Send, FileUp, Loader2, Bot, User, CheckCircle2 } from 'lucide-react';
import DecisionCard from '../components/ui/DecisionCard';

// Dynamic API URL
const API_BASE_URL = import.meta.env.VITE_API_URL || "https://attract-appeals-recorded-able.trycloudflare.com";

// 🎯 FIX 1: Helper to reliably retrieve sanitized user email
const getCleanUserEmail = () => {
  const email = localStorage.getItem('userEmail') || localStorage.getItem('email') || 'unknown_user@aarviencon.com';
  return email.toLowerCase().trim();
};

const AnalysisChat = ({ currentSessionId, onSessionSelect, onChatUpdated }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeTender, setActiveTender] = useState(null);
  const [progress, setProgress] = useState(null);
  
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const pollingInterval = useRef(null);

  // Prevents the history fetch from wiping the screen during an upload
  const isOperationActive = useRef(false);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading, progress]);

  // Fetch History
  useEffect(() => {
    if (isOperationActive.current) return;

    if (currentSessionId) {
      setIsLoading(true);
      axios.get(`${API_BASE_URL}/chats/history/${currentSessionId}`)
        .then(res => {
          let restoredTender = null;
          const loadedMessages = (res.data || []).map(m => {
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
      const userEmail = getCleanUserEmail();

      const contentStr = typeof content === 'object' 
        ? JSON.stringify({ isTenderResult: true, data: content }) 
        : content;

      await axios.post(`${API_BASE_URL}/chats/message`, {
        session_id: sessionId,
        role: role,
        content: contentStr,
        title: title,
        user_email: userEmail
      });

      // 🎯 FIX 2: Trigger immediate sidebar refresh so the new chat shows up instantly
      window.dispatchEvent(new Event('refresh-sidebar'));
      if (onChatUpdated) onChatUpdated(); 
    } catch (e) {
      console.error("❌ Failed to save message to DB:", e);
    }
  };

  const handleFileUpload = async (event) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    isOperationActive.current = true;

    let sid = currentSessionId;
    if (!sid) {
      sid = uuidv4();
      onSessionSelect(sid);
    }

    const fileNames = Array.from(files).map(f => f.name).join(', ');
    const userMsg = `📄 Uploading ${files.length} file(s): ${fileNames}`;
    
    setMessages(prev => [...prev, { type: 'user', text: userMsg }]);
    setIsLoading(true);

    // 🎯 FIX 3: Save initial user upload message immediately to open database session
    await persistMessage(sid, 'user', userMsg, `Analysis: ${files[0].name.substring(0, 25)}`);

    const taskId = `task_${uuidv4()}`;
    setProgress({ current: 0, total: 100 }); 

    const userEmail = getCleanUserEmail();

    const formData = new FormData();
    formData.append('task_id', taskId);
    formData.append('user_email', userEmail);

    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }

    try {
      const uploadRes = await axios.post(`${API_BASE_URL}/analyze-tender`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      if (uploadRes.data.error) {
        throw new Error(uploadRes.data.error);
      }

      pollingInterval.current = setInterval(async () => {
        try {
          const res = await axios.get(`${API_BASE_URL}/progress/${taskId}`);
          
          if (res.data.status === "completed") {
            clearInterval(pollingInterval.current);
            const tenderData = res.data.result.aarvi_intelligence;
            
            if (tenderData) {
              setActiveTender(tenderData);
              setMessages(prev => [...prev, { type: 'ai', result: tenderData }]);
              
              // 🎯 FIX 4: Generate structured session title from tender data
              const sessionTitle = (tenderData.tender_no && tenderData.tender_no !== "Not Specified")
                ? `${tenderData.tender_no} - ${tenderData.client_name || 'Analysis'}`
                : (tenderData.client_name || "Tender Analysis");

              await persistMessage(sid, 'ai', tenderData, sessionTitle);
            }
            
            setIsLoading(false);
            setProgress(null);
            isOperationActive.current = false;
            if (fileInputRef.current) fileInputRef.current.value = '';
            
          } else if (res.data.status === "error") {
            clearInterval(pollingInterval.current);
            throw new Error(res.data.error);
            
          } else if (res.data.total > 0) {
            setProgress({ current: res.data.current, total: res.data.total });
          }
        } catch (pollErr) {
          console.log("Polling check missed, retrying next cycle...");
        }
      }, 3000);

    } catch (e) {
      const errorText = `Analysis failed: ${e.response?.data?.detail || e.message}`;
      setMessages(prev => [...prev, { type: 'ai', text: errorText }]);
      setIsLoading(false);
      setProgress(null);
      isOperationActive.current = false;
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleChat = async () => {
    if (!input.trim()) return;
    isOperationActive.current = true;
    
    let sid = currentSessionId;
    let isNewSession = false;
    if (!sid) {
      sid = uuidv4();
      isNewSession = true;
      onSessionSelect(sid);
    }

    const userQuery = input;
    setMessages(prev => [...prev, { type: 'user', text: userQuery }]);
    setInput('');
    setIsLoading(true);

    // 🎯 FIX 5: Auto-generate title if this is the start of a session
    let chatTitle = null;
    if (isNewSession || messages.length <= 1) {
      try {
        const titleRes = await axios.post(`${API_BASE_URL}/chats/generate-title`, { first_message: userQuery });
        chatTitle = titleRes.data?.title || userQuery.substring(0, 30);
      } catch (e) {
        chatTitle = userQuery.substring(0, 30);
      }
    }

    await persistMessage(sid, 'user', userQuery, chatTitle);

    const userEmail = getCleanUserEmail();

    try {
      const response = await axios.post(`${API_BASE_URL}/chat/`, { 
        query: userQuery,
        context: activeTender || {},
        full_text: activeTender?.full_text || "",
        user_email: userEmail
      });
      
      const aiReply = response.data.reply || response.data;
      setMessages(prev => [...prev, { type: 'ai', text: aiReply }]);
      
      await persistMessage(sid, 'ai', aiReply);
    } catch (e) {
      setMessages(prev => [...prev, { type: 'ai', text: "Strategic memory error." }]);
    } finally {
      setIsLoading(false);
      isOperationActive.current = false;
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-50 relative">
      {activeTender && (
        <div className="bg-blue-900 text-white px-3 sm:px-4 py-2 flex items-center justify-between text-[10px] sm:text-xs font-medium shrink-0 shadow-md z-10">
          <div className="flex items-center gap-1.5 sm:gap-2 min-w-0 mr-2">
            <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />
            <span className="truncate">Consulting: {activeTender.tender_no || "Active Tender"}</span>
          </div>
          <span className="opacity-60 truncate max-w-[100px] sm:max-w-[200px] md:max-w-xs shrink-0 text-right">
            {activeTender.client_name}
          </span>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-3 sm:p-4 md:p-6 space-y-4 sm:space-y-6 custom-scrollbar">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.type === 'user' ? 'justify-end' : 'justify-start'}`}>
            {m.result ? (
              <DecisionCard result={m.result} onClose={() => {}} />
            ) : (
              <div className={`flex items-start gap-2 sm:gap-3 max-w-[92%] sm:max-w-[85%] md:max-w-2xl ${m.type === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`p-1.5 sm:p-2 rounded-lg shrink-0 ${m.type === 'user' ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-600'}`}>
                  {m.type === 'ai' ? <Bot size={16} className="sm:w-[18px] sm:h-[18px]" /> : <User size={16} className="sm:w-[18px] sm:h-[18px]" />}
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
        
        {isLoading && (
          <div className="flex justify-start my-4">
            {progress ? (
              <div className="w-full max-w-2xl bg-indigo-50 border border-indigo-100 p-3 sm:p-5 rounded-xl sm:rounded-2xl flex flex-col md:flex-row items-center justify-between gap-3 sm:gap-4 shadow-sm animate-pulse ml-0 sm:ml-10 md:ml-12">
                <div className="flex items-center gap-2 sm:gap-3">
                  <Loader2 className="animate-spin text-indigo-600 shrink-0" size={18} />
                  <span className="text-indigo-900 font-bold text-xs sm:text-sm tracking-wide uppercase text-center sm:text-left">AI Engine Scanning Document...</span>
                </div>
                <div className="flex-1 w-full mx-0 sm:mx-4">
                  <div className="h-2 sm:h-2.5 bg-indigo-200 rounded-full overflow-hidden">
                    <div 
                      className="bg-indigo-600 h-full transition-all duration-300 ease-out" 
                      style={{ width: `${(progress.current / progress.total) * 100}%` }}
                    ></div>
                  </div>
                </div>
                <span className="text-indigo-700 font-black text-xs sm:text-sm shrink-0">
                  Pages ({progress.current}/{progress.total})
                </span>
              </div>
            ) : (
              <div className="flex items-center gap-2 sm:gap-3 text-slate-400 animate-pulse text-xs sm:text-sm ml-0 sm:ml-10 md:ml-12">
                <Loader2 size={14} className="animate-spin sm:w-[16px] sm:h-[16px]" />
                Strategic Consultant is thinking...
              </div>
            )}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input section */}
      <div className="p-2 sm:p-4 bg-white border-t shrink-0">
        <div className="max-w-4xl mx-auto flex items-center gap-1.5 sm:gap-2 bg-slate-100 rounded-xl sm:rounded-2xl p-1 sm:p-1.5 border focus-within:border-blue-400 transition-all">
          <label className="cursor-pointer p-2 sm:p-2.5 hover:bg-white rounded-lg sm:rounded-xl text-slate-500 transition-colors">
            <FileUp size={18} className="sm:w-[22px] sm:h-[22px]" />
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
            className="flex-1 bg-transparent p-2 sm:p-2.5 outline-none text-xs sm:text-sm min-w-0" 
            placeholder={activeTender ? "Ask about margins, risks..." : "Upload your tender files..."} 
          />
          <button 
            onClick={handleChat} 
            disabled={!input.trim()}
            className={`p-2 sm:p-2.5 rounded-lg sm:rounded-xl transition-all shrink-0 ${input.trim() ? 'bg-blue-600 text-white shadow-md hover:bg-blue-700' : 'text-slate-400'}`}
          >
            <Send size={16} className="sm:w-[20px] sm:h-[20px]" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default AnalysisChat;