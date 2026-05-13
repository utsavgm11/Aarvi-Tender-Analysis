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
const API_BASE_URL = import.meta.env.VITE_API_URL || "https://aarvi-tender-api.onrender.com";// ⚠️ REPLACE THIS WITH YOUR ACTUAL LIVE BACKEND LINK

const AnalyticsDashboard = ({ onBack }) => {
  const [tenders, setTenders] = useState([]);
  const [kpiData, setKpiData] = useState({});
  const [selectedYear, setSelectedYear] = useState('All');
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // 1. Unified Fetch Logic
  // ✅ CRITICAL UPDATE: Fetching now includes the Manager Silo logic for both Tenders and KPIs
  const fetchData = useCallback(async (isAutoPoll = false) => {
    if (!isAutoPoll) setIsRefreshing(true);
    try {
      const managerName = localStorage.getItem('managerName');
      
      const queryParams = {};
      if (managerName && managerName !== 'undefined' && managerName !== 'null') {
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
    <div className="min-h-screen p-8 bg-slate-50">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          {onBack && (
            <button onClick={onBack} className="flex items-center gap-1 text-slate-400 hover:text-indigo-600 font-bold mb-2 transition-colors">
              <ArrowLeft size={16} /> Back to Management
            </button>
          )}
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-black text-slate-800 tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-slate-800 to-slate-500">
              Executive Insights
            </h1>
            {isRefreshing && <RefreshCcw size={16} className="animate-spin text-indigo-500" />}
          </div>
        </div>
        
        {/* Financial Year Filter */}
        <div className="flex flex-col items-end">
          <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 mr-2">Fiscal Period</label>
          <select 
            value={selectedYear} 
            onChange={(e) => setSelectedYear(e.target.value)}
            className="p-3 bg-white border border-slate-200 rounded-2xl font-black text-slate-700 shadow-sm outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all cursor-pointer min-w-[160px]"
          >
            {availableYears.map(year => (
              <option key={year} value={year}>{year === 'All' ? '📁 All Combined' : `📅 FY ${year}`}</option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="p-4 mb-8 bg-rose-50 text-rose-600 rounded-2xl text-sm font-bold flex items-center gap-3 border border-rose-100 animate-pulse">
           ⚠️ {error}
        </div>
      )}

      {loading ? (
        <div className="flex flex-col items-center justify-center h-96 text-slate-400">
            <RefreshCcw className="animate-spin mb-4" size={32} />
            <p className="font-bold animate-pulse">Calculating Real-time Analytics...</p>
        </div>
      ) : (
        <div className="space-y-8 animate-in fade-in duration-500">
          {/* KPI GRID - Uses data directly from the filtered backend endpoint */}
          <KPICardGroup stats={kpiData} />

          {/* CHARTS GRID - All charts receive the filtered list */}
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
            
            <div className="p-8 bg-white border border-slate-100 shadow-sm rounded-[2.5rem]">
              <StatusPieChart tenders={filteredTenders} />
            </div>
            
            <div className="p-8 bg-white border border-slate-100 shadow-sm rounded-[2.5rem]">
              <BiddingTrendChart tenders={filteredTenders} />
            </div>

            <div className="p-8 bg-white border border-slate-100 shadow-sm rounded-[2.5rem]">
              <ClientBarChart tenders={filteredTenders} />
            </div>
            
            <div className="p-8 bg-white border border-slate-100 shadow-sm rounded-[2.5rem]">
              <ClientPerformanceChart tenders={filteredTenders} />
            </div>

            {/* ROW 4: Tender Map (Full Width) */}
            <div className="p-8 bg-white border border-slate-100 shadow-sm rounded-[2.5rem] col-span-1 lg:col-span-2 h-[500px]">
              <TenderMap tenders={filteredTenders} />
            </div>

          </div>
        </div>
      )}
    </div>
  );
};

export default AnalyticsDashboard;