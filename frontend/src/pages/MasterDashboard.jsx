import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { 
  Target, Clock, CheckCircle, XCircle, FileText, 
  Search, Plus, Edit3, X, Trash2
} from 'lucide-react';

const MasterDashboard = () => {
  const [tenders, setTenders] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedFY, setSelectedFY] = useState('All'); // NEW: Financial Year State
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState('add');
  
  const [formData, setFormData] = useState({
    tender_no: '', name_of_client: '', tender_status: 'Pending', 
    received_date: '', due_date: '', location: '', 
    tender_open_price: '', quoted_value: '', description: '', 
    project_manager: '', emd: '', emd_status: 'Pending', 
    tender_fee_status: 'Pending', price_status: 'Pending', source: '', 
    comments: '', docs_prepared_by: '', financial_year: '2023-2024', pre_bidding_date: '',
  });

  // UPDATED: Now safely falls back to your Live Cloud URL
  const API_BASE_URL = import.meta.env.VITE_API_URL || "https://aarvi-tender-api.onrender.com";

 // ✅ CRITICAL UPDATE: Bypasses the Silo if the user is an Admin
  const fetchTenders = async () => {
    try {
      const managerName = localStorage.getItem('managerName');
      const userRole = localStorage.getItem('userRole'); // Grab the role!
      
      const queryParams = {};
      
      // ONLY apply the manager filter if the user is a project_manager
      if (userRole !== 'admin' && managerName && managerName !== 'undefined' && managerName !== 'null') {
        queryParams.manager = managerName;
      }

      const res = await axios.get(`${API_BASE_URL}/tenders`, {
        params: queryParams
      });
      
      setTenders(res.data);
    } catch (err) { console.error("Fetch Error:", err); }
  };

  useEffect(() => { 
    fetchTenders().finally(() => setLoading(false));
  }, []);

  const handleStatusChange = async (tender_no, newStatus) => {
    try {
      await axios.patch(`${API_BASE_URL}/tenders/${encodeURIComponent(tender_no)}/status`, { tender_status: newStatus });
      fetchTenders(); 
    } catch (err) { alert("Error Updating: " + (err.response?.data?.error || err.message)); }
  };

  const openAddModal = () => {
    setModalMode('add');
    setFormData({ 
      tender_no: '', name_of_client: '', tender_status: 'Pending', 
      received_date: '', due_date: '', location: '', 
      tender_open_price: '', quoted_value: '', description: '', 
      project_manager: '', emd: '', emd_status: 'Pending', 
      tender_fee_status: 'Pending', price_status: 'Pending', source: '', 
      comments: '', docs_prepared_by: '', financial_year: '2023-2024',
      pre_bidding_date: ''
    });
    setIsModalOpen(true);
  };

  const openEditModal = (tender) => {
    setModalMode('edit');
    setFormData({
      ...tender,
      received_date: tender.received_date ? tender.received_date.split(' ')[0] : '',
      due_date: tender.due_date ? tender.due_date.split(' ')[0] : '', 
      pre_bidding_date: tender.pre_bidding_date ? tender.pre_bidding_date.split(' ')[0] : '',
    });
    setIsModalOpen(true);
  };

  const handleSaveTender = async (e) => {
    e.preventDefault();
    
    const cleanedData = {
      ...formData,
      tender_open_price: formData.tender_open_price === '' ? null : parseFloat(formData.tender_open_price),
      quoted_value: formData.quoted_value === '' ? null : parseFloat(formData.quoted_value),
      pre_bidding_date: formData.pre_bidding_date === '' ? null : formData.pre_bidding_date
    };

    try {
      setLoading(true);
      if (modalMode === 'add') {
        await axios.post(`${API_BASE_URL}/tenders`, cleanedData);
      } else {
        await axios.put(`${API_BASE_URL}/tenders/${encodeURIComponent(formData.tender_no)}`, cleanedData);
      }
      setIsModalOpen(false);
      fetchTenders().finally(() => setLoading(false));
    } catch (err) {
      setLoading(false);
      console.error("Save Error Details:", err.response?.data);
      alert("Failed to save: " + (err.response?.data?.detail ? JSON.stringify(err.response.data.detail) : err.message));
    }
  };

  const handleDeleteTender = async (tenderNo) => {
    if (window.confirm(`Are you sure you want to permanently delete Tender: ${tenderNo}?`)) {
      try {
        setLoading(true);
        await axios.delete(`${API_BASE_URL}/tenders/${encodeURIComponent(tenderNo)}`);
        setIsModalOpen(false); 
        await fetchTenders(); 
      } catch (err) {
        alert("Delete failed: " + err.message);
      } finally {
        setLoading(false);
      }
    }
  };

  // UPDATED: Dynamic Export based on selected FY
  const handleDownload = () => {
    const url = selectedFY === 'All' 
      ? `${API_BASE_URL}/export-tenders` 
      : `${API_BASE_URL}/export-tenders?fy=${selectedFY}`;
    window.open(url, '_blank');
  };

  const today = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  // NEW: Dynamically grab all available Financial Years from the data
  const availableFYs = useMemo(() => {
    const years = [...new Set(tenders.map(t => t.financial_year))].filter(Boolean);
    return ['All', ...years.sort().reverse()];
  }, [tenders]);

  const getRowStyle = (dateStr) => {
    if (!dateStr) return '';
    const dueDate = new Date(dateStr);
    const diffDays = Math.ceil((dueDate - today) / (1000 * 60 * 60 * 24));
    if (diffDays < 0) return 'opacity-50 bg-slate-100 grayscale-[50%]'; 
    if (diffDays >= 0 && diffDays <= 4) return 'bg-red-50 border-l-4 border-l-red-500'; 
    return ''; 
  };

  // UPDATED: Comprehensive Sorting & Filtering Logic
  const sortedTenders = useMemo(() => {
    // 1. Filter by Search term AND Financial Year
    const filtered = tenders.filter(t => {
      const matchesSearch = t.name_of_client?.toLowerCase().includes(searchTerm.toLowerCase()) || 
                            t.tender_no?.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesFY = selectedFY === 'All' || t.financial_year === selectedFY;
      return matchesSearch && matchesFY;
    });

    // 2. Sort: Active up top (ascending), Expired at bottom (descending)
    return filtered.sort((a, b) => {
      const dateA = a.due_date ? new Date(a.due_date) : new Date('9999-12-31');
      const dateB = b.due_date ? new Date(b.due_date) : new Date('9999-12-31');
      
      const isAActive = dateA >= today;
      const isBActive = dateB >= today;

      if (isAActive && !isBActive) return -1;
      if (!isAActive && isBActive) return 1;

      // Both active: closest deadline first
      if (isAActive && isBActive) return dateA - dateB;

      // Both expired: most recent first
      return dateB - dateA;
    });
  }, [tenders, searchTerm, selectedFY, today]);

  const stats = useMemo(() => ({
  // 1. Total Active (Kept as original logic: Live tenders with future deadlines)
  totalActive: tenders.filter(t => 
    t.due_date && 
    new Date(t.due_date) >= today && 
    !['Tender Won', 'Tender Lost', 'Tender Cancelled', 'Tender Regret'].includes(t.tender_status)
  ).length,

  // 2. Tender Quoted (UPDATED: Now includes Won + Lost + Quoted + Cancelled)
  quoted: tenders.filter(t => 
    ['Tender Won', 'Tender Lost', 'Tender Quoted', 'Quoted', 'Quoted Active', 'Tender Cancelled'].includes(t.tender_status)
  ).length,

  // 3. Tenders Won
  won: tenders.filter(t => t.tender_status === 'Tender Won').length,

  // 4. Tenders Lost
  lost: tenders.filter(t => t.tender_status === 'Tender Lost').length,
}), [tenders, today]);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  if (loading && tenders.length === 0) return <div className="p-20 text-center font-bold text-slate-400">Loading Database...</div>;

  return (
    <div className="relative p-8 h-full bg-slate-50 overflow-y-auto">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <StatCard title="Total Active" value={stats.totalActive} icon={<Clock className="text-blue-500"/>} />
        <StatCard title="Tender Quoted" value={stats.quoted} icon={<Target className="text-amber-500"/>} />
        <StatCard title="Tenders Won" value={stats.won} icon={<CheckCircle className="text-emerald-600"/>} />
        <StatCard title="Tenders Lost" value={stats.lost} icon={<XCircle className="text-rose-500"/>} />
      </div>

      <div className="flex justify-between items-center mb-6">
        {/* UPDATED: Added Financial Year Dropdown next to Search */}
        <div className="flex gap-4 items-center">
          <div className="relative w-96">
            <Search className="absolute left-3 top-2.5 text-slate-400" size={18} />
            <input className="w-full pl-10 py-2 rounded-xl border outline-none focus:ring-2 focus:ring-indigo-500 transition-all" placeholder="Search Client or Tender..." onChange={(e) => setSearchTerm(e.target.value)} />
          </div>
          
          <select 
            value={selectedFY} 
            onChange={(e) => setSelectedFY(e.target.value)}
            className="bg-white border border-slate-200 px-4 py-2 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 font-medium text-slate-600 cursor-pointer"
          >
            {availableFYs.map(fy => (
              <option key={fy} value={fy}>{fy === 'All' ? 'All Financial Years' : fy}</option>
            ))}
          </select>
        </div>

        <div className="flex gap-3">
          <button onClick={openAddModal} className="bg-emerald-600 hover:bg-emerald-700 transition-colors text-white px-5 py-2 rounded-lg font-bold flex items-center gap-2"><Plus size={16}/> Add Tender</button>
          <button onClick={handleDownload} className="bg-slate-800 hover:bg-slate-900 transition-colors text-white px-5 py-2 rounded-lg font-bold flex items-center gap-2"><FileText size={16} /> Export CSV</button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border overflow-hidden shadow-sm">
        <table className="w-full text-left">
          <thead className="bg-slate-900 text-white text-xs uppercase tracking-wider">
            <tr>
              <th className="p-4">Client</th>
              <th className="p-4">Tender No</th>
              <th className="p-4">Due Date</th>
              <th className="p-4">Status</th>
              <th className="p-4 text-center">Action</th>
            </tr>
          </thead>
          <tbody>
            {sortedTenders.map((t) => (
              <tr key={t.tender_no} className={`border-b text-sm transition-all hover:bg-slate-50 ${getRowStyle(t.due_date)}`}>
                <td className="p-4 font-bold text-slate-700">{t.name_of_client}</td>
                <td className="p-4 font-mono text-slate-500">{t.tender_no}</td>
                <td className="p-4 font-bold">{t.due_date ? new Date(t.due_date).toLocaleDateString() : 'N/A'}</td>
                <td className="p-4">
                  <select 
                    value={t.tender_status || 'Pending'} 
                    onChange={(e) => handleStatusChange(t.tender_no, e.target.value)} 
                    className="bg-transparent border p-1 rounded font-black text-[10px] uppercase text-indigo-600 outline-none cursor-pointer hover:bg-indigo-50"
                  >
                    <option value="Pending">Pending</option>
                    <option value="Tender Quoted">Tender Quoted</option>
                    <option value="Tender Won">Tender Won</option>
                    <option value="Tender Lost">Tender Lost</option>
                    <option value="Tender Regret">Tender Regret</option>
                    <option value="Tender Cancelled">Tender Cancelled</option>
                  </select>
                </td>
                <td className="p-4 text-center">
                  <button onClick={() => openEditModal(t)} className="p-2 text-slate-400 hover:text-indigo-600 transition-colors">
                    <Edit3 size={18} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white p-8 rounded-[2rem] w-full max-w-5xl max-h-[90vh] overflow-y-auto shadow-2xl relative custom-scrollbar">
            <button onClick={() => setIsModalOpen(false)} className="absolute top-6 right-6 text-slate-400 hover:text-slate-800 transition-colors"><X size={24} /></button>
            <h2 className="text-2xl font-black mb-6 text-slate-800">{modalMode === 'add' ? 'Add New Tender' : 'Edit Tender Details'}</h2>
            <form onSubmit={handleSaveTender} className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <InputField label="Tender No *" name="tender_no" value={formData.tender_no} onChange={handleChange} required disabled={modalMode === 'edit'} />
                <InputField label="Name of Client *" name="name_of_client" value={formData.name_of_client} onChange={handleChange} required />
                <SelectField label="Tender Status" name="tender_status" value={formData.tender_status} onChange={handleChange} options={['Pending', 'Tender Quoted', 'Tender Won', 'Tender Lost', 'Tender Regret', 'Tender Cancelled']} />
                <InputField label="Received Date" name="received_date" type="date" value={formData.received_date} onChange={handleChange} />
                <InputField label="Due Date" name="due_date" type="date" value={formData.due_date} onChange={handleChange} />
                <InputField label="Pre-Bidding Date" name="pre_bidding_date" type="date" value={formData.pre_bidding_date} onChange={handleChange} />
                <InputField label="Location" name="location" value={formData.location} onChange={handleChange} />
                <InputField label="Tender Open Price" name="tender_open_price" value={formData.tender_open_price} onChange={handleChange} />
                <InputField label="Quoted Value" name="quoted_value" value={formData.quoted_value} onChange={handleChange} />
                <SelectField label="Price Status" name="price_status" value={formData.price_status} onChange={handleChange} options={['Pending', 'Submitted', 'Not Applicable']} />
                <InputField label="Project Manager" name="project_manager" value={formData.project_manager} onChange={handleChange} />
                <InputField label="Docs Prepared By" name="docs_prepared_by" value={formData.docs_prepared_by} onChange={handleChange} />
                <InputField label="Financial Year" name="financial_year" value={formData.financial_year} onChange={handleChange} />
                <InputField label="EMD Value" name="emd" value={formData.emd} onChange={handleChange} />
                <SelectField label="EMD Status" name="emd_status" value={formData.emd_status} onChange={handleChange} options={['Pending', 'Submitted', 'Exempted', 'Returned']} />
                <SelectField label="Tender Fee Status" name="tender_fee_status" value={formData.tender_fee_status} onChange={handleChange} options={['Pending', 'Paid', 'Exempted']} />
                <InputField label="Source (Portal/Email)" name="source" value={formData.source} onChange={handleChange} />
              </div>
              <div className="grid grid-cols-1 gap-6">
                <div><label className="block text-[11px] uppercase font-bold text-slate-500 mb-2">Description</label><textarea name="description" value={formData.description} onChange={handleChange} rows="2" className="w-full p-3 border border-slate-200 rounded-xl outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"></textarea></div>
                <div><label className="block text-[11px] uppercase font-bold text-slate-500 mb-2">Comments</label><textarea name="comments" value={formData.comments} onChange={handleChange} rows="2" className="w-full p-3 border border-slate-200 rounded-xl outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"></textarea></div>
              </div>
              
              <div className="pt-4 flex justify-between items-center border-t">
                {modalMode === 'edit' ? (
                  <button 
                    type="button" 
                    onClick={() => handleDeleteTender(formData.tender_no)}
                    className="px-6 py-3 font-bold text-rose-600 hover:bg-rose-50 rounded-xl transition-colors flex items-center gap-2"
                  >
                    <Trash2 size={18} /> Delete Tender
                  </button>
                ) : (
                  <div></div>
                )}

                <div className="flex gap-3">
                  <button type="button" onClick={() => setIsModalOpen(false)} className="px-6 py-3 font-bold text-slate-500 hover:bg-slate-100 rounded-xl transition-colors">Cancel</button>
                  <button type="submit" disabled={loading} className="px-8 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold transition-colors flex items-center gap-2">{loading ? 'Saving...' : 'Save Tender Record'}</button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

const StatCard = ({ title, value, icon }) => (
  <div className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm flex items-center justify-between hover:shadow-md transition-shadow">
    <div><p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{title}</p><h3 className="text-3xl font-black text-slate-800 mt-1">{value}</h3></div>
    <div className="p-4 bg-slate-50 rounded-2xl">{icon}</div>
  </div>
);

const InputField = ({ label, name, type = "text", value, onChange, required = false, disabled = false }) => (
  <div>
    <label className="block text-[11px] uppercase font-bold text-slate-500 mb-2">{label}</label>
    <input type={type} name={name} value={value} onChange={onChange} required={required} disabled={disabled} className={`w-full p-3 border border-slate-200 rounded-xl outline-none transition-colors ${disabled ? 'bg-slate-100 text-slate-400 cursor-not-allowed' : 'focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500'}`} />
  </div>
);

const SelectField = ({ label, name, value, onChange, options }) => (
  <div>
    <label className="block text-[11px] uppercase font-bold text-slate-500 mb-2">{label}</label>
    <select name={name} value={value} onChange={onChange} className="w-full p-3 border border-slate-200 rounded-xl outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 bg-white">{options.map(opt => <option key={opt} value={opt}>{opt}</option>)}</select>
  </div>
);

export default MasterDashboard;