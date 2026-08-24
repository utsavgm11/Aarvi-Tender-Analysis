import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { 
  Target, Clock, CheckCircle, XCircle, FileText, 
  Search, Plus, Edit3, X, Trash2, LayoutGrid, BarChart3, Save, Eye, Upload
} from 'lucide-react';
import PostBidForm from '../components/ui/PostBidForm'; 

// 📊 Global Custom CSV Export Columns Definition
const ALL_EXPORT_COLUMNS = [
  { key: 'tender_no', label: 'Tender No' },
  { key: 'name_of_client', label: 'Client Name' },
  { key: 'project_manager', label: 'Project Manager' },
  { key: 'description', label: 'Description' },
  { key: 'tender_status', label: 'Status' },
  { key: 'due_date', label: 'Due Date' },
  { key: 'received_date', label: 'Received Date' },
  { key: 'pre_bidding_date', label: 'Pre-Bidding Date' },
  { key: 'financial_year', label: 'Financial Year' },
  { key: 'location', label: 'Location' },
  { key: 'tender_open_price', label: 'Tender Open Price' },
  { key: 'quoted_value', label: 'Quoted Value' },
  { key: 'price_status', label: 'Price Status' },
  { key: 'emd', label: 'EMD Value' },
  { key: 'emd_status', label: 'EMD Status' },
  { key: 'tender_fee_status', label: 'Tender Fee Status' },
  { key: 'docs_prepared_by', label: 'Docs Prepared By' },
  { key: 'source', label: 'Source' },
  { key: 'comments', label: 'Comments' },
  { key: 'aarvi_rank', label: 'Aarvi Rank' },
  { key: 'reason_for_loss', label: 'Reason for Loss' },
  { key: 'post_bid_remarks', label: 'Post-Bid Remarks' },
];

const MasterDashboard = () => {
  const [tenders, setTenders] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedFY, setSelectedFY] = useState('All'); 
  const [selectedStatus, setSelectedStatus] = useState('All'); 
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState('add');
  
  // 👁️ Summary View Modal State
  const [isSummaryModalOpen, setIsSummaryModalOpen] = useState(false);
  const [viewSummaryTender, setViewSummaryTender] = useState(null);

  // 🗂️ Active Tab State for Edit Form
  const [activeFormTab, setActiveFormTab] = useState('core');
  
  // Post-Bid Intelligence States
  const [isPostBidModalOpen, setIsPostBidModalOpen] = useState(false);
  const [selectedTenderForPostBid, setSelectedTenderForPostBid] = useState(null);
  
  // File Upload State
  const [summaryFile, setSummaryFile] = useState(null);

  // 📥 Custom CSV Export Modal States
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [selectedColumns, setSelectedColumns] = useState([
    'tender_no', 'name_of_client', 'project_manager', 'description', 'due_date', 'tender_status'
  ]);

  const [formData, setFormData] = useState({
    tender_no: '', name_of_client: '', tender_status: 'Pending', 
    received_date: '', due_date: '', location: '', 
    tender_open_price: '', quoted_value: '', description: '', 
    project_manager: '', emd: '', emd_status: 'Pending', 
    tender_fee_status: 'Pending', price_status: 'Pending', source: '', 
    comments: '', docs_prepared_by: '', financial_year: '2023-2024', pre_bidding_date: '',
    aarvi_rank: '', reason_for_loss: '', post_bid_remarks: '',
    competitors: [{ rank: 'L1', company: '', amount: '', percent_diff: '' }]
  });

  const API_BASE_URL = import.meta.env.VITE_API_URL || "https://attract-appeals-recorded-able.trycloudflare.com";

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
    setActiveFormTab('core');
    setSummaryFile(null);
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
    setActiveFormTab('core');
    setSummaryFile(null);
    setFormData({
      ...tender,
      received_date: tender.received_date ? tender.received_date.split(' ')[0] : '',
      due_date: tender.due_date ? tender.due_date.split(' ')[0] : '', 
      pre_bidding_date: tender.pre_bidding_date ? tender.pre_bidding_date.split(' ')[0] : '',
      aarvi_rank: tender.aarvi_rank || '',
      reason_for_loss: tender.reason_for_loss || '',
      post_bid_remarks: tender.post_bid_remarks || '',
      competitors: tender.competitors && tender.competitors.length > 0 
        ? tender.competitors 
        : [{ rank: 'L1', company: '', amount: '', percent_diff: '' }]
    });
    setIsModalOpen(true);
  };

  const openSummaryModal = (tender) => {
    setViewSummaryTender(tender);
    setIsSummaryModalOpen(true);
  };

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
    
    // 🎯 FIX: Safely strip commas from user input before sending to backend float fields
    const cleanNumber = (val) => {
      if (val === '' || val === null || val === undefined) return null;
      const parsed = parseFloat(String(val).replace(/,/g, ''));
      return isNaN(parsed) ? null : parsed;
    };

    const formattedCompetitors = formData.competitors.map(c => ({
      rank: c.rank,
      company: c.company || "Unknown Competitor",
      amount: cleanNumber(c.amount) || 0.00,
      percent_diff: c.percent_diff ? parseFloat(c.percent_diff) : 0.00
    }));

    const cleanedData = {
      ...formData,
      tender_open_price: cleanNumber(formData.tender_open_price),
      quoted_value: cleanNumber(formData.quoted_value),
      pre_bidding_date: formData.pre_bidding_date === '' ? null : formData.pre_bidding_date,
      competitors: formattedCompetitors
    };

    try {
      setLoading(true);
      
      if (summaryFile) {
        const payload = new FormData();
        payload.append('summary_file', summaryFile);
        payload.append('tender_data', JSON.stringify(cleanedData));
        
        const config = { headers: { 'Content-Type': 'multipart/form-data' } };
        
        if (modalMode === 'add') {
          await axios.post(`${API_BASE_URL}/tenders-with-file`, payload, config);
        } else {
          await axios.put(`${API_BASE_URL}/tenders-with-file/${encodeURIComponent(formData.tender_no)}`, payload, config);
        }
      } else {
        if (modalMode === 'add') {
          await axios.post(`${API_BASE_URL}/tenders`, cleanedData);
        } else {
          await axios.put(`${API_BASE_URL}/tenders/${encodeURIComponent(formData.tender_no)}`, cleanedData);
        }
      }

      setIsModalOpen(false);
      setSummaryFile(null);
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

  // 📅 UTILITY: Format Date to strictly DD-MM-YYYY
  const formatDisplayDate = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    if (isNaN(date)) return 'N/A';
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}-${month}-${year}`;
  };

  // 🔍 Filter Logic (Client/Tender search + FY + Status Dropdown)
  const sortedTenders = useMemo(() => {
    const filtered = tenders.filter(t => {
      const matchesSearch = t.name_of_client?.toLowerCase().includes(searchTerm.toLowerCase()) || 
                            t.tender_no?.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesFY = selectedFY === 'All' || t.financial_year === selectedFY;
      const matchesStatus = selectedStatus === 'All' || t.tender_status === selectedStatus;
      return matchesSearch && matchesFY && matchesStatus;
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
  }, [tenders, searchTerm, selectedFY, selectedStatus, today]);

  // 📥 CUSTOM EXPORT CSV LOGIC
  const handleColumnToggle = (columnKey) => {
    setSelectedColumns(prev => 
      prev.includes(columnKey) ? prev.filter(k => k !== columnKey) : [...prev, columnKey]
    );
  };

  const handleSelectAllColumns = () => setSelectedColumns(ALL_EXPORT_COLUMNS.map(c => c.key));
  const handleClearAllColumns = () => setSelectedColumns([]);

  const handleExportCustomCSV = () => {
    if (selectedColumns.length === 0) {
      alert("Please select at least one column to export.");
      return;
    }

    const activeHeaders = ALL_EXPORT_COLUMNS.filter(c => selectedColumns.includes(c.key));
    const headerRow = activeHeaders.map(c => `"${c.label}"`).join(',');

    const dataRows = sortedTenders.map(row => {
      return activeHeaders.map(col => {
        let val = row[col.key];
        if (val === null || val === undefined) val = '';
        if (typeof val === 'string') {
          val = val.replace(/"/g, '""'); // Escape inner double quotes
        }
        return `"${val}"`;
      }).join(',');
    });

    const csvContent = [headerRow, ...dataRows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    
    const link = document.createElement('a');
    link.href = url;
    const statusSuffix = selectedStatus !== 'All' ? `_${selectedStatus}` : '';
    link.setAttribute('download', `Tender_Report${statusSuffix}_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    setIsExportModalOpen(false);
  };

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
    // 🎯 FIX: Wrapped the entire dashboard in a strictly constrained flex container to enforce exact alignment boundaries
    <div className="relative p-4 sm:p-6 md:p-8 h-full w-full flex-1 bg-slate-50 overflow-y-auto">
      <div className="max-w-[1600px] mx-auto w-full flex flex-col">
        
        {/* 📊 Responsive Stats Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 mb-6 sm:mb-8 w-full">
          <StatCard title="Total Active" value={stats.totalActive} icon={<Clock className="text-blue-500 w-5 h-5 sm:w-6 sm:h-6"/>} />
          <StatCard title="Tender Quoted" value={stats.quoted} icon={<Target className="text-amber-500 w-5 h-5 sm:w-6 sm:h-6"/>} />
          <StatCard title="Tenders Won" value={stats.won} icon={<CheckCircle className="text-emerald-600 w-5 h-5 sm:w-6 sm:h-6"/>} />
          <StatCard title="Tenders Lost" value={stats.lost} icon={<XCircle className="text-rose-500 w-5 h-5 sm:w-6 sm:h-6"/>} />
        </div>

        {/* 🔍 Search & Filters Bar */}
        <div className="flex flex-col lg:flex-row justify-between items-stretch lg:items-center gap-4 mb-6 w-full">
          
          <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 items-stretch sm:items-center w-full lg:w-auto">
            {/* Search Box */}
            <div className="relative w-full sm:w-64 lg:w-80">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
              <input 
                className="w-full pl-10 pr-4 py-2.5 sm:py-2 rounded-xl border outline-none focus:ring-2 focus:ring-indigo-500 transition-all text-sm sm:text-base bg-white" 
                placeholder="Search Client or Tender..." 
                onChange={(e) => setSearchTerm(e.target.value)} 
              />
            </div>
            
            {/* FY Filter Dropdown */}
            <select 
              value={selectedFY} 
              onChange={(e) => setSelectedFY(e.target.value)}
              className="bg-white border border-slate-200 px-4 py-2.5 sm:py-2 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 font-medium text-slate-600 cursor-pointer text-sm sm:text-base w-full sm:w-auto"
            >
              {availableFYs.map(fy => (
                <option key={fy} value={fy}>{fy === 'All' ? 'All Financial Years' : fy}</option>
              ))}
            </select>

            {/* 🎯 Status Filter Dropdown */}
            <select 
              value={selectedStatus} 
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="bg-white border border-slate-200 px-4 py-2.5 sm:py-2 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500 font-semibold text-indigo-600 cursor-pointer text-sm sm:text-base w-full sm:w-auto"
            >
              <option value="All">All Statuses</option>
              <option value="Pending">Pending</option>
              <option value="Tender Quoted">Tender Quoted</option>
              <option value="Tender Won">Tender Won</option>
              <option value="Tender Lost">Tender Lost</option>
              <option value="Tender Regret">Tender Regret</option>
              <option value="Tender Cancelled">Tender Cancelled</option>
            </select>
          </div>

          <div className="flex flex-row gap-2 sm:gap-3 w-full lg:w-auto">
            <button onClick={openAddModal} className="flex-1 lg:flex-none justify-center bg-emerald-600 hover:bg-emerald-700 transition-colors text-white px-4 sm:px-5 py-2.5 sm:py-2 rounded-xl sm:rounded-lg font-bold flex items-center gap-2 text-sm sm:text-base">
              <Plus size={16}/> <span className="hidden sm:inline">Add Tender</span><span className="sm:hidden">Add</span>
            </button>
            <button onClick={() => setIsExportModalOpen(true)} className="flex-1 lg:flex-none justify-center bg-slate-800 hover:bg-slate-900 transition-colors text-white px-4 sm:px-5 py-2.5 sm:py-2 rounded-xl sm:rounded-lg font-bold flex items-center gap-2 text-sm sm:text-base">
              <FileText size={16} /> <span className="hidden sm:inline">Export CSV</span><span className="sm:hidden">Export</span>
            </button>
          </div>
        </div>

        {/* 📋 Data Table Container */}
        {/* 🎯 FIX: Added overflow-hidden to the wrapper and table-fixed to the table to force absolute uniform column edges */}
        <div className="bg-white rounded-xl sm:rounded-2xl border shadow-sm w-full overflow-hidden">
          <div className="overflow-x-auto custom-scrollbar w-full">
            <table className="w-full text-left min-w-[900px] table-fixed">
              <thead className="bg-slate-900 text-white text-xs uppercase tracking-wider">
                <tr>
                  <th className="p-3 sm:p-4 whitespace-nowrap text-left w-[18%]">Client</th>
                  <th className="p-3 sm:p-4 whitespace-nowrap text-left w-[15%]">Tender No</th>
                  <th className="p-3 sm:p-4 whitespace-nowrap text-left w-[15%]">Project Manager</th>
                  <th className="p-3 sm:p-4 whitespace-nowrap text-left w-[22%]">Description</th>
                  <th className="p-3 sm:p-4 whitespace-nowrap text-center w-[10%]">Due Date</th>
                  <th className="p-3 sm:p-4 whitespace-nowrap text-center w-[12%]">Status</th>
                  <th className="p-3 sm:p-4 whitespace-nowrap text-center w-[8%]">Action</th>
                </tr>
              </thead>
              <tbody>
                {sortedTenders.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="p-8 text-center text-slate-400 italic">No tenders match your search criteria.</td>
                  </tr>
                ) : (
                  sortedTenders.map((t) => (
                    <tr key={t.tender_no} className={`border-b text-xs sm:text-sm transition-all hover:bg-slate-50 ${getRowStyle(t.due_date)}`}>
                      <td className="p-3 sm:p-4 font-bold text-slate-700 truncate text-left" title={t.name_of_client}>{t.name_of_client}</td>
                      <td className="p-3 sm:p-4 font-mono text-slate-500 truncate text-left" title={t.tender_no}>{t.tender_no}</td>
                      <td className="p-3 sm:p-4 font-medium text-slate-600 truncate text-left" title={t.project_manager}>{t.project_manager || 'N/A'}</td>
                      <td className="p-3 sm:p-4 text-slate-600 truncate text-left" title={t.description}>{t.description || 'N/A'}</td>
                      <td className="p-3 sm:p-4 font-bold truncate text-center">{formatDisplayDate(t.due_date)}</td>
                      <td className="p-3 sm:p-4 text-center">
                        <select 
                          value={t.tender_status || 'Pending'} 
                          onChange={(e) => handleStatusChange(t.tender_no, e.target.value)} 
                          className="bg-transparent border p-1 rounded font-black text-[9px] sm:text-[10px] uppercase text-indigo-600 outline-none cursor-pointer hover:bg-indigo-50 w-full min-w-[100px] text-center"
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
                        <div className="flex items-center justify-center gap-1">
                          <button 
                            onClick={() => openSummaryModal(t)} 
                            title="View Tender Summary"
                            className="p-1.5 sm:p-2 text-slate-400 hover:text-indigo-600 transition-colors rounded-lg hover:bg-indigo-50"
                          >
                            <Eye size={18} className="w-[16px] h-[16px] sm:w-[18px] sm:h-[18px]" />
                          </button>
                          <button 
                            onClick={() => openEditModal(t)} 
                            title="Edit Tender Details"
                            className="p-1.5 sm:p-2 text-slate-400 hover:text-indigo-600 transition-colors rounded-lg hover:bg-indigo-50"
                          >
                            <Edit3 size={18} className="w-[16px] h-[16px] sm:w-[18px] sm:h-[18px]" />
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
      </div>

      {/* 👑 MASTER FORM CONTAINER PANEL (ADD / EDIT) */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50 p-2 sm:p-4 animate-in fade-in duration-200">
          <div className="bg-white p-4 sm:p-6 md:p-8 rounded-[1.5rem] sm:rounded-[2rem] w-full max-w-5xl max-h-[95vh] sm:max-h-[90vh] overflow-y-auto shadow-2xl relative custom-scrollbar flex flex-col">
            <button onClick={() => setIsModalOpen(false)} className="absolute top-4 right-4 sm:top-6 sm:right-6 text-slate-400 hover:text-slate-800 transition-colors bg-white rounded-full sm:bg-transparent p-1 sm:p-0 z-10 shadow-sm sm:shadow-none"><X size={20} className="sm:w-[24px] sm:h-[24px]" /></button>
            
            <h2 className="text-xl sm:text-2xl font-black text-slate-800 mb-2 sm:mb-4 pr-8 shrink-0">
              {modalMode === 'add' ? 'Add New Tender' : 'Edit Tender Details'}
            </h2>

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
                      
                      {/* 📄 Upload Tender Summary PDF/Word Field */}
                      <div>
                        <label className="block text-[10px] sm:text-[11px] uppercase font-bold text-slate-500 mb-1.5 sm:mb-2">Upload Tender Summary (PDF/Word)</label>
                        <input 
                          type="file" 
                          accept=".pdf,.doc,.docx"
                          onChange={(e) => setSummaryFile(e.target.files[0])}
                          className="w-full p-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-bold file:bg-indigo-50 file:text-indigo-600 hover:file:bg-indigo-100 cursor-pointer outline-none"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-1 gap-4 sm:gap-6">
                      <div><label className="block text-[10px] sm:text-[11px] uppercase font-bold text-slate-500 mb-1.5 sm:mb-2">Description</label><textarea name="description" value={formData.description} onChange={handleChange} rows="2" className="w-full p-2.5 sm:p-3 border border-slate-200 rounded-xl outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 text-sm sm:text-base"></textarea></div>
                      <div><label className="block text-[10px] sm:text-[11px] uppercase font-bold text-slate-500 mb-1.5 sm:mb-2">Comments</label><textarea name="comments" value={formData.comments} onChange={handleChange} rows="2" className="w-full p-2.5 sm:p-3 border border-slate-200 rounded-xl outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 text-sm sm:text-base"></textarea></div>
                    </div>
                  </div>
                )}

                {/* PAGE TAB 2: LOSS INTEL */}
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

      {/* 👁️ VIEW TENDER SUMMARY MODAL */}
      {isSummaryModalOpen && viewSummaryTender && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
          <div className="bg-white p-6 sm:p-8 rounded-[1.5rem] w-full max-w-4xl max-h-[90vh] overflow-y-auto shadow-2xl relative custom-scrollbar flex flex-col">
            <button onClick={() => setIsSummaryModalOpen(false)} className="absolute top-4 right-4 text-slate-400 hover:text-slate-800 transition-colors p-1 z-10 bg-white rounded-full">
              <X size={20} />
            </button>
            <div className="shrink-0">
              <h3 className="text-xl font-black text-slate-800 mb-1 pr-6">{viewSummaryTender.name_of_client}</h3>
              <p className="text-xs font-mono font-bold text-indigo-600 mb-6">Tender No: {viewSummaryTender.tender_no}</p>
              
              <div className="space-y-4 text-sm text-slate-700">
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100">
                    <span className="text-[10px] font-bold uppercase text-slate-400 block mb-0.5">Project Manager</span>
                    <p className="font-bold text-slate-800">{viewSummaryTender.project_manager || 'Not Assigned'}</p>
                  </div>
                  <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100">
                    <span className="text-[10px] font-bold uppercase text-slate-400 block mb-0.5">Financial Year</span>
                    <p className="font-bold text-slate-800">{viewSummaryTender.financial_year || 'N/A'}</p>
                  </div>
                </div>

                <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                  <span className="text-[10px] font-bold uppercase text-slate-400 block mb-1">Tender Description</span>
                  <p className="whitespace-pre-wrap text-xs sm:text-sm leading-relaxed">{viewSummaryTender.description || 'No description provided.'}</p>
                </div>
              </div>
            </div>

            <div className="flex-1 mt-6 flex flex-col min-h-[400px]">
              {viewSummaryTender.summary_file_url ? (
                <div className="flex flex-col h-full">
                  <div className="flex items-center justify-between mb-3 shrink-0">
                    <div className="flex items-center gap-2 text-indigo-900 font-bold text-xs">
                      <FileText size={18} />
                      <span className="uppercase tracking-wider">Embedded Summary Document</span>
                    </div>
                    <a 
                      href={viewSummaryTender.summary_file_url} 
                      target="_blank" 
                      rel="noreferrer" 
                      className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold transition-colors shadow-sm"
                    >
                      Open in New Tab
                    </a>
                  </div>
                  <div className="w-full flex-1 bg-slate-100 rounded-xl overflow-hidden border border-slate-200">
                    <iframe 
                      src={viewSummaryTender.summary_file_url.toLowerCase().endsWith('.pdf') ? viewSummaryTender.summary_file_url : `https://docs.google.com/gview?url=${encodeURIComponent(viewSummaryTender.summary_file_url)}&embedded=true`} 
                      width="100%" 
                      height="100%" 
                      title="Tender Summary Document"
                      className="border-none bg-white"
                    />
                  </div>
                </div>
              ) : (
                <div className="p-6 bg-slate-50 border border-dashed border-slate-200 rounded-xl text-center text-xs text-slate-400 italic flex items-center justify-center h-full">
                  No summary document attached to this tender.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 📥 CUSTOM COLUMN EXPORT MODAL */}
      {isExportModalOpen && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
          <div className="bg-white p-6 rounded-[1.5rem] w-full max-w-xl max-h-[85vh] overflow-y-auto shadow-2xl relative custom-scrollbar flex flex-col">
            <button onClick={() => setIsExportModalOpen(false)} className="absolute top-4 right-4 text-slate-400 hover:text-slate-800 transition-colors p-1">
              <X size={20} />
            </button>

            <h3 className="text-xl font-black text-slate-800 mb-1">Custom Export Columns</h3>
            <p className="text-xs text-slate-500 mb-4">Select the specific fields you want included in your downloadable CSV report ({sortedTenders.length} rows matched).</p>

            {/* Quick Toggle Controls */}
            <div className="flex justify-between items-center bg-slate-50 p-3 rounded-xl mb-4 border border-slate-100">
              <span className="text-xs font-bold text-slate-600">{selectedColumns.length} of {ALL_EXPORT_COLUMNS.length} Selected</span>
              <div className="flex gap-2 text-xs font-bold">
                <button type="button" onClick={handleSelectAllColumns} className="text-indigo-600 hover:underline">Select All</button>
                <span className="text-slate-300">|</span>
                <button type="button" onClick={handleClearAllColumns} className="text-slate-500 hover:underline">Clear All</button>
              </div>
            </div>

            {/* Column Checkbox Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-2 gap-2 max-h-60 overflow-y-auto custom-scrollbar p-1 mb-6 border border-slate-100 rounded-xl">
              {ALL_EXPORT_COLUMNS.map(col => (
                <label key={col.key} className="flex items-center gap-2 p-2 hover:bg-indigo-50/50 rounded-lg cursor-pointer text-xs font-medium text-slate-700 transition-colors">
                  <input 
                    type="checkbox" 
                    checked={selectedColumns.includes(col.key)} 
                    onChange={() => handleColumnToggle(col.key)}
                    className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 border-slate-300 cursor-pointer"
                  />
                  <span>{col.label}</span>
                </label>
              ))}
            </div>

            {/* Action Buttons */}
            <div className="flex justify-end gap-3 pt-2 border-t border-slate-100">
              <button type="button" onClick={() => setIsExportModalOpen(false)} className="px-5 py-2.5 font-bold text-slate-500 bg-slate-50 hover:bg-slate-100 rounded-xl transition-colors text-xs">
                Cancel
              </button>
              <button type="button" onClick={handleExportCustomCSV} className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold transition-colors flex items-center gap-2 text-xs">
                <FileText size={16} /> Download Selected CSV
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Post Bid Modal Component */}
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