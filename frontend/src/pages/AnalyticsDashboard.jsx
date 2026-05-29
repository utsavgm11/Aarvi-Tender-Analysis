import React, { useState, useEffect, useMemo, useCallback } from 'react';
import axios from 'axios';
import { ArrowLeft, RefreshCcw } from 'lucide-react';
import { 
  BiddingTrendChart, 
  ClientBarChart, 
  StatusPieChart, 
  TenderMap,
  KPICardGroup,
  ClientPerformanceChart 
} from '../components/charts'; 

// --- CHANGED: Dynamic API routing ---
// This automatically uses localhost when you are coding, and your live Vercel URL when hosted.
// ✅ Constant: Always talk to the cloud backend
const API_BASE_URL = import.meta.env.VITE_API_URL || "https://attract-appeals-recorded-able.trycloudflare.com";// ⚠️ REPLACE THIS WITH YOUR ACTUAL LIVE BACKEND LINK

const AnalyticsDashboard = ({ onBack }) => {
  const [tenders, setTenders] = useState([]);
  const [kpiData, setKpiData] = useState({});
  const [selectedYear, setSelectedYear] = useState('All');
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // 1. Unified Fetch Logic
  // ✅ CRITICAL UPDATE: Fetching now includes the Manager Silo logic and Admin Bypass
  const fetchData = useCallback(async (isAutoPoll = false) => {
    if (!isAutoPoll) setIsRefreshing(true);
    try {
      const managerName = localStorage.getItem('managerName');
      const userRole = localStorage.getItem('userRole'); // Grab the role!
      
      const queryParams = {};
      
      // ONLY apply the manager filter if the user is a project_manager
      if (userRole !== 'admin' && managerName && managerName !== 'undefined' && managerName !== 'null') {
        queryParams.manager = managerName;
      }

      // Add the year to the KPI query params specifically
      const kpiParams = { ...queryParams, year: selectedYear };

      const [tenderRes, kpiRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/tenders`, { params: queryParams }),
        axios.get(`${API_BASE_URL}/kpi-stats`, { params: kpiParams })
      ]);
      
      setTenders(tenderRes.data);
      setKpiData(kpiRes.data);
      setError(null);
    } catch (err) {
      console.error("Fetch error:", err);
      setError("Unable to sync dashboard with database.");
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [selectedYear]);

  
  // 2. Initial load and Live Polling
  useEffect(() => {
    fetchData();
    const interval = setInterval(() => fetchData(true), 30000); // Silent refresh every 30s
    return () => clearInterval(interval);
  }, [fetchData]);

  // 3. Derived State for UI Filters
  const availableYears = useMemo(() => {
    // Extracts unique years from all tenders regardless of current filter
    const years = [...new Set(tenders.map(t => t.financial_year))].filter(Boolean);
    return ['All', ...years.sort().reverse()];
  }, [tenders]);

  // This is the data passed to all sub-charts
  const filteredTenders = useMemo(() => {
    if (selectedYear === 'All') return tenders;
    return tenders.filter(t => t.financial_year === selectedYear);
  }, [tenders, selectedYear]);

  return (
    <div className="min-h-screen p-4 sm:p-6 md:p-8 bg-slate-50">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 sm:gap-0 mb-6 sm:mb-8">
        <div className="w-full sm:w-auto">
          {onBack && (
            <button onClick={onBack} className="flex items-center gap-1 text-slate-400 hover:text-indigo-600 font-bold mb-2 transition-colors text-sm sm:text-base">
              <ArrowLeft size={16} /> <span className="hidden sm:inline">Back to Management</span><span className="sm:hidden">Back</span>
            </button>
          )}
          <div className="flex items-center gap-2 sm:gap-3">
            <h1 className="text-2xl sm:text-3xl font-black text-slate-800 tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-slate-800 to-slate-500">
              Executive Insights
            </h1>
            {isRefreshing && <RefreshCcw size={16} className="animate-spin text-indigo-500 shrink-0" />}
          </div>
        </div>
        
        {/* Financial Year Filter */}
        <div className="flex flex-col items-start sm:items-end w-full sm:w-auto">
          <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 sm:mr-2">Fiscal Period</label>
          <select 
            value={selectedYear} 
            onChange={(e) => setSelectedYear(e.target.value)}
            className="p-2 sm:p-3 bg-white border border-slate-200 rounded-xl sm:rounded-2xl text-sm sm:text-base font-black text-slate-700 shadow-sm outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all cursor-pointer w-full sm:w-auto sm:min-w-[160px]"
          >
            {availableYears.map(year => (
              <option key={year} value={year}>{year === 'All' ? '📁 All Combined' : `📅 FY ${year}`}</option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="p-3 sm:p-4 mb-6 sm:mb-8 bg-rose-50 text-rose-600 rounded-xl sm:rounded-2xl text-xs sm:text-sm font-bold flex items-center gap-2 sm:gap-3 border border-rose-100 animate-pulse">
            <span className="shrink-0">⚠️</span> <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="flex flex-col items-center justify-center h-64 sm:h-96 text-slate-400">
            <RefreshCcw className="animate-spin mb-3 sm:mb-4 w-6 h-6 sm:w-8 sm:h-8" />
            <p className="font-bold animate-pulse text-sm sm:text-base">Calculating Real-time Analytics...</p>
        </div>
      ) : (
        <div className="space-y-6 sm:space-y-8 animate-in fade-in duration-500">
          {/* KPI GRID - Uses data directly from the filtered backend endpoint */}
          <KPICardGroup stats={kpiData} />

          {/* CHARTS GRID - All charts receive the filtered list */}
          <div className="grid grid-cols-1 gap-4 sm:gap-6 lg:gap-8 lg:grid-cols-2">
            
            <div className="p-4 sm:p-6 md:p-8 bg-white border border-slate-100 shadow-sm rounded-2xl sm:rounded-[2.5rem]">
              <StatusPieChart tenders={filteredTenders} />
            </div>
            
            <div className="p-4 sm:p-6 md:p-8 bg-white border border-slate-100 shadow-sm rounded-2xl sm:rounded-[2.5rem] overflow-x-auto custom-scrollbar">
              <div className="min-w-[400px]">
                <BiddingTrendChart tenders={filteredTenders} />
              </div>
            </div>

            <div className="p-4 sm:p-6 md:p-8 bg-white border border-slate-100 shadow-sm rounded-2xl sm:rounded-[2.5rem] overflow-x-auto custom-scrollbar">
              <div className="min-w-[400px]">
                <ClientBarChart tenders={filteredTenders} />
              </div>
            </div>
            
            <div className="p-4 sm:p-6 md:p-8 bg-white border border-slate-100 shadow-sm rounded-2xl sm:rounded-[2.5rem] overflow-x-auto custom-scrollbar">
              <div className="min-w-[400px]">
                <ClientPerformanceChart tenders={filteredTenders} />
              </div>
            </div>

            {/* ROW 4: Tender Map (Full Width) */}
            <div className="p-4 sm:p-6 md:p-8 bg-white border border-slate-100 shadow-sm rounded-2xl sm:rounded-[2.5rem] col-span-1 lg:col-span-2 h-[400px] sm:h-[500px]">
              <TenderMap tenders={filteredTenders} />
            </div>

          </div>
        </div>
      )}
    </div>
  );
};

export default AnalyticsDashboard;