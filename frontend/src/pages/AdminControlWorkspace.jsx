import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { 
  Shield, Users, Trash2, Plus, RefreshCw, 
  Search, X, Save, Edit3, Mail, ShieldCheck 
} from 'lucide-react';

// 🎯 FIX: Automatically strips trailing slashes to prevent 404 network errors
const API_BASE_URL = (import.meta.env.VITE_API_URL || "https://attract-appeals-recorded-able.trycloudflare.com").replace(/\/$/, "");

const AdminControlWorkspace = () => {
  const [users, setUsers] = useState([]);
  const [analytics, setAnalytics] = useState({ daily: [], monthly: [] }); // Logic kept intact
  const [loading, setLoading] = useState(true);
  
  // UI Modal Controls
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState('add'); // 'add' or 'edit'
  const [searchTerm, setSearchTerm] = useState('');

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
      const [usersRes, usageRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/api/admin/users`, { params: { admin_email: adminEmail } }),
        axios.get(`${API_BASE_URL}/api/admin/usage-analytics`, { params: { admin_email: adminEmail } })
      ]);
      setUsers(usersRes.data || []);
      setAnalytics(usageRes.data || { daily: [], monthly: [] });
    } catch (err) {
      console.error("Administrative Synchronizer Error:", err);
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
      password: '', // Kept empty for security overrides
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
        await axios.post(`${API_BASE_URL}/api/admin/users?admin_email=${encodeURIComponent(adminEmail)}`, {
          email: formData.email.trim().toLowerCase(),
          password: formData.password,
          role: formData.role
        });
        alert("Corporate credentials initialized successfully.");
      } else {
        if (formData.password.trim().length > 0) {
          await axios.patch(`${API_BASE_URL}/api/admin/users/reset-password?admin_email=${encodeURIComponent(adminEmail)}`, {
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
        await axios.delete(`${API_BASE_URL}/api/admin/users/${encodeURIComponent(targetEmail)}?admin_email=${encodeURIComponent(adminEmail)}`);
        await fetchAdminData();
      } catch (err) {
        alert(err.response?.data?.detail || "Deletion block intercepted.");
      } finally {
        setLoading(false);
      }
    }
  };

  // Inline Search Match Sorting Logic
  const filteredUsers = useMemo(() => {
    return users.filter(u => 
      u.email?.toLowerCase().includes(searchTerm.toLowerCase()) || 
      u.manager_name?.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [users, searchTerm]);

  return (
    <div className="p-6 md:p-10 h-full bg-slate-50 overflow-y-auto font-sans">
      
      {/* Upper Navigation Control Deck */}
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

      {/* Main Datagrid Container Card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xl shadow-slate-100/50 overflow-hidden animate-in fade-in duration-300">
        
        {/* Table Operations Action Bar */}
        <div className="p-5 border-b border-slate-100 bg-slate-50/50 flex flex-col sm:flex-row justify-between items-stretch sm:items-center gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
            <input 
              className="w-full pl-11 pr-4 py-2.5 bg-white rounded-xl border border-slate-200 outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all text-sm font-medium" 
              placeholder="Filter by account email routing..."
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

        {/* Dynamic User Grid Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-900 text-slate-300 text-[11px] font-black uppercase tracking-widest">
                <th className="p-5 pl-8">Security Access Handle</th>
                <th className="p-5">Clearance Context Scope</th>
                <th className="p-5 text-right pr-8">Administrative Operations</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading && users.length === 0 ? (
                <tr>
                  <td colSpan="3" className="p-16 text-center text-slate-400 font-medium text-sm animate-pulse flex-col items-center justify-center">
                    Querying network security ledger...
                  </td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan="3" className="p-16 text-center text-slate-400 italic text-sm">
                    No authorized records matched the filtration context.
                  </td>
                </tr>
              ) : (
                filteredUsers.map((u) => (
                  <tr key={u.email} className="text-sm hover:bg-slate-50/80 transition-colors group">
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
                        u.role === 'admin' 
                          ? 'bg-purple-50 text-purple-700 border-purple-200' 
                          : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      }`}>
                        <ShieldCheck size={14} />
                        {(u.role || 'project_manager').replace('_', ' ')}
                      </span>
                    </td>
                    <td className="p-5 text-right pr-8 align-middle">
                      <div className="inline-flex items-center justify-end gap-2">
                        <button 
                          onClick={() => openEditModal(u)} 
                          className="p-2.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 active:scale-90 rounded-xl transition-all"
                          title="Modify Account Configuration"
                        >
                          <Edit3 size={18} />
                        </button>
                        <button 
                          onClick={() => handleDeleteUser(u.email)} 
                          className="p-2.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 active:scale-90 rounded-xl transition-all"
                          title="Revoke Node Permissions"
                        >
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

      {/* 👑 CREDENTIALS FORM POPUP MODAL OVERLAY PANEL */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white p-8 rounded-3xl w-full max-w-md shadow-2xl border border-slate-100 flex flex-col animate-in zoom-in-95 duration-200">
            <div className="flex justify-between items-center mb-8">
              <h2 className="text-xl font-black text-slate-900 tracking-tight">
                {modalMode === 'add' ? 'Initialize Corporate Profile' : 'Modify Access Matrix'}
              </h2>
              <button 
                onClick={() => setIsModalOpen(false)} 
                className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-full transition-all"
              >
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
                <button 
                  type="button" 
                  onClick={() => setIsModalOpen(false)} 
                  className="px-5 py-2.5 font-bold text-slate-500 hover:bg-slate-100 hover:text-slate-700 rounded-xl text-sm transition-all"
                >
                  Cancel
                </button>
                <button 
                  type="submit" 
                  disabled={loading}
                  className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 active:scale-95 text-white font-bold rounded-xl text-sm shadow-lg shadow-indigo-600/20 transition-all flex items-center gap-2 disabled:opacity-70"
                >
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