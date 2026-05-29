import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { 
  Shield, Users, Activity, Trash2, Key, Plus, 
  RefreshCw, Search, X, Save, Edit3, UserCheck 
} from 'lucide-react';

 const API_BASE_URL = import.meta.env.VITE_API_URL || "https://attract-appeals-recorded-able.trycloudflare.com";

const AdminControlWorkspace = () => {
  const [activeView, setActiveView] = useState('users'); // 'users' or 'billing'
  const [users, setUsers] = useState([]);
  const [analytics, setAnalytics] = useState({ daily: [], monthly: [] });
  const [loading, setLoading] = useState(true);
  
  // UI Modal Controls
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState('add'); // 'add' or 'edit'
  const [searchTerm, setSearchTerm] = useState('');

  // Integrated Form Fields State Layout (Matches MasterDashboard pattern)
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    role: 'project_manager',
    manager_name: ''
  });

  const adminEmail = localStorage.getItem('userEmail') || 'utsavm@aarviencon.com';

  const fetchAdminData = async () => {
    try {
      const [usersRes, usageRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/api/admin/users`, { params: { admin_email: adminEmail } }),
        axios.get(`${API_BASE_URL}/api/admin/usage-analytics`, { params: { admin_email: adminEmail } })
      ]);
      setUsers(usersRes.data || []);
      setAnalytics(usageRes.data || { daily: [], monthly: [] });
    } catch (err) {
      console.error("Administrative Synchronizer Error:", err);
    }
  };

  useEffect(() => {
    fetchAdminData().finally(() => setLoading(false));
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
        // Create profile using standard NewUser model shape
        await axios.post(`${API_BASE_URL}/api/admin/users?admin_email=${encodeURIComponent(adminEmail)}`, {
          email: formData.email.trim().toLowerCase(),
          password: formData.password,
          role: formData.role
        });
        alert("Corporate credentials initialized successfully.");
      } else {
        // 🎉 FIXED: Changed from '#' to '//' so Vite can parse it cleanly
        // Optional password change trigger if characters are submitted
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

  if (loading && users.length === 0) {
    return <div className="p-20 text-center font-bold text-slate-400">Syncing Administration Tables...</div>;
  }

  return (
    <div className="relative p-4 sm:p-6 md:p-8 h-full bg-slate-50 overflow-y-auto">
      
      {/* Upper Navigation Control Deck */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-black text-slate-900 flex items-center gap-3">
            <Shield className="text-amber-500 shrink-0" size={32} />
            System Administration Workspace
          </h1>
          <p className="text-slate-500 mt-1">Manage infrastructure clearances and track live API log registries.</p>
        </div>
        <button onClick={fetchAdminData} className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 text-slate-600 rounded-xl shadow-sm hover:bg-slate-50 transition-colors font-bold text-sm">
          <RefreshCw size={16} /> Sync Table State
        </button>
      </div>

      {/* Primary Switch Selection Tabs */}
      <div className="flex border-b border-slate-200 mb-6 gap-2">
        <button 
          onClick={() => setActiveView('users')} 
          className={`px-5 py-3 text-xs font-bold uppercase tracking-wider border-b-2 transition-all flex items-center gap-2 ${activeView === 'users' ? 'border-b-indigo-600 text-indigo-600' : 'border-b-transparent text-slate-400 hover:text-slate-600'}`}
        >
          <Users size={16}/> Existing Users Table
        </button>
        <button 
          onClick={() => setActiveView('billing')} 
          className={`px-5 py-3 text-xs font-bold uppercase tracking-wider border-b-2 transition-all flex items-center gap-2 ${activeView === 'billing' ? 'border-b-amber-500 text-amber-500' : 'border-b-transparent text-slate-400 hover:text-slate-600'}`}
        >
          <Activity size={16}/> Real-Time API Logs
        </button>
      </div>

      {/* 👤 VIEW: LIVE USERS DATAGRID CONFIGURATION */}
      {activeView === 'users' && (
        <>
          <div className="flex flex-col sm:flex-row justify-between items-stretch sm:items-center gap-4 mb-6">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
              <input 
                className="w-full pl-10 pr-4 py-2 rounded-xl border outline-none focus:ring-2 focus:ring-indigo-500 text-sm" 
                placeholder="Find account email or node identifier..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <button onClick={openAddModal} className="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-xl font-bold flex items-center justify-center gap-2 text-sm shadow-md transition-colors">
              <Plus size={16}/> Create Account Profile
            </button>
          </div>

          <div className="bg-white rounded-2xl border shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead className="bg-slate-900 text-white text-xs uppercase tracking-wider">
                  <tr>
                    <th className="p-4">Manager Assignment Node</th>
                    <th className="p-4">Clearance Role</th>
                    <th className="p-4 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.length === 0 ? (
                    <tr><td colSpan="3" className="p-8 text-center text-slate-400 italic">No user entries located.</td></tr>
                  ) : (
                    filteredUsers.map((u) => (
                      <tr key={u.email} className="border-b text-sm hover:bg-slate-50/80 transition-colors">
                        <td className="p-4">
                          <div className="font-bold text-slate-800">{u.manager_name || "Unassigned Profile"}</div>
                          <div className="text-xs font-mono text-slate-400">{u.email}</div>
                        </td>
                        <td className="p-4">
                          <span className={`px-2.5 py-1 rounded text-xs font-black tracking-wide ${u.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-slate-100 text-slate-600'}`}>
                            {(u.role || 'project_manager').toUpperCase()}
                          </span>
                        </td>
                        <td className="p-4 text-center flex justify-center gap-1">
                          <button onClick={() => openEditModal(u)} className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors">
                            <Edit3 size={16} />
                          </button>
                          <button onClick={() => handleDeleteUser(u.email)} className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors">
                            <Trash2 size={16} />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* 📊 VIEW: METRIC LEDGERS DATA STREAM */}
      {activeView === 'billing' && (
        <div className="space-y-8 animate-in fade-in duration-200">
          <div className="bg-white rounded-2xl border p-6 shadow-sm">
            <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2"><UserCheck className="text-emerald-500"/> Consolidated Monthly Accounting summaries</h2>
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-500 font-bold border-b">
                <tr><th className="p-3 text-left">Cycle</th><th className="p-3 text-left">Account Handle</th><th className="p-3 text-right">Computed Cost</th></tr>
              </thead>
              <tbody>
                {analytics.monthly.map((m, idx) => (
                  <tr key={idx} className="border-b last:border-0 hover:bg-slate-50/50"><td className="p-3 font-medium">{m.month_str}</td><td className="p-3">{m.user_email}</td><td className="p-3 text-right font-bold text-indigo-600">₹{parseFloat(m.monthly_cost_inr).toFixed(2)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="bg-white rounded-2xl border p-6 shadow-sm">
            <h2 className="text-lg font-bold text-slate-800 mb-4">Continuous Transaction Logging Feed</h2>
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-500 font-bold border-b">
                <tr><th className="p-3 text-left">Date</th><th className="p-3 text-left">User</th><th className="p-3 text-left">Trigger Action</th><th className="p-3 text-right">Cost (INR)</th></tr>
              </thead>
              <tbody>
                {analytics.daily.map((d, idx) => (
                  <tr key={idx} className="border-b last:border-0 hover:bg-slate-50/50"><td className="p-3 text-slate-400 text-xs">{d.date_str}</td><td className="p-3 font-semibold text-slate-700">{d.user_email}</td><td className="p-3"><span className="bg-indigo-50 border border-indigo-100 text-indigo-700 px-2 py-0.5 rounded text-xs font-bold">{d.action_type}</span></td><td className="p-3 text-right font-mono text-emerald-600 font-bold">₹{parseFloat(d.total_cost_inr).toFixed(4)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 👑 CREDENTIALS FORM POPUP MODAL OVERLAY PANEL */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white p-6 sm:p-8 rounded-[1.5rem] w-full max-w-md shadow-2xl relative flex flex-col animate-in zoom-in-95 duration-150">
            <button onClick={() => setIsModalOpen(false)} className="absolute top-4 right-4 text-slate-400 hover:text-slate-700 transition-colors"><X size={20}/></button>
            
            <h2 className="text-xl font-black text-slate-800 mb-6">
              {modalMode === 'add' ? 'Provision System Access Profile' : 'Modify Access Configurations'}
            </h2>

            <form onSubmit={handleSaveUser} className="space-y-5">
              <div>
                <label className="block text-[10px] uppercase font-black tracking-wider text-slate-400 mb-1.5">Corporate Email Address</label>
                <input 
                  type="email" name="email" required placeholder="username@aarviencon.com"
                  value={formData.email} onChange={handleInputChange} disabled={modalMode === 'edit'}
                  className="w-full p-3 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 bg-white text-sm disabled:bg-slate-50 disabled:text-slate-400 disabled:cursor-not-allowed"
                />
              </div>

              <div>
                <label className="block text-[10px] uppercase font-black tracking-wider text-slate-400 mb-1.5">
                  {modalMode === 'add' ? 'Access Token Key (Password) *' : 'Override Password Crypt Key (Optional)'}
                </label>
                <input 
                  type="text" name="password" required={modalMode === 'add'} minLength={6} placeholder={modalMode === 'add' ? "Min 6 characters" : "Leave blank to maintain key"}
                  value={formData.password} onChange={handleInputChange}
                  className="w-full p-3 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 bg-white text-sm"
                />
              </div>

              <div>
                <label className="block text-[10px] uppercase font-black tracking-wider text-slate-400 mb-1.5">Clearance Permission Scope</label>
                <select 
                  name="role" value={formData.role} onChange={handleInputChange}
                  className="w-full p-3 border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 bg-white text-sm font-semibold text-slate-700 cursor-pointer"
                >
                  <option value="project_manager">Project Manager (Standard access)</option>
                  <option value="admin">System Admin (Full rights)</option>
                </select>
              </div>

              <div className="pt-4 border-t border-slate-100 flex justify-end gap-3">
                <button type="button" onClick={() => setIsModalOpen(false)} className="px-4 py-2.5 font-bold text-slate-400 hover:bg-slate-50 rounded-xl text-sm transition-colors">Cancel</button>
                <button type="submit" className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl text-sm shadow-md transition-colors flex items-center gap-2">
                  <Save size={16}/> Save Profile
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