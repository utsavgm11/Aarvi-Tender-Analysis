import React, { useState } from 'react';
import axios from 'axios';
import { Shield, Zap, Database, ChevronRight, Lock } from 'lucide-react';

const LandingPage = ({ onLoginSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // This tells the app: Use the Render URL from Vercel, 
  // but fall back to your laptop if the variable isn't found.
  const API_BASE_URL = import.meta.env.VITE_API_URL || "https://attract-appeals-recorded-able.trycloudflare.com";
  
  const handleAuth = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // 1. Ask backend to authenticate
      const res = await axios.post(`${API_BASE_URL}/login`, { email, password });
      
      // 2. Save to Vault
      localStorage.setItem('userRole', res.data.role);
      localStorage.setItem('userEmail', res.data.email);
      // ✅ NEW: Save the Project Manager's Name for the Dashboards
      localStorage.setItem('managerName', res.data.manager_name || ''); 
      
      // 3. The Bulletproof Gate Opener
      if (typeof onLoginSuccess === 'function') {
          // Standard React transition if Vite is working properly
          onLoginSuccess(res.data.role);
      } else {
          // Fallback: If Vite drops the prop, reload the page. 
          // App.jsx will instantly read the localStorage and let you in!
          window.location.reload();
      }
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || "Invalid email or password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-[100dvh] w-full flex items-center justify-center bg-[#0f172a] overflow-x-hidden overflow-y-auto lg:overflow-hidden py-10 lg:py-0">
      {/* Animated Background Gradients */}
      <div className="absolute top-[-10%] left-[-10%] w-[80%] lg:w-[50%] h-[50%] bg-blue-600/20 rounded-full blur-[100px] lg:blur-[120px] animate-pulse"></div>
      <div className="absolute bottom-[-10%] right-[-10%] w-[80%] lg:w-[50%] h-[50%] bg-emerald-600/10 rounded-full blur-[100px] lg:blur-[120px]"></div>

      {/* Main Split Container */}
      <div className="relative z-10 w-full max-w-7xl px-4 sm:px-6 grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-16 items-center my-auto">
        
        {/* LEFT SIDE: 70% Content */}
        <div className="lg:col-span-7 space-y-6 sm:space-y-8 text-center lg:text-left mt-8 lg:mt-0">
          <div className="inline-block px-3 sm:px-4 py-1 sm:py-1.5 rounded-full border border-blue-500/30 bg-blue-500/10 text-blue-400 text-[10px] sm:text-xs font-bold uppercase tracking-[0.2em] backdrop-blur-md">
            Strategic Intelligence v3.0
          </div>

          <h1 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-black text-white tracking-tighter leading-tight">
            Aarvi <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400">Encon</span>
          </h1>
          
          <p className="text-sm sm:text-base md:text-lg lg:text-xl text-slate-400 max-w-2xl mx-auto lg:mx-0 font-medium leading-relaxed px-2 sm:px-0">
            The next-generation AI Bid Consultant. Cross-reference complex documents with our verified database of <strong>2,713+ historical tenders</strong> in a single, secure workspace.
          </p>

          {/* Feature Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 pt-4 sm:pt-6">
            <Feature icon={<Database size={18} className="sm:w-5 sm:h-5"/>} title="Historical Brain" />
            <Feature icon={<Zap size={18} className="sm:w-5 sm:h-5"/>} title="Agentic RAG" />
            <Feature icon={<Shield size={18} className="sm:w-5 sm:h-5"/>} title="Enterprise Security" />
          </div>
        </div>

        {/* RIGHT SIDE: 30% Login Form */}
        <div className="lg:col-span-5 relative w-full max-w-md mx-auto lg:max-w-none">
          <div className="bg-white/10 backdrop-blur-2xl border border-white/10 p-6 sm:p-8 md:p-10 rounded-[1.5rem] sm:rounded-[2rem] shadow-2xl relative overflow-hidden">
            
            {/* Subtle glow inside the card */}
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 to-emerald-500"></div>

            <h2 className="text-2xl sm:text-3xl font-black text-white mb-1 sm:mb-2 text-center lg:text-left">
              Welcome Back
            </h2>
            <p className="text-xs sm:text-sm text-slate-400 mb-6 sm:mb-8 font-medium text-center lg:text-left">
              Enter your credentials to access the vault.
            </p>

            <form onSubmit={handleAuth} className="space-y-4 sm:space-y-5">
              <div>
                <label className="block text-[10px] sm:text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5 sm:mb-2">Company Email</label>
                <div className="relative">
                  <input 
                    type="email" 
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    placeholder="name@aarviencon.com"
                    // Added text-base specifically to prevent iOS Safari from zooming in on input focus
                    className="w-full bg-slate-900/50 border border-white/10 text-white text-base sm:text-sm px-4 py-3 sm:py-3.5 rounded-xl outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-slate-600"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] sm:text-xs font-bold text-slate-400 uppercase tracking-wider mb-1.5 sm:mb-2">Password</label>
                <div className="relative">
                  <input 
                    type="password" 
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    placeholder="••••••••"
                    // Added text-base specifically to prevent iOS Safari from zooming in on input focus
                    className="w-full bg-slate-900/50 border border-white/10 text-white text-base sm:text-sm px-4 py-3 sm:py-3.5 rounded-xl outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-slate-600"
                  />
                  <Lock size={16} className="absolute right-4 top-3.5 sm:top-4 text-slate-500" />
                </div>
              </div>

              {/* Error Messages */}
              {error && (
                <div className="p-3 rounded-xl text-xs sm:text-sm font-bold bg-red-500/10 text-red-400 border border-red-500/20 text-center lg:text-left">
                  {error}
                </div>
              )}

              <button 
                type="submit" 
                disabled={loading}
                className="w-full py-3.5 sm:py-4 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white rounded-xl font-black text-base sm:text-lg shadow-[0_0_20px_rgba(37,99,235,0.3)] transition-all active:scale-[0.98] flex items-center justify-center gap-2 disabled:opacity-70 mt-2"
              >
                {loading ? 'Authenticating...' : 'Secure Login'}
                {!loading && <ChevronRight size={18} className="sm:w-[20px] sm:h-[20px]" />}
              </button>
            </form>
          </div>
        </div>
        
      </div>
    </div>
  );
};

const Feature = ({ icon, title }) => (
  <div className="flex items-center justify-center lg:justify-start gap-2 sm:gap-3 px-4 sm:px-5 py-3 sm:py-4 rounded-xl sm:rounded-2xl bg-white/5 border border-white/10 backdrop-blur-sm">
    <div className="p-1.5 sm:p-2 bg-blue-500/20 rounded-lg text-blue-400 shrink-0">{icon}</div>
    <span className="text-white text-xs sm:text-sm font-bold uppercase tracking-widest">{title}</span>
  </div>
);

export default LandingPage;