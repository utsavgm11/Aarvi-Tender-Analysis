import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { 
  Shield, Users, Trash2, Plus, RefreshCw, 
  Search, X, Save, Edit3, Mail, ShieldCheck,
  Activity, FileText, MessageSquare, Calendar, 
  TrendingUp, IndianRupee, Clock, BarChart3
} from 'lucide-react';

// 🎯 UNIVERSAL API ROUTING PATHWAY
const API_BASE_URL = (import.meta.env.VITE_API_URL || "https://attract-appeals-recorded-able.trycloudflare.com").replace(/\/$/, "");

const AdminControlWorkspace = () => {
  const [users, setUsers] = useState([]);
  const [logs, setLogs] = useState([]); // 📊 Stores the raw backend tracking array
  const [loading, setLoading] = useState(true);
  
  // UI Controls
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState('add'); 
  const [searchTerm, setSearchTerm] = useState('');
  const [timeFilter, setTimeFilter] = useState('month'); // today | week | month | all

  // Integrated Form Fields State Layout
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    role: 'project_manager',
    manager_name: ''
  });

  const adminEmail = localStorage.getItem('userEmail') || 'utsavm@aarviencon.com';

  const fetchAdminData = async () => {
    try {
      setLoading(true);

      // Task 1: Fetch Accounts Data
      try {
        const usersRes = await axios.get(`${API_BASE_URL}/api/users`, { 
          params: { admin_email: adminEmail } 
        });
        setUsers(usersRes.data || []);
      } catch (userErr) {
        console.error("User Directory Data Fetch Blocked:", userErr);
      }

      // Task 2: Fetch Raw Timeline Analytics
      try {
        const usageRes = await axios.get(`${API_BASE_URL}/api/usage-analytics`, { 
          params: { admin_email: adminEmail } 
        });
        setLogs(usageRes.data?.logs || []);
      } catch (usageErr) {
        console.warn("Analytics Engine Offline or Route Missing.");
      }

    } catch (err) {
      console.error("Administrative Synchronizer Exception Error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAdminData();
  }, []);

  const openAddModal = () => {
    setModalMode('add');
    setFormData({ email: '', password: '', role: 'project_manager', manager_name: '' });
    setIsModalOpen(true);
  };

  const openEditModal = (user) => {
    setModalMode('edit');
    setFormData({
      email: user.email,
      password: '', 
      role: user.role || 'project_manager',
      manager_name: user.manager_name || ''
    });
    setIsModalOpen(true);
  };

  const handleInputChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSaveUser = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (modalMode === 'add') {
        await axios.post(`${API_BASE_URL}/api/users?admin_email=${encodeURIComponent(adminEmail)}`, {
          email: formData.email.trim().toLowerCase(),
          password: formData.password,
          role: formData.role
        });
        alert("Corporate credentials initialized successfully.");
      } else {
        if (formData.password.trim().length > 0) {
          await axios.patch(`${API_BASE_URL}/api/users/reset-password?admin_email=${encodeURIComponent(adminEmail)}`, {
            email: formData.email,
            newPassword: formData.password
          });
          alert("User record update pushed to cloud.");
        } else {
          alert("No changes applied. Type a password value to override credentials record.");
        }
      }
      setIsModalOpen(false);
      await fetchAdminData();
    } catch (err) {
      alert(err.response?.data?.detail || "Profile adjustment pipeline rejected.");
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteUser = async (targetEmail) => {
    if (window.confirm(`CRITICAL WARNING: Wipe access permission profiles for ${targetEmail}?`)) {
      try {
        setLoading(true);
        await axios.delete(`${API_BASE_URL}/api/users/${encodeURIComponent(targetEmail)}?admin_email=${encodeURIComponent(adminEmail)}`);
        await fetchAdminData();
      } catch (err) {
        alert(err.response?.data?.detail || "Deletion block intercepted.");
      } finally {
        setLoading(false);
      }
    }
  };

  // 🧠 DATA COMPUTE ENGINE: User Grid Filter
  const filteredUsers = useMemo(() => {
    return users.filter(u => 
      u.email?.toLowerCase().includes(searchTerm.toLowerCase()) || 
      u.manager_name?.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [users, searchTerm]);

  // 🧠 DATA COMPUTE ENGINE: Dynamic Analytics Timeline Filter
  const filteredLogs = useMemo(() => {
    const now = new Date();
    let startDate = new Date(0); // Default to all time

    if (timeFilter === 'today') {
      startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    } else if (timeFilter === 'week') {
      startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    } else if (timeFilter === 'month') {
      startDate = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
    }

    return logs.filter(log => {
      const logDate = new Date(log.usage_date);
      const matchesTime = logDate >= startDate;
      // Search syncs seamlessly with both User Email AND Tender Numbers
      const matchesSearch = 
        log.user_email?.toLowerCase().includes(searchTerm.toLowerCase()) || 
        log.tender_no?.toLowerCase().includes(searchTerm.toLowerCase());
      
      return matchesTime && matchesSearch;
    });
  }, [logs, timeFilter, searchTerm]);

  // 🧠 DATA COMPUTE ENGINE: Aggregation & Leaderboard Math
  const analyticsStats = useMemo(() => {
    let totalCost = 0;
    let scansCount = 0;
    let chatsCount = 0;
    const userTotals = {};

    filteredLogs.forEach(log => {
      const cost = parseFloat(log.cost_inr) || 0;
      totalCost += cost;

      if (log.action_type?.toLowerCase().includes('scan')) scansCount++;
      if (log.action_type?.toLowerCase().includes('chat')) chatsCount++;

      const email = log.user_email || 'Unknown';
      userTotals[email] = (userTotals[email] || 0) + cost;
    });

    const leaderboard = Object.entries(userTotals)
      .map(([email, cost]) => ({ email, cost }))
      .sort((a, b) => b.cost - a.cost);

    return { totalCost, scansCount, chatsCount, leaderboard };
  }, [filteredLogs]);

  // UI Helpers
  const formatDate = (dateString) => {
    if (!dateString) return "Unknown Time";
    const d = new Date(dateString);
    return `${d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })}, ${d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}`;
  };

  return (
    <div className="p-6 md:p-10 h-full bg-slate-50 overflow-y-auto font-sans">
      
      {/* 🚀 UPPER CONTROL DECK */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 mb-8">
        <div>
          <h1 className="text-2xl md:text-3xl font-black text-slate-900 tracking-tight flex items-center gap-3">
            <Shield className="text-indigo-600 shrink-0" size={36} />
            System Control Node
          </h1>
          <p className="text-slate-500 mt-2 text-sm md:text-base font-medium">Provision corporate access authorizations and workspace clearances.</p>
        </div>
        
        <button 
          onClick={fetchAdminData} 
          disabled={loading}
          className="flex items-center gap-2 px-5 py-2.5 bg-white border border-slate-200 text-slate-700 rounded-xl shadow-sm hover:bg-slate-100 hover:text-indigo-600 active:scale-95 transition-all font-bold text-sm disabled:opacity-50"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> 
          {loading ? 'Syncing...' : 'Sync Node Grid'}
        </button>
      </div>

      {/* 👤 MAIN USER DATAGRID */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xl shadow-slate-100/50 overflow-hidden animate-in fade-in duration-300 mb-12">
        <div className="p-5 border-b border-slate-100 bg-slate-50/50 flex flex-col sm:flex-row justify-between items-stretch sm:items-center gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
            <input 
              className="w-full pl-11 pr-4 py-2.5 bg-white rounded-xl border border-slate-200 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all text-sm font-medium" 
              placeholder="Search users or tender numbers..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          
          <button 
            onClick={openAddModal} 
            className="bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white px-6 py-2.5 rounded-xl font-bold flex items-center justify-center gap-2 text-sm shadow-lg shadow-indigo-600/20 transition-all"
          >
            <Plus size={18}/> Create Profile
          </button>
        </div>

        {/* 🎯 FIX APPLIED HERE: Added max-h-[320px] and overflow-y-auto */}
        <div className="overflow-x-auto overflow-y-auto max-h-[320px]">
          <table className="w-full text-left border-collapse">
            <thead className="sticky top-0 z-10">
              <tr className="bg-slate-900 text-slate-300 text-[11px] font-black uppercase tracking-widest">
                <th className="p-5 pl-8">Security Access Handle</th>
                <th className="p-5">Clearance Context Scope</th>
                <th className="p-5 text-right pr-8">Administrative Operations</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && users.length === 0 ? (
                <tr>
                  <td colSpan="3" className="p-16 text-center text-slate-400 font-medium text-sm animate-pulse">Querying network security ledger...</td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan="3" className="p-16 text-center text-slate-400 italic text-sm">No authorized records matched the filtration context.</td>
                </tr>
              ) : (
                filteredUsers.map((u) => (
                  <tr key={u.email} className="text-sm hover:bg-slate-50/80 transition-colors group bg-white">
                    <td className="p-5 pl-8">
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600 border border-indigo-100 group-hover:scale-105 transition-transform">
                          <Users size={18} />
                        </div>
                        <div>
                          <div className="font-extrabold text-slate-900 text-sm">{u.manager_name || "Enterprise User"}</div>
                          <div className="text-xs font-mono text-slate-500 mt-0.5 flex items-center gap-1">
                            <Mail size={12} className="text-slate-400" />
                            {u.email}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="p-5 align-middle">
                      <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wide border ${
                        u.role === 'admin' ? 'bg-purple-50 text-purple-700 border-purple-200' : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      }`}>
                        <ShieldCheck size={14} /> {(u.role || 'project_manager').replace('_', ' ')}
                      </span>
                    </td>
                    <td className="p-5 text-right pr-8 align-middle">
                      <div className="inline-flex items-center justify-end gap-2">
                        <button onClick={() => openEditModal(u)} className="p-2.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 active:scale-90 rounded-xl transition-all" title="Modify Account">
                          <Edit3 size={18} />
                        </button>
                        <button onClick={() => handleDeleteUser(u.email)} className="p-2.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 active:scale-90 rounded-xl transition-all" title="Revoke Permissions">
                          <Trash2 size={18} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <hr className="border-slate-200/60 mb-10" />

      {/* 📊 NEW LAYER 1: HIGH OCTANE ANALYTICS HEADER & STAT CARDS */}
      <div className="mb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <h2 className="text-xl font-black text-slate-900 flex items-center gap-2">
          <Activity className="text-indigo-600" size={24} /> Infrastructure Utilization
        </h2>
        
        {/* Dynamic Timeline Filter Strip */}
        <div className="flex bg-white border border-slate-200 rounded-xl p-1 shadow-sm">
          {['today', 'week', 'month', 'all'].map((filter) => (
            <button
              key={filter}
              onClick={() => setTimeFilter(filter)}
              className={`px-4 py-1.5 text-xs font-bold uppercase tracking-wider rounded-lg transition-all ${
                timeFilter === filter 
                  ? 'bg-slate-900 text-white shadow-md' 
                  : 'text-slate-500 hover:text-slate-800 hover:bg-slate-100'
              }`}
            >
              {filter === 'all' ? 'All Time' : filter}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {/* Stat Card: Total Cost */}
        <div className="bg-white p-6 rounded-2xl border-l-4 border-l-emerald-500 border border-slate-200 shadow-xl shadow-slate-100/50">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs uppercase tracking-widest font-bold text-slate-400 mb-1">Total AI Investment</p>
              <h3 className="text-3xl font-black text-slate-900">₹{analyticsStats.totalCost.toFixed(2)}</h3>
            </div>
            <div className="p-3 bg-emerald-50 rounded-xl text-emerald-600"><IndianRupee size={22} /></div>
          </div>
        </div>

        {/* Stat Card: Scan Volume */}
        <div className="bg-white p-6 rounded-2xl border-l-4 border-l-indigo-500 border border-slate-200 shadow-xl shadow-slate-100/50">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs uppercase tracking-widest font-bold text-slate-400 mb-1">Tender Scans</p>
              <h3 className="text-3xl font-black text-slate-900">{analyticsStats.scansCount}</h3>
            </div>
            <div className="p-3 bg-indigo-50 rounded-xl text-indigo-600"><FileText size={22} /></div>
          </div>
        </div>

        {/* Stat Card: Chat Volume */}
        <div className="bg-white p-6 rounded-2xl border-l-4 border-l-slate-800 border border-slate-200 shadow-xl shadow-slate-100/50">
          <div className="flex justify-between items-start">
            <div>
              <p className="text-xs uppercase tracking-widest font-bold text-slate-400 mb-1">Workspace Queries</p>
              <h3 className="text-3xl font-black text-slate-900">{analyticsStats.chatsCount}</h3>
            </div>
            <div className="p-3 bg-slate-100 rounded-xl text-slate-800"><MessageSquare size={22} /></div>
          </div>
        </div>
      </div>

      {/* 🧾 NEW LAYER 2: 70/30 SPLIT OPERATIONS PANEL */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Column (70%): The Raw Ledger */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 shadow-xl shadow-slate-100/50 overflow-hidden flex flex-col">
          <div className="p-5 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
            <div>
              <h3 className="font-black text-slate-900 tracking-tight flex items-center gap-2 text-lg">
                <Clock size={18} className="text-indigo-600" /> Operational Ledger
              </h3>
              <p className="text-xs text-slate-500 mt-1">Real-time transactional audit trail ({filteredLogs.length} events)</p>
            </div>
          </div>
          
          <div className="overflow-x-auto overflow-y-auto max-h-[450px]">
            <table className="w-full text-left border-collapse">
              <thead className="sticky top-0 bg-slate-900 z-10">
                <tr className="text-slate-300 text-[10px] font-black uppercase tracking-widest">
                  <th className="p-4 pl-6">Timestamp</th>
                  <th className="p-4">Employee Identity</th>
                  <th className="p-4">Context Badge</th>
                  <th className="p-4 text-right pr-6">Cost Impact</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {filteredLogs.length === 0 ? (
                  <tr>
                    <td colSpan="4" className="p-12 text-center text-slate-400 italic">No usage operations recorded in this timeframe.</td>
                  </tr>
                ) : (
                  filteredLogs.map((log, index) => (
                    <tr key={index} className="hover:bg-slate-50/50 transition-colors bg-white">
                      <td className="p-4 pl-6 text-xs text-slate-500 font-medium whitespace-nowrap">
                        {formatDate(log.usage_date)}
                      </td>
                      <td className="p-4 font-semibold text-slate-900">
                        {log.user_email}
                      </td>
                      <td className="p-4">
                        <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-[10px] font-black uppercase tracking-wider border ${
                          log.action_type?.includes('Scan') 
                            ? 'bg-indigo-50 border-indigo-100 text-indigo-700' 
                            : 'bg-slate-100 border-slate-200 text-slate-700'
                        }`}>
                          {log.action_type}
                        </span>
                        {log.tender_no && log.tender_no !== 'N/A' && (
                          <div className="text-[10px] text-slate-400 font-mono mt-1 border border-slate-100 bg-slate-50 px-1.5 py-0.5 rounded inline-block">
                            {log.tender_no}
                          </div>
                        )}
                      </td>
                      <td className="p-4 text-right pr-6 font-extrabold text-emerald-600">
                        ₹{parseFloat(log.cost_inr || 0).toFixed(4)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column (30%): Employee Summary Leaderboard */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-xl shadow-slate-100/50 overflow-hidden flex flex-col max-h-[530px]">
          <div className="p-5 border-b border-slate-100 bg-slate-50/50">
            <h3 className="font-black text-slate-900 tracking-tight flex items-center gap-2 text-lg">
              <BarChart3 size={18} className="text-indigo-600" /> User Aggregation
            </h3>
            <p className="text-xs text-slate-500 mt-1">Resource expenditure by employee</p>
          </div>
          
          <div className="p-4 overflow-y-auto flex-1 divide-y divide-slate-50">
            {analyticsStats.leaderboard.length === 0 ? (
              <div className="text-center text-slate-400 italic p-6 text-sm">No footprint data found.</div>
            ) : (
              analyticsStats.leaderboard.map((user, index) => (
                <div key={user.email} className="py-3 flex justify-between items-center hover:bg-slate-50 px-2 rounded-lg transition-colors cursor-pointer">
                  <div className="flex items-center gap-3">
                    <div className="w-6 h-6 rounded-full bg-slate-100 flex items-center justify-center text-[10px] font-black text-slate-500 border border-slate-200">
                      {index + 1}
                    </div>
                    <div className="text-sm font-bold text-slate-800 truncate max-w-[140px]" title={user.email}>
                      {user.email.split('@')[0]}
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-sm font-black text-slate-900">₹{user.cost.toFixed(2)}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

      </div>

      {/* 👑 CREDENTIALS FORM POPUP MODAL OVERLAY PANEL */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white p-8 rounded-3xl w-full max-w-md shadow-2xl border border-slate-100 flex flex-col animate-in zoom-in-95 duration-200">
            <div className="flex justify-between items-center mb-8">
              <h2 className="text-xl font-black text-slate-900 tracking-tight">
                {modalMode === 'add' ? 'Initialize Corporate Profile' : 'Modify Access Matrix'}
              </h2>
              <button onClick={() => setIsModalOpen(false)} className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-full transition-all">
                <X size={20}/>
              </button>
            </div>

            <form onSubmit={handleSaveUser} className="space-y-5">
              <div>
                <label className="block text-[11px] uppercase font-black tracking-widest text-slate-500 mb-2">System Handle Email</label>
                <input 
                  type="email" name="email" required placeholder="username@aarviencon.com"
                  value={formData.email} onChange={handleInputChange} disabled={modalMode === 'edit'}
                  className="w-full p-3.5 border border-slate-200 rounded-xl outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-600 bg-white text-sm font-medium transition-all disabled:bg-slate-50 disabled:text-slate-400 disabled:cursor-not-allowed"
                />
              </div>

              <div>
                <label className="block text-[11px] uppercase font-black tracking-widest text-slate-500 mb-2">
                  {modalMode === 'add' ? 'Security Access Code (Password) *' : 'Override Crypt Token (Optional)'}
                </label>
                <input 
                  type="text" name="password" required={modalMode === 'add'} minLength={6} placeholder={modalMode === 'add' ? "Min 6 alphanumeric characters" : "Leave blank to maintain asset key"}
                  value={formData.password} onChange={handleInputChange}
                  className="w-full p-3.5 border border-slate-200 rounded-xl outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-600 bg-white text-sm font-medium transition-all font-mono"
                />
              </div>

              <div>
                <label className="block text-[11px] uppercase font-black tracking-widest text-slate-500 mb-2">Clearance Authorization Scope</label>
                <select 
                  name="role" value={formData.role} onChange={handleInputChange}
                  className="w-full p-3.5 border border-slate-200 rounded-xl outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-600 bg-white text-sm font-bold text-slate-700 cursor-pointer transition-all appearance-none"
                >
                  <option value="project_manager">Project Manager (Standard Clearance)</option>
                  <option value="admin">System Administrator (Full Infrastructure Access)</option>
                </select>
              </div>

              <div className="pt-6 mt-4 border-t border-slate-100 flex justify-end gap-3">
                <button type="button" onClick={() => setIsModalOpen(false)} className="px-5 py-2.5 font-bold text-slate-500 hover:bg-slate-100 hover:text-slate-700 rounded-xl text-sm transition-all">
                  Cancel
                </button>
                <button type="submit" disabled={loading} className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white font-bold rounded-xl text-sm shadow-lg shadow-indigo-600/20 transition-all flex items-center gap-2 disabled:opacity-70">
                  <Save size={18}/> {modalMode === 'add' ? 'Push Configuration' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
};

export default AdminControlWorkspace;