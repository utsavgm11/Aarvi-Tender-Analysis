import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { 
  Target, Clock, CheckCircle, XCircle, FileText, 
  Search, Plus, Edit3, X, Trash2, LayoutGrid, BarChart3, Save
} from 'lucide-react';
import PostBidForm from '../components/ui/PostBidForm'; 

const MasterDashboard = () => {
  const [tenders, setTenders] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedFY, setSelectedFY] = useState('All'); 
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState('add');
  
  // 🗂️ NEW: Active Tab State for the Edit Form Modal Panel
  const [activeFormTab, setActiveFormTab] = useState('core'); // 'core' or 'loss_intel'

  // Post-Bid Intelligence States
  const [isPostBidModalOpen, setIsPostBidModalOpen] = useState(false);
  const [selectedTenderForPostBid, setSelectedTenderForPostBid] = useState(null);
  
  const [formData, setFormData] = useState({
    tender_no: '', name_of_client: '', tender_status: 'Pending', 
    received_date: '', due_date: '', location: '', 
    tender_open_price: '', quoted_value: '', description: '', 
    project_manager: '', emd: '', emd_status: 'Pending', 
    tender_fee_status: 'Pending', price_status: 'Pending', source: '', 
    comments: '', docs_prepared_by: '', financial_year: '2023-2024', pre_bidding_date: '',
    // 📊 Added matching post-bid schema keys directly into the main state data tree
    aarvi_rank: '', reason_for_loss: '', post_bid_remarks: '',
    competitors: [{ rank: 'L1', company: '', amount: '', percent_diff: '' }]
  });

  const API_BASE_URL = import.meta.env.VITE_API_URL || "https://aarvi-tender-api.onrender.com";

  const fetchTenders = async () => {
    try {
      const managerName = localStorage.getItem('managerName');
      const userRole = localStorage.getItem('userRole'); 
      const queryParams = {};
      
      if (userRole !== 'admin' && managerName && managerName !== 'undefined' && managerName !== 'null') {
        queryParams.manager = managerName;
      }

      const res = await axios.get(`${API_BASE_URL}/tenders`, { params: queryParams });
      setTenders(res.data);
    } catch (err) { console.error("Fetch Error:", err); }
  };

  useEffect(() => { 
    fetchTenders().finally(() => setLoading(false));
  }, []);

  const handleStatusChange = async (tender_no, newStatus) => {
    if (newStatus === 'Tender Lost') {
      setSelectedTenderForPostBid(tender_no);
      setIsPostBidModalOpen(true);
      return; 
    }

    try {
      await axios.patch(`${API_BASE_URL}/tenders/${encodeURIComponent(tender_no)}/status`, { tender_status: newStatus });
      fetchTenders(); 
    } catch (err) { alert("Error Updating: " + (err.response?.data?.error || err.message)); }
  };

  const handlePostBidSuccess = async (postBidPayload) => {
    try {
      await axios.put(`${API_BASE_URL}/log-loss/${encodeURIComponent(selectedTenderForPostBid)}`, postBidPayload);
      setIsPostBidModalOpen(false);
      setSelectedTenderForPostBid(null);
      fetchTenders(); 
    } catch (err) {
      console.error("Error logging leaderboard data:", err);
      alert("Failed to save leaderboard data: " + JSON.stringify(err.response?.data?.detail || err.message));
    }
  };

  const openAddModal = () => {
    setModalMode('add');
    setActiveFormTab('core'); // Reset tab view
    setFormData({ 
      tender_no: '', name_of_client: '', tender_status: 'Pending', 
      received_date: '', due_date: '', location: '', 
      tender_open_price: '', quoted_value: '', description: '', 
      project_manager: '', emd: '', emd_status: 'Pending', 
      tender_fee_status: 'Pending', price_status: 'Pending', source: '', 
      comments: '', docs_prepared_by: '', financial_year: '2023-2024', pre_bidding_date: '',
      aarvi_rank: '', reason_for_loss: '', post_bid_remarks: '',
      competitors: [{ rank: 'L1', company: '', amount: '', percent_diff: '' }]
    });
    setIsModalOpen(true);
  };

  const openEditModal = (tender) => {
    setModalMode('edit');
    setActiveFormTab('core'); // Always open on Core details tab first
    setFormData({
      ...tender,
      received_date: tender.received_date ? tender.received_date.split(' ')[0] : '',
      due_date: tender.due_date ? tender.due_date.split(' ')[0] : '', 
      pre_bidding_date: tender.pre_bidding_date ? tender.pre_bidding_date.split(' ')[0] : '',
      // Map existing layout fields or fallback safely to blanks
      aarvi_rank: tender.aarvi_rank || '',
      reason_for_loss: tender.reason_for_loss || '',
      post_bid_remarks: tender.post_bid_remarks || '',
      competitors: tender.competitors && tender.competitors.length > 0 
        ? tender.competitors 
        : [{ rank: 'L1', company: '', amount: '', percent_diff: '' }]
    });
    setIsModalOpen(true);
  };

  // Automated Aarvi Tracking sync inside the inline array form
  useEffect(() => {
    if (formData.aarvi_rank && formData.aarvi_rank !== 'Disqualified' && formData.aarvi_rank !== 'L5+') {
      const exists = formData.competitors.some(c => c.rank === formData.aarvi_rank);
      if (!exists) {
        const filtered = formData.competitors.filter(c => c.company?.toLowerCase() !== 'aarvi encon');
        setFormData(prev => ({
          ...prev,
          competitors: [
            ...filtered,
            { rank: formData.aarvi_rank, company: 'Aarvi Encon', amount: '', percent_diff: '' }
          ].sort((a, b) => a.rank.localeCompare(b.rank))
        }));
      }
    }
  }, [formData.aarvi_rank]);

  const handleCompetitorChange = (index, field, value) => {
    const updated = [...formData.competitors];
    updated[index][field] = value;
    setFormData({ ...formData, competitors: updated });
  };

  const addCompetitorRow = () => {
    if (formData.competitors.length >= 5) {
      alert("You can record up to L5 leaderboard data matrix.");
      return;
    }
    const nextRank = `L${formData.competitors.length + 1}`;
    setFormData({
      ...formData,
      competitors: [...formData.competitors, { rank: nextRank, company: '', amount: '', percent_diff: '' }]
    });
  };

  const removeCompetitorRow = (index) => {
    if (formData.competitors[index].company === 'Aarvi Encon') {
      alert("To alter Aarvi Encon positioning, please adjust the status rank selector directly.");
      return;
    }
    setFormData({
      ...formData,
      competitors: formData.competitors.filter((_, i) => i !== index)
    });
  };

  const handleSaveTender = async (e) => {
    e.preventDefault();
    
    // Clean up numerical string arrays cleanly before shipping payload
    const formattedCompetitors = formData.competitors.map(c => ({
      rank: c.rank,
      company: c.company || "Unknown Competitor",
      amount: c.amount ? parseFloat(c.amount) : 0.00,
      percent_diff: c.percent_diff ? parseFloat(c.percent_diff) : 0.00
    }));

    const cleanedData = {
      ...formData,
      tender_open_price: formData.tender_open_price === '' ? null : parseFloat(formData.tender_open_price),
      quoted_value: formData.quoted_value === '' ? null : parseFloat(formData.quoted_value),
      pre_bidding_date: formData.pre_bidding_date === '' ? null : formData.pre_bidding_date,
      competitors: formattedCompetitors
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
      } catch (err) { alert("Delete failed: " + err.message); } finally { setLoading(false); }
    }
  };

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

  const sortedTenders = useMemo(() => {
    const filtered = tenders.filter(t => {
      const matchesSearch = t.name_of_client?.toLowerCase().includes(searchTerm.toLowerCase()) || 
                            t.tender_no?.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesFY = selectedFY === 'All' || t.financial_year === selectedFY;
      return matchesSearch && matchesFY;
    });

    return filtered.sort((a, b) => {
      const dateA = a.due_date ? new Date(a.due_date) : new Date('9999-12-31');
      const dateB = b.due_date ? new Date(b.due_date) : new Date('9999-12-31');
      const isAActive = dateA >= today;
      const isBActive = dateB >= today;
      if (isAActive && !isBActive) return -1;
      if (!isAActive && isBActive) return 1;
      if (isAActive && isBActive) return dateA - dateB;
      return dateB - dateA;
    });
  }, [tenders, searchTerm, selectedFY, today]);

  const stats = useMemo(() => ({
    totalActive: tenders.filter(t => 
      t.due_date && new Date(t.due_date) >= today && 
      !['Tender Won', 'Tender Lost', 'Tender Cancelled', 'Tender Regret'].includes(t.tender_status)
    ).length,
    quoted: tenders.filter(t => 
      ['Tender Won', 'Tender Lost', 'Tender Quoted', 'Quoted', 'Quoted Active', 'Tender Cancelled'].includes(t.tender_status)
    ).length,
    won: tenders.filter(t => t.tender_status === 'Tender Won').length,
    lost: tenders.filter(t => t.tender_status === 'Tender Lost').length,
  }), [tenders, today]);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  if (loading && tenders.length === 0) return <div className="p-20 text-center font-bold text-slate-400">Loading Database...</div>;

  return (
    <div className="relative p-4 sm:p-6 md:p-8 h-full bg-slate-50 overflow-y-auto">
      
      {/* 📊 Responsive Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 mb-6 sm:mb-8">
        <StatCard title="Total Active" value={stats.totalActive} icon={<Clock className="text-blue-500 w-5 h-5 sm:w-6 sm:h-6"/>} />
        <StatCard title="Tender Quoted" value={stats.quoted} icon={<Target className="text-amber-500 w-5 h-5 sm:w-6 sm:h-6"/>} />
        <StatCard title="Tenders Won" value={stats.won} icon={<CheckCircle className="text-emerald-600 w-5 h-5 sm:w-6 sm:h-6"/>} />
        <StatCard title="Tenders Lost" value={stats.lost} icon={<XCircle className="text-rose-500 w-5 h-5 sm:w-6 sm:h-6"/>} />
      </div>

      {/* 🔍 Search & Filters Bar */}
      <div className="flex flex-col lg:flex-row justify-between items-stretch lg:items-center gap-4 mb-6">
        
        <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 items-stretch sm:items-center w-full lg:w-auto">
          <div className="relative w-full sm:w-72 lg:w-96">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
            <input 
              className="w-full pl-10 pr-4 py-2.5 sm:py-2 rounded-xl border outline-none focus:ring-2 focus:ring-indigo-500 transition-all text-sm sm:text-base" 
              placeholder="Search Client or Tender..." 
              onChange={(e) => setSearchTerm(e.target.value)} 
            />
          </div>
          
          <select 
            value={selectedFY} 
            onChange={(e) => setSelectedFY(e.target.value)}
            className="bg-white border border-slate-200 px-4 py-2.5 sm:py-2 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 font-medium text-slate-600 cursor-pointer text-sm sm:text-base w-full sm:w-auto"
          >
            {availableFYs.map(fy => (
              <option key={fy} value={fy}>{fy === 'All' ? 'All Financial Years' : fy}</option>
            ))}
          </select>
        </div>

        <div className="flex flex-row gap-2 sm:gap-3 w-full lg:w-auto">
          <button onClick={openAddModal} className="flex-1 lg:flex-none justify-center bg-emerald-600 hover:bg-emerald-700 transition-colors text-white px-4 sm:px-5 py-2.5 sm:py-2 rounded-xl sm:rounded-lg font-bold flex items-center gap-2 text-sm sm:text-base">
            <Plus size={16}/> <span className="hidden sm:inline">Add Tender</span><span className="sm:hidden">Add</span>
          </button>
          <button onClick={handleDownload} className="flex-1 lg:flex-none justify-center bg-slate-800 hover:bg-slate-900 transition-colors text-white px-4 sm:px-5 py-2.5 sm:py-2 rounded-xl sm:rounded-lg font-bold flex items-center gap-2 text-sm sm:text-base">
            <FileText size={16} /> <span className="hidden sm:inline">Export CSV</span><span className="sm:hidden">Export</span>
          </button>
        </div>
      </div>

      {/* 📋 Responsive Data Table Container */}
      <div className="bg-white rounded-xl sm:rounded-2xl border shadow-sm w-full">
        {/* Added overflow-x-auto to make the table scroll horizontally on mobile */}
        <div className="overflow-x-auto custom-scrollbar">
          <table className="w-full text-left min-w-[700px]">
            <thead className="bg-slate-900 text-white text-xs uppercase tracking-wider">
              <tr>
                <th className="p-3 sm:p-4 whitespace-nowrap">Client</th>
                <th className="p-3 sm:p-4 whitespace-nowrap">Tender No</th>
                <th className="p-3 sm:p-4 whitespace-nowrap">Due Date</th>
                <th className="p-3 sm:p-4 whitespace-nowrap">Status</th>
                <th className="p-3 sm:p-4 text-center whitespace-nowrap">Action</th>
              </tr>
            </thead>
            <tbody>
              {sortedTenders.length === 0 ? (
                <tr>
                  <td colSpan="5" className="p-8 text-center text-slate-400 italic">No tenders match your search criteria.</td>
                </tr>
              ) : (
                sortedTenders.map((t) => (
                  <tr key={t.tender_no} className={`border-b text-xs sm:text-sm transition-all hover:bg-slate-50 ${getRowStyle(t.due_date)}`}>
                    <td className="p-3 sm:p-4 font-bold text-slate-700 max-w-[150px] sm:max-w-[250px] truncate" title={t.name_of_client}>{t.name_of_client}</td>
                    <td className="p-3 sm:p-4 font-mono text-slate-500 whitespace-nowrap">{t.tender_no}</td>
                    <td className="p-3 sm:p-4 font-bold whitespace-nowrap">{t.due_date ? new Date(t.due_date).toLocaleDateString() : 'N/A'}</td>
                    <td className="p-3 sm:p-4">
                      <select 
                        value={t.tender_status || 'Pending'} 
                        onChange={(e) => handleStatusChange(t.tender_no, e.target.value)} 
                        className="bg-transparent border p-1 rounded font-black text-[9px] sm:text-[10px] uppercase text-indigo-600 outline-none cursor-pointer hover:bg-indigo-50 w-full min-w-[100px]"
                      >
                        <option value="Pending">Pending</option>
                        <option value="Tender Quoted">Tender Quoted</option>
                        <option value="Tender Won">Tender Won</option>
                        <option value="Tender Lost">Tender Lost</option>
                        <option value="Tender Regret">Tender Regret</option>
                        <option value="Tender Cancelled">Tender Cancelled</option>
                      </select>
                    </td>
                    <td className="p-3 sm:p-4 text-center">
                      <button onClick={() => openEditModal(t)} className="p-1.5 sm:p-2 text-slate-400 hover:text-indigo-600 transition-colors">
                        <Edit3 size={18} className="w-[16px] h-[16px] sm:w-[18px] sm:h-[18px]" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 👑 MASTER FORM CONTAINER PANEL */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50 p-2 sm:p-4 animate-in fade-in duration-200">
          <div className="bg-white p-4 sm:p-6 md:p-8 rounded-[1.5rem] sm:rounded-[2rem] w-full max-w-5xl max-h-[95vh] sm:max-h-[90vh] overflow-y-auto shadow-2xl relative custom-scrollbar flex flex-col animate-in zoom-in-95 duration-200">
            <button onClick={() => setIsModalOpen(false)} className="absolute top-4 right-4 sm:top-6 sm:right-6 text-slate-400 hover:text-slate-800 transition-colors bg-white rounded-full sm:bg-transparent p-1 sm:p-0 z-10 shadow-sm sm:shadow-none"><X size={20} className="sm:w-[24px] sm:h-[24px]" /></button>
            
            <h2 className="text-xl sm:text-2xl font-black text-slate-800 mb-2 sm:mb-4 pr-8 shrink-0">
              {modalMode === 'add' ? 'Add New Tender' : 'Edit Tender Details'}
            </h2>

            {/* 📑 DYNAMIC TAB SWITCHER HEADER HEADER */}
            {formData.tender_status === 'Tender Lost' && (
              <div className="flex flex-row border-b border-slate-100 mb-4 sm:mb-6 gap-1 sm:gap-2 shrink-0 overflow-x-auto custom-scrollbar">
                <button
                  type="button"
                  onClick={() => setActiveFormTab('core')}
                  className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-5 py-2.5 sm:py-3 text-[10px] sm:text-xs font-bold uppercase tracking-wider transition-all border-b-2 whitespace-nowrap ${activeFormTab === 'core' ? 'border-b-indigo-600 text-indigo-600 bg-indigo-50/40 rounded-t-xl' : 'border-b-transparent text-slate-400 hover:text-slate-600'}`}
                >
                  <LayoutGrid size={14} className="sm:w-[16px] sm:h-[16px]" /> Core Technical Details
                </button>
                <button
                  type="button"
                  onClick={() => setActiveFormTab('loss_intel')}
                  className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-5 py-2.5 sm:py-3 text-[10px] sm:text-xs font-bold uppercase tracking-wider transition-all border-b-2 whitespace-nowrap ${activeFormTab === 'loss_intel' ? 'border-b-rose-600 text-rose-600 bg-rose-50/40 rounded-t-xl' : 'border-b-transparent text-slate-400 hover:text-slate-600'}`}
                >
                  <BarChart3 size={14} className="sm:w-[16px] sm:h-[16px]" /> L1 - L5 Loss Intelligence
                </button>
              </div>
            )}

            <form onSubmit={handleSaveTender} className="flex flex-col flex-1 min-h-0">
              
              <div className="overflow-y-auto flex-1 custom-scrollbar pb-2">
                {/* PAGE TAB 1: CORE DATA FORM PANEL */}
                {activeFormTab === 'core' && (
                  <div className="space-y-4 sm:space-y-6 transition-all duration-200 pr-1">
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
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
                    <div className="grid grid-cols-1 gap-4 sm:gap-6">
                      <div><label className="block text-[10px] sm:text-[11px] uppercase font-bold text-slate-500 mb-1.5 sm:mb-2">Description</label><textarea name="description" value={formData.description} onChange={handleChange} rows="2" className="w-full p-2.5 sm:p-3 border border-slate-200 rounded-xl outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 text-sm sm:text-base"></textarea></div>
                      <div><label className="block text-[10px] sm:text-[11px] uppercase font-bold text-slate-500 mb-1.5 sm:mb-2">Comments</label><textarea name="comments" value={formData.comments} onChange={handleChange} rows="2" className="w-full p-2.5 sm:p-3 border border-slate-200 rounded-xl outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 text-sm sm:text-base"></textarea></div>
                    </div>
                  </div>
                )}

                {/* 📊 PAGE TAB 2: SLIDING LEADERBOARD DATA MATRIX VIEW */}
                {activeFormTab === 'loss_intel' && formData.tender_status === 'Tender Lost' && (
                  <div className="space-y-4 sm:space-y-6 transition-all duration-300 bg-slate-50/50 p-3 sm:p-6 rounded-xl sm:rounded-2xl border border-slate-100 pr-1 sm:pr-6">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                      <div>
                        <label className="block text-[10px] sm:text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Aarvi's Final Position</label>
                        <select 
                          name="aarvi_rank"
                          value={formData.aarvi_rank} 
                          onChange={handleChange}
                          className="w-full p-2.5 bg-white border border-slate-200 rounded-xl focus:ring-2 focus:ring-rose-500 outline-none text-xs sm:text-sm font-semibold"
                        >
                          <option value="">Select Rank...</option>
                          <option value="L2">L2 (Runner Up)</option>
                          <option value="L3">L3</option>
                          <option value="L4">L4</option>
                          <option value="L5">L5</option>
                          <option value="L5+">Lower than L5</option>
                          <option value="Disqualified">Technically Disqualified</option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-[10px] sm:text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Primary Reason for Loss</label>
                        <select 
                          name="reason_for_loss"
                          value={formData.reason_for_loss} 
                          onChange={handleChange}
                          className="w-full p-2.5 bg-white border border-slate-200 rounded-xl focus:ring-2 focus:ring-rose-500 outline-none text-xs sm:text-sm font-semibold"
                        >
                          <option value="">Select Reason...</option>
                          <option value="Price Too High">Price Too High (Commercial)</option>
                          <option value="Technical Qualification">Lack of Technical Experience</option>
                          <option value="Financial Criteria">Failed Financial Criteria</option>
                          <option value="Client Preference">Client Preference/Relationship</option>
                          <option value="Documentation Error">Documentation Error</option>
                        </select>
                      </div>
                    </div>

                    {/* Leaderboard Array Form Fields */}
                    <div>
                      <div className="flex justify-between items-center mb-2 sm:mb-3">
                        <label className="block text-[10px] sm:text-[11px] font-bold text-slate-400 uppercase tracking-wider">Bidding Leaderboard Matrix</label>
                        <button
                          type="button"
                          onClick={addCompetitorRow}
                          className="flex items-center gap-1 text-[10px] sm:text-xs font-bold text-rose-600 bg-rose-50 hover:bg-rose-100 px-2 sm:px-2.5 py-1.5 rounded-lg transition-all"
                        >
                          <Plus size={14} /> <span className="hidden sm:inline">Add Position Row</span><span className="sm:hidden">Add</span>
                        </button>
                      </div>

                      <div className="space-y-3 sm:space-y-2 pr-1">
                        {formData.competitors.map((row, index) => (
                          <div key={index} className="grid grid-cols-2 sm:grid-cols-12 gap-2 items-center bg-white p-3 sm:p-2 rounded-xl border border-slate-200/60">
                            <div className="col-span-1 sm:col-span-2 order-1 sm:order-none">
                              <select
                                value={row.rank}
                                onChange={(e) => handleCompetitorChange(index, 'rank', e.target.value)}
                                className="w-full p-1.5 sm:p-1.5 bg-slate-50 border rounded-lg text-xs font-bold sm:text-center outline-none"
                              >
                                <option value="L1">L1</option>
                                <option value="L2">L2</option>
                                <option value="L3">L3</option>
                                <option value="L4">L4</option>
                                <option value="L5">L5</option>
                              </select>
                            </div>

                            <div className="col-span-2 sm:col-span-4 order-3 sm:order-none">
                              <input
                                type="text"
                                value={row.company}
                                disabled={row.company === 'Aarvi Encon'}
                                onChange={(e) => handleCompetitorChange(index, 'company', e.target.value)}
                                placeholder={row.rank === 'L1' ? "Winning Bidder Name" : "Company Name"}
                                required
                                className="w-full p-2 sm:p-1.5 pl-3 sm:pl-2 border rounded-lg text-xs outline-none disabled:bg-indigo-50 disabled:text-indigo-800 disabled:font-bold"
                              />
                            </div>

                            <div className="col-span-1 sm:col-span-3 order-4 sm:order-none">
                              <input
                                type="number"
                                value={row.amount}
                                onChange={(e) => handleCompetitorChange(index, 'amount', e.target.value)}
                                placeholder="Bid Value (₹)"
                                className="w-full p-2 sm:p-1.5 border rounded-lg text-xs outline-none font-mono"
                              />
                            </div>

                            <div className="col-span-1 sm:col-span-2 order-5 sm:order-none">
                              <input
                                type="number"
                                step="0.01"
                                value={row.percent_diff}
                                disabled={row.rank === 'L1'}
                                onChange={(e) => handleCompetitorChange(index, 'percent_diff', e.target.value)}
                                placeholder="Gap %"
                                className="w-full p-2 sm:p-1.5 border rounded-lg text-xs outline-none font-mono disabled:bg-slate-100 disabled:text-slate-400"
                              />
                            </div>

                            <div className="col-span-1 sm:col-span-1 text-right sm:text-center order-2 sm:order-none flex justify-end">
                              <button
                                type="button"
                                onClick={() => removeCompetitorRow(index)}
                                className="text-slate-400 hover:text-rose-500 transition-colors p-1.5 sm:p-1 bg-slate-50 sm:bg-transparent rounded-lg sm:rounded-none"
                              >
                                <Trash2 size={16} className="sm:w-[14px] sm:h-[14px]" />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div>
                      <label className="block text-[10px] sm:text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5 mt-2 sm:mt-0">Strategy Notes / Management Remarks</label>
                      <textarea
                        name="post_bid_remarks"
                        value={formData.post_bid_remarks}
                        onChange={handleChange}
                        rows="3"
                        placeholder="Type any internal operational notes here..."
                        className="w-full p-2.5 bg-white border border-slate-200 rounded-xl focus:ring-2 focus:ring-rose-500 outline-none text-xs sm:text-sm resize-none"
                      ></textarea>
                    </div>
                  </div>
                )}
              </div>

              {/* Modal Control Actions Footer */}
              <div className="pt-4 sm:pt-6 mt-4 border-t border-slate-100 shrink-0 flex flex-col sm:flex-row justify-between items-center gap-3 sm:gap-0 bg-white">
                {modalMode === 'edit' ? (
                  <button 
                    type="button" 
                    onClick={() => handleDeleteTender(formData.tender_no)}
                    className="w-full sm:w-auto px-4 sm:px-6 py-2.5 sm:py-3 font-bold text-rose-600 hover:bg-rose-50 rounded-xl transition-colors flex items-center justify-center gap-2 text-sm sm:text-base order-2 sm:order-1"
                  >
                    <Trash2 size={16} className="sm:w-[18px] sm:h-[18px]"/> <span className="sm:inline">Delete Tender</span>
                  </button>
                ) : (
                  <div className="hidden sm:block order-1"></div>
                )}

                <div className="flex w-full sm:w-auto gap-2 sm:gap-3 order-1 sm:order-2">
                  <button type="button" onClick={() => setIsModalOpen(false)} className="flex-1 sm:flex-none px-4 sm:px-6 py-2.5 sm:py-3 font-bold text-slate-500 bg-slate-50 sm:bg-transparent hover:bg-slate-100 rounded-xl transition-colors text-sm sm:text-base">Cancel</button>
                  <button type="submit" disabled={loading} className="flex-[2] sm:flex-none justify-center px-4 sm:px-8 py-2.5 sm:py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold transition-colors flex items-center gap-2 text-sm sm:text-base">
                    <Save size={16}/> {loading ? 'Saving...' : <span className="truncate">Save Record</span>}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      <PostBidForm 
        tenderId={selectedTenderForPostBid}
        isOpen={isPostBidModalOpen}
        onClose={() => { setIsPostBidModalOpen(false); setSelectedTenderForPostBid(null); }}
        onSubmitSuccess={handlePostBidSuccess}
      />
    </div>
  );
};

const StatCard = ({ title, value, icon }) => (
  <div className="bg-white p-4 sm:p-6 rounded-xl sm:rounded-2xl border border-slate-100 shadow-sm flex items-center justify-between hover:shadow-md transition-shadow">
    <div><p className="text-[9px] sm:text-[10px] font-bold text-slate-400 uppercase tracking-widest">{title}</p><h3 className="text-2xl sm:text-3xl font-black text-slate-800 mt-1">{value}</h3></div>
    <div className="p-3 sm:p-4 bg-slate-50 rounded-xl sm:rounded-2xl">{icon}</div>
  </div>
);

const InputField = ({ label, name, type = "text", value, onChange, required = false, disabled = false }) => (
  <div>
    <label className="block text-[10px] sm:text-[11px] uppercase font-bold text-slate-500 mb-1.5 sm:mb-2">{label}</label>
    <input type={type} name={name} value={value || ''} onChange={onChange} required={required} disabled={disabled} className={`w-full p-2.5 sm:p-3 border border-slate-200 rounded-xl outline-none transition-colors text-sm sm:text-base ${disabled ? 'bg-slate-100 text-slate-400 cursor-not-allowed' : 'focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 bg-white'}`} />
  </div>
);

const SelectField = ({ label, name, value, onChange, options }) => (
  <div>
    <label className="block text-[10px] sm:text-[11px] uppercase font-bold text-slate-500 mb-1.5 sm:mb-2">{label}</label>
    <select name={name} value={value || ''} onChange={onChange} className="w-full p-2.5 sm:p-3 border border-slate-200 rounded-xl outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 bg-white text-sm sm:text-base cursor-pointer">
      {options.map(opt => <option key={opt} value={opt}>{opt}</option>)}
    </select>
  </div>
);

export default MasterDashboard;