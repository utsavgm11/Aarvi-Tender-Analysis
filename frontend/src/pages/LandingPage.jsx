import React, { useState } from 'react';
import axios from 'axios';
import { Shield, Zap, Database, ChevronRight, Lock } from 'lucide-react';

const LandingPage = ({ onLoginSuccess }) => {
  const [isLoginMode, setIsLoginMode] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // This tells the app: Use the Render URL from Vercel, 
// but fall back to your laptop if the variable isn't found.
  const API_BASE_URL = import.meta.env.VITE_API_URL || "https://aarvi-tender-api.onrender.com";
  
  const handleAuth = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isLoginMode) {
        // 1. Ask backend
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
        
      } else {
        // SIGNUP
        await axios.post(`${API_BASE_URL}/signup`, { email, password });
        setIsLoginMode(true);
        setError("Account created successfully! Please log in.");
      }
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || "An error occurred connecting to the server.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen w-full flex items-center justify-center bg-[#0f172a] overflow-hidden">
      {/* Animated Background Gradients */}
      <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-blue-600/20 rounded-full blur-[120px] animate-pulse"></div>
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-emerald-600/10 rounded-full blur-[120px]"></div>

      {/* Main Split Container */}
      <div className="relative z-10 w-full max-w-7xl px-6 grid grid-cols-1 lg:grid-cols-12 gap-16 items-center">
        
        {/* LEFT SIDE: 70% Content */}
        <div className="lg:col-span-7 space-y-8 text-left">
          <div className="inline-block px-4 py-1.5 rounded-full border border-blue-500/30 bg-blue-500/10 text-blue-400 text-xs font-bold uppercase tracking-[0.2em] backdrop-blur-md">
            Strategic Intelligence v3.0
          </div>

          <h1 className="text-5xl md:text-7xl font-black text-white tracking-tighter leading-tight">
            Aarvi <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400">Encon</span>
          </h1>
          
          <p className="text-lg md:text-xl text-slate-400 max-w-2xl font-medium leading-relaxed">
            The next-generation AI Bid Consultant. Cross-reference complex documents with our verified database of <strong>2,713+ historical tenders</strong> in a single, secure workspace.
          </p>

          {/* Feature Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-6">
            <Feature icon={<Database size={20}/>} title="Historical Brain" />
            <Feature icon={<Zap size={20}/>} title="Agentic RAG" />
            <Feature icon={<Shield size={20}/>} title="Enterprise Security" />
          </div>
        </div>

        {/* RIGHT SIDE: 30% Login Form */}
        <div className="lg:col-span-5 relative">
          <div className="bg-white/10 backdrop-blur-2xl border border-white/10 p-8 md:p-10 rounded-[2rem] shadow-2xl relative overflow-hidden">
            
            {/* Subtle glow inside the card */}
            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 to-emerald-500"></div>

            <h2 className="text-3xl font-black text-white mb-2">
              {isLoginMode ? 'Welcome Back' : 'Create Account'}
            </h2>
            <p className="text-sm text-slate-400 mb-8 font-medium">
              {isLoginMode ? 'Enter your credentials to access the vault.' : 'Restricted to @aarviencon.com domain only.'}
            </p>

            <form onSubmit={handleAuth} className="space-y-5">
              <div>
                <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Company Email</label>
                <div className="relative">
                  <input 
                    type="email" 
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    placeholder="name@aarviencon.com"
                    className="w-full bg-slate-900/50 border border-white/10 text-white px-4 py-3 rounded-xl outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-slate-600"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Password</label>
                <div className="relative">
                  <input 
                    type="password" 
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    placeholder="••••••••"
                    className="w-full bg-slate-900/50 border border-white/10 text-white px-4 py-3 rounded-xl outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-slate-600"
                  />
                  <Lock size={16} className="absolute right-4 top-3.5 text-slate-500" />
                </div>
              </div>

              {/* Error / Success Messages */}
              {error && (
                <div className={`p-3 rounded-xl text-sm font-bold ${error.includes('successfully') ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'}`}>
                  {error}
                </div>
              )}

              <button 
                type="submit" 
                disabled={loading}
                className="w-full py-4 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white rounded-xl font-black text-lg shadow-[0_0_20px_rgba(37,99,235,0.3)] transition-all active:scale-[0.98] flex items-center justify-center gap-2 disabled:opacity-70"
              >
                {loading ? 'Authenticating...' : (isLoginMode ? 'Secure Login' : 'Register Account')}
                {!loading && <ChevronRight size={20} />}
              </button>
            </form>

            <div className="mt-6 text-center">
              <button 
                onClick={() => { setIsLoginMode(!isLoginMode); setError(''); }}
                className="text-sm font-bold text-slate-400 hover:text-white transition-colors"
              >
                {isLoginMode ? "Don't have an account? Sign up" : "Already have an account? Log in"}
              </button>
            </div>
          </div>
        </div>
        
      </div>
    </div>
  );
};

const Feature = ({ icon, title }) => (
  <div className="flex items-center justify-start gap-3 px-5 py-4 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-sm">
    <div className="p-2 bg-blue-500/20 rounded-lg text-blue-400">{icon}</div>
    <span className="text-white text-sm font-bold uppercase tracking-widest">{title}</span>
  </div>
);

export default LandingPage;