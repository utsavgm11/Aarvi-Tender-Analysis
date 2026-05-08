import React from 'react';
import {
  ShieldCheck, AlertTriangle, TrendingUp, DollarSign,
  Briefcase, FileText, Target, CheckCircle2, XCircle,
  HardHat, Wallet, Users, Loader2
} from 'lucide-react';

// --- DATA CLEANER ---
const cleanText = (val) => {
  if (val === undefined || val === null || val === "" || val === "N/A" || val === "Not Specified") {
    return "Not Specified";
  }
  return String(val).trim().replace(/\\n/g, '\n');
};

// Added 'progress' prop to handle real-time scanning updates
const DecisionCard = ({ result, progress }) => {
  
  const data = result?.aarvi_intelligence || result || {};
  
  // --- EXPLICIT MAPPING FOR NEW AI LOGIC ---
  const d = {
    tender_no: cleanText(data.tender_no),
    client_name: cleanText(data.client_name),
    description: cleanText(data.description),
    bid_decision: cleanText(data.bid_decision),
    pq_status: cleanText(data.pq_status),
    win_probability: cleanText(data.win_probability),
    profit_forecast: cleanText(data.profit_forecast), // Now returns "85 / 100"
    tender_open_price: cleanText(data.tender_open_price),
    emd: cleanText(data.emd),
    
    // NEW COMBINED KEYS
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
    strategic_advice: cleanText(data.strategic_advice)
  };

  const bidDecision = String(d.bid_decision).toUpperCase();
  const isGo = bidDecision.includes("RECOMMENDED");
  const isReview = bidDecision.includes("CAUTION") || bidDecision.includes("PENDING");
  const isNoGo = bidDecision.includes("NO BID");

  // Calculate Profit Score Color
  const profitScore = parseInt(d.profit_forecast) || 0;
  const profitColor = profitScore >= 75 ? 'emerald' : profitScore >= 45 ? 'amber' : 'rose';

  return (
    <div className="max-w-7xl mx-auto my-8 font-sans space-y-8">
      
      {/* --- LIVE PROGRESS BAR --- */}
      {/* Pass { current: 45, total: 200 } to the progress prop to trigger this */}
      {progress && progress.total > 0 && progress.current < progress.total && (
        <div className="bg-indigo-50 border border-indigo-100 p-5 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-4 shadow-sm animate-pulse">
          <div className="flex items-center gap-3">
            <Loader2 className="animate-spin text-indigo-600" size={20} />
            <span className="text-indigo-900 font-bold text-sm tracking-wide uppercase">AI Engine Scanning Document...</span>
          </div>
          <div className="flex-1 w-full md:max-w-md mx-4">
            <div className="h-2.5 bg-indigo-200 rounded-full overflow-hidden">
              <div 
                className="bg-indigo-600 h-full transition-all duration-300 ease-out" 
                style={{ width: `${(progress.current / progress.total) * 100}%` }}
              ></div>
            </div>
          </div>
          <span className="text-indigo-700 font-black text-sm">
            Pages Scanned ({progress.current}/{progress.total})
          </span>
        </div>
      )}

      {/* --- HEADER --- */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 bg-white p-8 rounded-2xl border border-slate-100 shadow-sm">
        <div>
          <span className="bg-slate-900 text-white px-3 py-1 rounded text-[10px] font-bold uppercase tracking-widest">
            {d.tender_no !== "Not Specified" ? d.tender_no : "TENDER ID PENDING"}
          </span>
          <h1 className="text-3xl font-extrabold text-slate-900 mt-3">{d.client_name !== "Not Specified" ? d.client_name : "Unknown Client"}</h1>
          <p className="text-slate-500 mt-1">{d.description !== "Not Specified" ? d.description : "Project Analysis Summary"}</p>
        </div>
        
        <div className={`px-6 py-3 rounded-xl font-bold text-sm border flex items-center gap-2 ${
          isGo ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
          isReview ? 'bg-amber-50 text-amber-700 border-amber-200' :
          isNoGo ? 'bg-rose-50 text-rose-700 border-rose-200' : 'bg-slate-50 text-slate-700 border-slate-200'
        }`}>
          {isGo ? <CheckCircle2 size={18} /> : isReview ? <AlertTriangle size={18} /> : <XCircle size={18} />}
          {bidDecision}
        </div>
      </div>

      {/* --- KPI STRIP --- */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-5">
        <KpiCard title="PQ Status" val={d.pq_status} icon={<ShieldCheck size={18}/>} color={d.pq_status === 'Pass' ? 'emerald' : d.pq_status === 'Pending Review' ? 'amber' : 'rose'} />
        <KpiCard title="Win Probability" val={d.win_probability} icon={<Target size={18}/>} color="blue" />
        <KpiCard title="Profit Score" val={d.profit_forecast} icon={<TrendingUp size={18}/>} color={profitColor} />
        <KpiCard title="Tender Value" val={d.tender_open_price} icon={<Wallet size={18}/>} color="slate" />
        <KpiCard title="EMD" val={d.emd} icon={<FileText size={18}/>} color="slate" />
      </div>

      {/* --- UNIFIED QUALIFICATION SUMMARY (2-COLUMN) --- */}
      <div className="bg-white p-8 rounded-2xl border border-slate-100 shadow-sm">
        <h2 className="text-sm font-bold text-slate-800 uppercase tracking-widest mb-6">Qualification Criteria Summary</h2>
        
        <div className="grid md:grid-cols-2 gap-5 mb-5">
          <QualItem 
            title="Financial Qualification (Turnover / Net Worth / PBG)" 
            icon={<DollarSign size={16} />}
            req={d.financial_qualification} 
            isRisk={d.financial_qualification === "Not Specified"}
          />
          <QualItem 
            title="Technical Qualification (Experience / Similar Work)" 
            icon={<Briefcase size={16} />}
            req={d.technical_qualification} 
            isRisk={d.technical_qualification === "Not Specified"}
          />
        </div>

        <div className="grid grid-cols-1">
          <QualItem 
            title="Mandatory Compliance & Statutory Rules" 
            icon={<ShieldCheck size={16} />}
            req={d.mandatory_compliance} 
            isRisk={d.compliance_status === "Fail"} 
          />
        </div>
      </div>

      {/* --- OPERATIONAL DETAILS GRID --- */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
        <DetailCard title="Scope of Work" icon={<Briefcase size={16}/>} content={d.scope_of_work} />
        <DetailCard title="Manpower Details" icon={<Users size={16}/>} content={`**Count:** ${d.manpower_count}\n**Quals:** ${d.manpower_qual}\n**Shift:** ${d.shift_duty}`} />
        <DetailCard title="Similar Work Extracted" icon={<HardHat size={16}/>} content={d.similar_work} isRisk={d.similar_work === "Not Specified"} />
      </div>

      {/* --- FINANCIAL & RISK --- */}
      <div className="grid md:grid-cols-2 gap-5">
        <DetailCard title="Payment Terms" icon={<DollarSign size={16}/>} content={d.payment_terms} />
        <DetailCard title="Penalty & Risk Clauses" icon={<AlertTriangle size={16}/>} content={d.penalty_terms} isRisk />
      </div>

      {/* --- NEW: ADVANCED STRATEGIC ADVICE SECTION --- */}
      <div className={`p-8 rounded-2xl border shadow-sm ${isNoGo ? 'bg-rose-50 border-rose-100' : isReview ? 'bg-amber-50 border-amber-100' : 'bg-indigo-50 border-indigo-100'}`}>
        <h3 className={`font-bold mb-4 flex items-center gap-2 text-lg ${isNoGo ? 'text-rose-900' : isReview ? 'text-amber-900' : 'text-indigo-900'}`}>
          <TrendingUp size={22} className={isNoGo ? 'text-rose-600' : isReview ? 'text-amber-600' : 'text-indigo-600'} /> 
          Executive Strategic Advice
        </h3>
        <div className="text-slate-700 text-sm leading-relaxed space-y-2">
          {renderFormattedContent(d.strategic_advice)}
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
    slate: 'bg-slate-100 text-slate-600' 
  };
  return (
    <div className="bg-white p-5 rounded-xl border border-slate-100 flex items-center gap-4 hover:shadow-md transition-all">
      <div className={`p-2.5 rounded-lg ${map[color] || map.slate}`}>{icon}</div>
      <div>
        <p className="text-[10px] uppercase font-bold text-slate-400">{title}</p>
        <p className="font-bold text-slate-800 line-clamp-1" title={val}>{val}</p>
      </div>
    </div>
  );
};

// Updated QualItem for scrollable, equal height 2-column layout
const QualItem = ({ title, icon, req, isRisk }) => (
  <div className={`p-6 rounded-xl border flex flex-col h-[280px] ${isRisk ? 'border-amber-200 bg-amber-50/50' : 'border-slate-100 bg-slate-50/50'}`}>
    <div className="flex justify-between items-center mb-4 pb-3 border-b border-slate-200/60">
      <h4 className="font-bold text-sm text-slate-800 flex items-center gap-2">
        <span className={isRisk ? 'text-amber-500' : 'text-slate-400'}>{icon}</span>
        {title}
      </h4>
      {isRisk && <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-amber-100 text-amber-700 border border-amber-200">Review Required</span>}
    </div>
    <div className="text-xs text-slate-600 leading-relaxed overflow-y-auto pr-2 sleek-scroll flex-1">
      {renderFormattedContent(req)}
    </div>
  </div>
);

const renderFormattedContent = (text) => {
  if (!text || text === "Not Specified") return <span className="italic text-slate-400">Not Specified</span>;
  return text.split('\n').map((line, index) => {
    const isBullet = line.trim().startsWith('•') || line.trim().startsWith('-');
    const cleanLine = line.replace(/^[•-]\s*/, '');
    
    // Bold parsing
    const parts = cleanLine.split(/(\*\*.*?\*\*)/g);
    const formattedLine = parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className="text-slate-800">{part.slice(2, -2)}</strong>;
      }
      return part;
    });

    return (
      <div key={index} className={`mb-1.5 ${isBullet ? 'pl-4 flex' : 'mt-3 mb-2'}`}>
        {isBullet && <span className="mr-2 text-indigo-400 font-bold">•</span>}
        <span className="leading-relaxed">{formattedLine}</span>
      </div>
    );
  });
};

const DetailCard = ({ title, icon, content, isRisk = false }) => (
  <div className={`bg-white p-6 rounded-2xl border shadow-sm h-[250px] flex flex-col transition-all hover:shadow-lg hover:-translate-y-1 ${isRisk ? 'border-rose-200' : 'border-slate-100'}`}>
    <h4 className="flex items-center gap-2 font-bold text-slate-800 text-sm mb-4 border-b pb-2 border-slate-50">
      <span className={isRisk ? 'text-rose-500' : 'text-slate-400'}>{icon}</span> {title}
    </h4>
    <div className="text-slate-600 text-xs overflow-y-auto pr-2 sleek-scroll flex-1">
      {renderFormattedContent(content)}
    </div>
  </div>
);

export default DecisionCard;