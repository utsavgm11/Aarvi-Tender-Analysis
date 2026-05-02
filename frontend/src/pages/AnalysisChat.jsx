import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';
import { Send, FileUp, Loader2, Bot, User, CheckCircle2 } from 'lucide-react';
import DecisionCard from '../components/ui/DecisionCard';

// Added onChatUpdated to trigger sidebar refreshes
const AnalysisChat = ({ currentSessionId, onSessionSelect, onChatUpdated }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeTender, setActiveTender] = useState(null);
  
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  // 1. Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // 2. Fetch History when currentSessionId changes
  useEffect(() => {
    if (currentSessionId) {
      setIsLoading(true);
      axios.get(`http://127.0.0.1:8001/chats/history/${currentSessionId}`)
        .then(res => {
          let restoredTender = null;
          
          const loadedMessages = res.data.map(m => {
            try {
              // FIX: Use m.content and m.role to match FastAPI backend
              const parsed = JSON.parse(m.content); 
              if (parsed && parsed.isTenderResult) {
                restoredTender = parsed.data; // Restore context
                return { type: m.role, result: parsed.data };
              }
            } catch (e) {
              // If it's not JSON, it's a normal text message
            }
            // FIX: Map backend 'role' to 'type', and 'content' to 'text'
            return { type: m.role, text: m.content };
          });
          
          setMessages(loadedMessages);
          setActiveTender(restoredTender); 
        })
        .catch(err => console.error("Error loading history:", err))
        .finally(() => setIsLoading(false));
    } else {
      // New Chat State
      setMessages([{ type: 'ai', text: 'Welcome! Please upload your tender document(s) to begin the strategic analysis.' }]);
      setActiveTender(null);
    }
  }, [currentSessionId]);

  // 3. Helper to save messages to the database
  const persistMessage = async (sessionId, role, content, title = null) => {
    try {
      const contentStr = typeof content === 'object' 
        ? JSON.stringify({ isTenderResult: true, data: content }) 
        : content;

      await axios.post('http://127.0.0.1:8001/chats/message', {
        session_id: sessionId,
        role: role,
        content: contentStr,
        title: title
      });
      
      // FIX: Trigger the sidebar to refresh so new chats appear instantly
      if (onChatUpdated) onChatUpdated(); 
      
    } catch (e) {
      console.error("Failed to save message to DB", e);
    }
  };

  // 4. Handle File Uploads
  const handleFileUpload = async (event) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    let sid = currentSessionId;
    let isNewSession = false;
    if (!sid) {
      sid = uuidv4();
      isNewSession = true;
      onSessionSelect(sid);
    }

    const fileNames = Array.from(files).map(f => f.name).join(', ');
    const userMsg = `📄 Uploading ${files.length} file(s): ${fileNames}`;
    
    setMessages(prev => [...prev, { type: 'user', text: userMsg }]);
    setIsLoading(true);

    let chatTitle = "New Analysis";
    if (isNewSession) {
      try {
        const titleRes = await axios.post('http://127.0.0.1:8001/chats/generate-title', { first_message: userMsg });
        chatTitle = titleRes.data.title;
      } catch (e) {}
    }

    await persistMessage(sid, 'user', userMsg, isNewSession ? chatTitle : null);

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }

    try {
      const response = await axios.post('http://127.0.0.1:8001/analyze-tender', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      const tenderData = response.data.aarvi_intelligence;
      if (tenderData) setActiveTender(tenderData);
      
      setMessages(prev => [...prev, { type: 'ai', result: tenderData }]);
      await persistMessage(sid, 'ai', tenderData); 

    } catch (e) {
      const errorMsg = e.response?.data?.detail || e.message; 
      const errorText = `Analysis failed: ${errorMsg}`;
      setMessages(prev => [...prev, { type: 'ai', text: errorText }]);
      await persistMessage(sid, 'ai', errorText);
    } finally {
      setIsLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // 5. Handle Text Chat
  const handleChat = async () => {
    if (!input.trim()) return;
    
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

    let chatTitle = "New Analysis";
    if (isNewSession) {
      try {
        const titleRes = await axios.post('http://127.0.0.1:8001/chats/generate-title', { first_message: userQuery });
        chatTitle = titleRes.data.title;
      } catch (e) {}
    }

    await persistMessage(sid, 'user', userQuery, isNewSession ? chatTitle : null);

    try {
      const response = await axios.post('http://127.0.0.1:8001/chat/', { 
        query: userQuery,
        context: activeTender || {},
        full_text: activeTender?.full_text || "" 
      });
      
      const aiReply = response.data.reply;
      setMessages(prev => [...prev, { type: 'ai', text: aiReply }]);
      await persistMessage(sid, 'ai', aiReply);

    } catch (e) {
      const errorText = "I'm having trouble accessing my strategic memory right now.";
      setMessages(prev => [...prev, { type: 'ai', text: errorText }]);
      await persistMessage(sid, 'ai', errorText);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-50 relative">
      {/* Context Indicator */}
      {activeTender && (
        <div className="bg-blue-900 text-white px-4 py-2 flex items-center justify-between text-xs font-medium shrink-0 shadow-md z-10">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={14} className="text-emerald-400" />
            <span>Consulting on: {activeTender.tender_no || "Active Tender"}</span>
          </div>
          <span className="opacity-60 truncate max-w-[200px]">{activeTender.client_name}</span>
        </div>
      )}

      {/* Message Feed */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6">
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
        {isLoading && (
          <div className="flex items-center gap-3 text-slate-400 animate-pulse text-sm ml-12">
            <Loader2 size={16} className="animate-spin" />
            Strategic Consultant is thinking...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Chat Input Bar */}
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