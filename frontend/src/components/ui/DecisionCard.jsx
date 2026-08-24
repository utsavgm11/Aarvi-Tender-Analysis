import React, { useState } from 'react';
import axios from 'axios';
import {
  ShieldCheck, AlertTriangle, TrendingUp, DollarSign,
  Briefcase, FileText, Target, CheckCircle2, XCircle,
  HardHat, Wallet, Users, Loader2, Download, BarChart,
  Clock, Save
} from 'lucide-react';
import html2pdf from 'html2pdf.js';
import PrintableTenderReport from './PrintableTenderReport';

// NEW WORD EXPORT IMPORTS
import { asBlob } from 'html-docx-js-typescript';
import { saveAs } from 'file-saver';

const API_BASE_URL = import.meta.env.VITE_API_URL || "https://attract-appeals-recorded-able.trycloudflare.com";

// --- DATA CLEANER ---
const cleanText = (val) => {
  if (val === undefined || val === null || val === "" || val === "N/A" || val === "Not Specified") {
    return "Not Specified";
  }
  return String(val).trim().replace(/\\n/g, '\n');
};

const DecisionCard = ({ result, progress }) => {
  const data = result?.aarvi_intelligence || result || {};
  
  const [isDownloading, setIsDownloading] = useState(false);
  const [isDownloadingWord, setIsDownloadingWord] = useState(false);
  
  // NEW: Save to Dashboard State
  const [isSaving, setIsSaving] = useState(false);
  
  const d = {
    tender_no: cleanText(data.tender_no),
    client_name: cleanText(data.client_name),
    description: cleanText(data.description),
    due_date: cleanText(data.due_date), // NEW: Extracted Due Date
    bid_decision: cleanText(data.bid_decision),
    pq_status: cleanText(data.pq_status),
    win_probability: cleanText(data.win_probability),
    profit_forecast: cleanText(data.profit_forecast), 
    tender_open_price: cleanText(data.tender_open_price),
    emd: cleanText(data.emd),
    financial_qualification: cleanText(data.financial_qualification),
    technical_qualification: cleanText(data.technical_qualification),
    mandatory_compliance: cleanText(data.mandatory_compliance),
    compliance_status: cleanText(data.compliance_status),
    compliance_reason: cleanText(data.compliance_reason),
    scope_of_work: cleanText(data.scope_of_work),
    manpower_count: cleanText(data.manpower_count),
    manpower_qual: cleanText(data.manpower_qual),
    shift_duty: cleanText(data.shift_duty),
    similar_work: cleanText(data.similar_work),
    payment_terms: cleanText(data.payment_terms),
    penalty_terms: cleanText(data.penalty_terms),
    strategic_advice: cleanText(data.strategic_advice),
    win_loss_kpi: cleanText(data.win_loss_kpi),
    historical_competitors: cleanText(data.historical_competitors)
  };

  const bidDecision = String(d.bid_decision).toUpperCase();
  const isGo = bidDecision.includes("RECOMMENDED") || bidDecision.includes("GO");
  const isReview = bidDecision.includes("CAUTION") || bidDecision.includes("PENDING");
  const isNoGo = bidDecision.includes("NO BID") || bidDecision.includes("FAIL");

  const profitScore = parseInt(d.profit_forecast) || 0;
  const profitColor = profitScore >= 75 ? 'emerald' : profitScore >= 45 ? 'amber' : 'rose';

  const hasCompetitors = d.historical_competitors && 
                         !d.historical_competitors.includes("Not Specified") && 
                         d.historical_competitors.length > 5;

  // --- NEW: Save Tender to Dashboard Logic (No File Upload) ---
  const handleSaveToDashboard = async () => {
    setIsSaving(true);
    try {
      const payload = {
        tender_status: 'Pending',
        name_of_client: d.client_name !== "Not Specified" ? d.client_name.substring(0, 255) : "Unknown Client",
        tender_no: d.tender_no !== "Not Specified" ? d.tender_no.substring(0, 100) : `TND-${Math.floor(Math.random() * 10000)}`,
        due_date: d.due_date !== "Not Specified" ? d.due_date : null,
        description: d.description !== "Not Specified" ? d.description : "",
        emd: d.emd !== "Not Specified" ? d.emd : null,
        financial_year: "2026-2027", 
        tender_open_price: null, // Avoid floating point crashes from text
        quoted_value: 0.0,
        price_status: 'Pending',
        emd_status: 'Pending',
        tender_fee_status: 'Pending',
        project_manager: localStorage.getItem('managerName') || 'Unassigned'
      };

      await axios.post(`${API_BASE_URL}/tenders`, payload);

      alert("✅ AI Summary & Tender successfully saved to the Master Dashboard!");
    } catch (err) {
      console.error(err);
      alert("❌ Failed to save tender. Check backend connection.");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDownloadPDF = () => {
    setIsDownloading(true);
    const element = document.getElementById('printable-report-container');
    const opt = {
      margin:       10,
      filename:     `Aarvi_Tender_Report_${d.tender_no !== "Not Specified" ? d.tender_no : "New"}.pdf`,
      image:        { type: 'jpeg', quality: 0.98 },
      html2canvas:  { scale: 2, useCORS: true },
      jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' }
    };
    html2pdf().set(opt).from(element).save().then(() => setIsDownloading(false));
  };

  const handleDownloadWord = async () => {
    setIsDownloadingWord(true);
    const reportElement = document.getElementById('printable-report'); 
    
    if (!reportElement) {
      alert("Report content not found.");
      setIsDownloadingWord(false);
      return;
    }

    const clone = reportElement.cloneNode(true);

    const fullHtml = `
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="utf-8">
          <style>
            body { font-family: 'Calibri', 'Times New Roman', serif; font-size: 10.5pt; color: #000000; line-height: 1.4; }
            h1 { font-size: 16pt; font-weight: bold; text-align: center; margin-bottom: 2pt; text-transform: uppercase; letter-spacing: 1pt; }
            h2 { font-size: 12pt; font-weight: bold; text-align: center; text-transform: uppercase; margin-top: 2pt; border-top: 1pt solid #000; padding-top: 4pt; display: inline-block;}
            h3 { font-size: 11pt; font-weight: bold; text-transform: uppercase; border-bottom: 1.5pt solid #000000; padding-bottom: 3pt; margin-top: 16pt; margin-bottom: 6pt; }
            .grid-table { width: 100%; border-collapse: collapse; margin-bottom: 12pt; border: 1pt solid #000000; }
            .grid-row { display: table-row; }
            .grid-label { display: table-cell; width: 25%; background-color: #f3f4f6; font-weight: bold; padding: 6pt 8pt; border: 1pt solid #000000; vertical-align: top; font-size: 10pt; }
            .grid-value { display: table-cell; width: 75%; padding: 6pt 8pt; border: 1pt solid #000000; vertical-align: top; font-size: 10pt; }
            .font-bold, strong { font-weight: bold; }
            .italic { font-style: italic; }
            .text-center { text-align: center; }
            .text-[10px] { font-size: 8pt; }
            .text-gray-500 { color: #6b7280; }
            div { margin-bottom: 4pt; }
          </style>
        </head>
        <body>
          ${clone.innerHTML}
        </body>
      </html>
    `;

   try {
      const docxBuffer = await asBlob(fullHtml, {
        orientation: 'portrait',
        margins: { top: 720, right: 720, bottom: 720, left: 720 }
      });
      saveAs(docxBuffer, `Aarvi_Tender_Report_${d.tender_no !== "Not Specified" ? d.tender_no : "New"}.docx`);
    } catch (error) {
      console.error("Word generation failed:", error);
    } finally {
      setIsDownloadingWord(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto my-4 sm:my-8 px-3 sm:px-6 lg:px-8 font-sans space-y-4 sm:space-y-8 relative overflow-hidden text-left">
      
      {progress && progress.total > 0 && progress.current < progress.total && (
        <div className="bg-indigo-50 border border-indigo-100 p-4 sm:p-5 rounded-xl sm:rounded-2xl flex flex-col md:flex-row items-center justify-between gap-3 sm:gap-4 shadow-sm animate-pulse">
          <div className="flex items-center gap-2 sm:gap-3">
            <Loader2 className="animate-spin text-indigo-600" size={20} />
            <span className="text-indigo-900 font-bold text-xs sm:text-sm tracking-wide uppercase text-center sm:text-left">AI Engine Scanning Document...</span>
          </div>
          <div className="flex-1 w-full md:max-w-md mx-0 md:mx-4">
            <div className="h-2.5 bg-indigo-200 rounded-full overflow-hidden">
              <div 
                className="bg-indigo-600 h-full transition-all duration-300 ease-out" 
                style={{ width: `${(progress.current / progress.total) * 100}%` }}
              ></div>
            </div>
          </div>
          <span className="text-indigo-700 font-black text-xs sm:text-sm">
            Pages Scanned ({progress.current}/{progress.total})
          </span>
        </div>
      )}

      {/* HEADER & ACTION BAR */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4 sm:gap-6 bg-white p-5 sm:p-8 rounded-xl sm:rounded-2xl border border-slate-100 shadow-sm text-left">
        <div className="flex-1 w-full">
          <span className="bg-slate-900 text-white px-3 py-1 rounded text-[10px] font-bold uppercase tracking-widest inline-block">
            {d.tender_no !== "Not Specified" ? d.tender_no : "TENDER ID PENDING"}
          </span>
          <h1 className="text-xl sm:text-2xl md:text-3xl font-extrabold text-slate-900 mt-3 leading-tight">{d.client_name !== "Not Specified" ? d.client_name : "Unknown Client"}</h1>
          <p className="text-sm sm:text-base text-slate-500 mt-1">{d.description !== "Not Specified" ? d.description : "Project Analysis Summary"}</p>
        </div>
        
        <div className="flex flex-wrap items-center justify-start md:justify-end gap-2 sm:gap-3 w-full md:w-auto mt-4 md:mt-0">
          
          {/* STATUS BADGE */}
          <div className={`px-4 py-2 rounded-lg font-bold text-sm border flex items-center justify-center gap-2 h-[40px] w-full sm:w-auto ${
            isGo ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
            isReview ? 'bg-amber-50 text-amber-700 border-amber-200' :
            isNoGo ? 'bg-rose-50 text-rose-700 border-rose-200' : 'bg-slate-50 text-slate-700 border-slate-200'
          }`}>
            {isGo ? <CheckCircle2 size={16} /> : isReview ? <AlertTriangle size={16} /> : <XCircle size={16} />}
            <span className="truncate">{bidDecision}</span>
          </div>

          {/* PDF DOWNLOAD BUTTON */}
          <button 
            onClick={handleDownloadPDF}
            disabled={isDownloading}
            className="flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-bold shadow-sm transition-all active:scale-95 disabled:opacity-70 disabled:cursor-not-allowed text-sm h-[40px] w-full sm:w-auto"
          >
            {isDownloading ? <Loader2 className="animate-spin" size={16} /> : <Download size={16} />}
            {isDownloading ? 'PDF...' : 'PDF'}
          </button>

          {/* WORD DOWNLOAD BUTTON */}
          <button 
            onClick={handleDownloadWord}
            disabled={isDownloadingWord}
            className="flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-bold shadow-sm transition-all active:scale-95 disabled:opacity-70 disabled:cursor-not-allowed text-sm h-[40px] w-full sm:w-auto"
          >
            {isDownloadingWord ? <Loader2 className="animate-spin" size={16} /> : <FileText size={16} />}
            {isDownloadingWord ? 'Word...' : 'Word'}
          </button>

          {/* SAVE TO DASHBOARD BUTTON */}
          <button 
            onClick={handleSaveToDashboard}
            disabled={isSaving}
            className="flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg font-bold shadow-sm transition-all active:scale-95 disabled:opacity-70 disabled:cursor-not-allowed text-sm h-[40px] w-full sm:w-auto"
          >
            {isSaving ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
            {isSaving ? 'Saving...' : 'Save Tender'}
          </button>

        </div>
      </div>

      {/* --- KPI STRIP GRID --- */}
      <div className="flex flex-col gap-3 sm:gap-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-5">
          <KpiCard title="PQ Status" val={d.pq_status} icon={<ShieldCheck size={18}/>} color={d.pq_status === 'Pass' ? 'emerald' : d.pq_status === 'Pending Review' ? 'amber' : 'rose'} />
          <KpiCard title="Due Date" val={d.due_date} icon={<Clock size={18}/>} color="amber" />
          <KpiCard title="Win Probability" val={d.win_probability} icon={<Target size={18}/>} color="blue" />
          <KpiCard title="Profit Score" val={d.profit_forecast} icon={<TrendingUp size={18}/>} color={profitColor} />
        </div>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-5">
          <KpiCard title="Win/Loss History" val={d.win_loss_kpi} icon={<BarChart size={18}/>} color="indigo" />
          <KpiCard title="Tender Value" val={d.tender_open_price} icon={<Wallet size={18}/>} color="slate" />
          <KpiCard title="EMD Amount" val={d.emd} icon={<FileText size={18}/>} color="slate" />
        </div>
      </div>

      <div className="bg-white p-5 sm:p-8 rounded-xl sm:rounded-2xl border border-slate-100 shadow-sm text-left">
        <h2 className="text-xs sm:text-sm font-bold text-slate-800 uppercase tracking-widest mb-4 sm:mb-6">Qualification Criteria Summary</h2>
        <div className="grid md:grid-cols-2 gap-4 sm:gap-5 mb-4 sm:mb-5">
          <QualItem title="Financial Qualification (Turnover / Net Worth / PBG)" icon={<DollarSign size={16} />} req={d.financial_qualification} isRisk={d.financial_qualification === "Not Specified"} />
          <QualItem title="Technical Qualification (Experience / Similar Work)" icon={<Briefcase size={16} />} req={d.technical_qualification} isRisk={d.technical_qualification === "Not Specified"} />
        </div>
        <div className="grid grid-cols-1">
          <QualItem title="Mandatory Compliance & Statutory Rules" icon={<ShieldCheck size={16} />} req={d.mandatory_compliance} isRisk={d.compliance_status === "Fail"} />
        </div>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5 text-left">
        <DetailCard title="Scope of Work" icon={<Briefcase size={16}/>} content={d.scope_of_work} />
        <DetailCard title="Manpower Details" icon={<Users size={16}/>} content={`**Count:** ${d.manpower_count}\n**Quals:** ${d.manpower_qual}\n**Shift:** ${d.shift_duty}`} />
        <DetailCard title="Similar Work Extracted" icon={<HardHat size={16}/>} content={d.similar_work} isRisk={d.similar_work === "Not Specified"} />
      </div>

      <div className="grid md:grid-cols-2 gap-4 sm:gap-5 text-left">
        <DetailCard title="Payment Terms" icon={<DollarSign size={16}/>} content={d.payment_terms} />
        <DetailCard title="Penalty & Risk Clauses" icon={<AlertTriangle size={16}/>} content={d.penalty_terms} isRisk />
      </div>

      {/* --- PROFESSIONAL CORPORATE HISTORICAL COMPETITOR SECTION --- */}
      {hasCompetitors && (
        <div className="bg-white p-5 sm:p-8 rounded-xl sm:rounded-2xl border border-slate-200 border-l-[6px] border-l-slate-800 shadow-sm relative overflow-hidden text-left">
          <div className="absolute top-0 right-0 p-4 opacity-[0.03]">
            <Users size={120} />
          </div>
          <h3 className="font-extrabold mb-3 sm:mb-4 flex items-center gap-2 text-lg sm:text-xl text-slate-900 relative z-10">
            <Users size={20} className="text-slate-700 sm:w-6 sm:h-6" /> 
            Historical Competitors & L1 Threats
          </h3>
          <div className="text-slate-700 text-xs sm:text-sm leading-relaxed space-y-2 relative z-10 font-medium text-left">
            {renderFormattedContent(d.historical_competitors)}
          </div>
        </div>
      )}

      <div className={`p-5 sm:p-8 rounded-xl sm:rounded-2xl border shadow-sm text-left ${isNoGo ? 'bg-rose-50 border-rose-100' : isReview ? 'bg-amber-50 border-amber-100' : 'bg-indigo-50 border-indigo-100'}`}>
        <h3 className={`font-bold mb-3 sm:mb-4 flex items-center gap-2 text-base sm:text-lg ${isNoGo ? 'text-rose-900' : isReview ? 'text-amber-900' : 'text-indigo-900'}`}>
          <TrendingUp size={20} className={`sm:w-[22px] sm:h-[22px] ${isNoGo ? 'text-rose-600' : isReview ? 'text-amber-600' : 'text-indigo-600'}`} /> 
          Executive Strategic Advice
        </h3>
        <div className="text-slate-800 text-xs sm:text-sm leading-relaxed space-y-2 text-left">
          {renderFormattedContent(d.strategic_advice)}
        </div>
      </div>

      <div style={{ position: 'absolute', top: '-9999px', left: '-9999px' }}>
        <div id="printable-report-container">
          <PrintableTenderReport d={d} bidDecision={bidDecision} />
        </div>
      </div>
    </div>
  );
};

// --- SUB-COMPONENTS ---

const KpiCard = ({ title, val, icon, color }) => {
  const map = { 
    emerald: 'bg-emerald-50 text-emerald-600', 
    blue: 'bg-blue-50 text-blue-600', 
    amber: 'bg-amber-50 text-amber-600', 
    rose: 'bg-rose-50 text-rose-600',
    slate: 'bg-slate-100 text-slate-600',
    indigo: 'bg-indigo-50 text-indigo-600'
  };
  const lines = String(val).split('\n');

  return (
    <div className="bg-white p-4 sm:p-5 rounded-xl border border-slate-100 flex items-center gap-3 sm:gap-4 hover:shadow-md transition-all text-left">
      <div className={`p-2.5 rounded-lg shrink-0 ${map[color] || map.slate}`}>{icon}</div>
      <div className="flex-1 min-w-0">
        <p className="text-[9px] sm:text-[10px] uppercase font-bold text-slate-400 mb-0.5">{title}</p>
        {lines.map((line, index) => (
          <p key={index} className={`${index === 0 ? 'font-bold text-slate-800 text-xs sm:text-sm truncate' : 'text-[10px] sm:text-[11px] font-semibold text-slate-500 truncate mt-0.5'}`} title={line}>
            {line}
          </p>
        ))}
      </div>
    </div>
  );
};

const QualItem = ({ title, icon, req, isRisk }) => (
  <div className={`p-4 sm:p-6 rounded-xl border flex flex-col min-h-[220px] sm:h-[280px] text-left ${isRisk ? 'border-amber-200 bg-amber-50/50' : 'border-slate-100 bg-slate-50/50'}`}>
    <div className="flex flex-col sm:flex-row sm:justify-between items-start sm:items-center gap-2 sm:gap-0 mb-3 sm:mb-4 pb-3 border-b border-slate-200/60 shrink-0 text-left">
      <h4 className="font-bold text-xs sm:text-sm text-slate-800 flex items-center gap-2">
        <span className={`shrink-0 ${isRisk ? 'text-amber-500' : 'text-slate-400'}`}>{icon}</span>
        <span className="leading-snug">{title}</span>
      </h4>
      {isRisk && <span className="text-[9px] sm:text-[10px] px-2 py-0.5 rounded-full font-bold bg-amber-100 text-amber-700 border border-amber-200 shrink-0">Review Required</span>}
    </div>
    <div className="text-[11px] sm:text-xs text-slate-600 leading-relaxed overflow-y-auto pr-1 sm:pr-2 sleek-scroll flex-1 text-left">
      {renderFormattedContent(req)}
    </div>
  </div>
);

const renderFormattedContent = (text) => {
  if (!text || text === "Not Specified") return <span className="italic text-slate-400">Not Specified</span>;
  return text.split('\n').map((line, index) => {
    const isBullet = line.trim().startsWith('•') || line.trim().startsWith('-');
    const cleanLine = line.replace(/^[•-]\s*/, '');
    const parts = cleanLine.split(/(\*\*.*?\*\*)/g);
    const formattedLine = parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) return <strong key={i} className="text-slate-900">{part.slice(2, -2)}</strong>;
      return part;
    });
    return (
      <div key={index} className={`mb-1.5 text-left ${isBullet ? 'pl-3 sm:pl-4 flex' : 'mt-2 sm:mt-3 mb-1.5 sm:mb-2'}`}>
        {isBullet && <span className="mr-1.5 sm:mr-2 text-indigo-400 font-bold">•</span>}
        <span className="leading-relaxed text-left">{formattedLine}</span>
      </div>
    );
  });
};

const DetailCard = ({ title, icon, content, isRisk = false }) => (
  <div className={`bg-white p-4 sm:p-6 rounded-xl sm:rounded-2xl border shadow-sm min-h-[200px] sm:h-[250px] flex flex-col transition-all hover:shadow-md sm:hover:shadow-lg hover:-translate-y-0.5 sm:hover:-translate-y-1 text-left ${isRisk ? 'border-rose-200' : 'border-slate-100'}`}>
    <h4 className="flex items-center gap-2 font-bold text-slate-800 text-xs sm:text-sm mb-3 sm:mb-4 border-b pb-2 border-slate-50 shrink-0">
      <span className={isRisk ? 'text-rose-500' : 'text-slate-400'}>{icon}</span> {title}
    </h4>
    <div className="text-slate-600 text-[11px] sm:text-xs overflow-y-auto pr-1 sm:pr-2 sleek-scroll flex-1 text-left">
      {renderFormattedContent(content)}
    </div>
  </div>
);

export default DecisionCard;