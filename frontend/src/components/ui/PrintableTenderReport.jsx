import React from 'react';

// Formatter to handle bolding and bullet points formally
const renderFormalContent = (text) => {
  if (!text || text === "Not Specified") return <span className="italic text-gray-500">Not Specified</span>;
  
  return text.split('\n').map((line, index) => {
    const isBullet = line.trim().startsWith('•') || line.trim().startsWith('-');
    const cleanLine = line.replace(/^[•-]\s*/, '');
    
    const parts = cleanLine.split(/(\*\*.*?\*\*)/g);
    const formattedLine = parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className="font-bold text-black">{part.slice(2, -2)}</strong>;
      }
      return part;
    });

    return (
      <div key={index} className={`mb-1 ${isBullet ? 'pl-5 pr-2 relative' : 'mt-1.5 mb-1.5 pr-2'}`} style={{ breakInside: 'avoid', pageBreakInside: 'avoid' }}>
        {isBullet && <span className="absolute left-1 top-0 text-black font-bold text-[15px]">•</span>}
        <span className="leading-snug text-left block">{formattedLine}</span>
      </div>
    );
  });
};

const PrintableTenderReport = ({ d, bidDecision }) => {
  const hasHistory = d.historical_competitors && d.historical_competitors !== "Not Specified" && d.historical_competitors !== "No Data";

  return (
    <div id="printable-report" className="bg-white px-8 py-8 font-serif text-black relative" style={{ width: '750px', minHeight: '1123px' , margin: '0 auto', boxSizing: 'border-box'}}>
      
      {/* 🚀 ULTIMATE PRINT LAYOUT DIRECTIVES */}
      <style>{`
        @media print {
          body {
            background: white !important;
            color: black !important;
          }
          /* Ensure our modular rows never fracture horizontally */
          .grid-row {
            break-inside: avoid !important;
            page-break-inside: avoid !important;
            display: flex !important;
          }
          .section-block {
            break-inside: avoid !important;
            page-break-inside: avoid !important;
          }
        }
        /* Fallback for preview screens to preserve layout equality */
        .grid-table {
          display: flex;
          flex-direction: column;
          width: 100%;
          border: 1px solid black;
        }
        .grid-row {
          display: flex;
          width: 100%;
          border-bottom: 1px solid black;
        }
        .grid-row:last-child {
          border-bottom: none;
        }
        .grid-label {
          width: 25%;
          background-color: #f9fafb;
          font-weight: bold;
          padding: 8px 12px;
          border-right: 1px solid black;
          font-size: 13px;
        }
        .grid-value {
          width: 75%;
          padding: 8px 12px;
          font-size: 13px;
          text-align: left;
        }
      `}</style>
      
      {/* --- HEADER (Formal Letterhead) --- */}
      <div className="text-center border-b-2 border-black pb-4 mb-6" style={{ breakInside: 'avoid' }}>
        <h1 className="text-2xl font-extrabold uppercase tracking-widest text-black">AARVI ENCON</h1>
        <h2 className="text-base font-bold uppercase tracking-widest mt-1 border-t border-black pt-1 inline-block">
          Strategic Tender Intelligence Report
        </h2>
        <p className="text-[11px] mt-2 font-mono">DOCUMENT ID: {d.tender_no} | DATE: {new Date().toLocaleDateString()}</p>
      </div>

      {/* --- SECTION 1.0: PROJECT METADATA --- */}
      <div className="section-block mb-6">
        <h3 className="text-lg font-bold mb-2 border-b border-black pb-1 uppercase">1.0 Project Identification</h3>
        <div className="grid-table">
          <div className="grid-row">
            <div className="grid-label">Tender Reference</div>
            <div className="grid-value">{d.tender_no}</div>
          </div>
          <div className="grid-row">
            <div className="grid-label">Client Organization</div>
            <div className="grid-value font-bold text-sm">{d.client_name}</div>
          </div>
          <div className="grid-row">
            <div className="grid-label">Financial Base</div>
            <div className="grid-value">
              <strong>Est. Value:</strong> {d.tender_open_price} &nbsp; | &nbsp; <strong>EMD Amount:</strong> {d.emd}
            </div>
          </div>
          <div className="grid-row">
            <div className="grid-label">Project Description</div>
            <div className="grid-value italic">{d.description}</div>
          </div>
        </div>
      </div>

      {/* --- SECTION 2.0: AI DECISION MATRIX --- */}
      <div className="section-block mb-6">
        <h3 className="text-lg font-bold mb-2 border-b border-black pb-1 uppercase">2.0 Executive Bid Decision</h3>
        <div className="grid-table" style={{ borderWidth: '2px' }}>
          <div className="grid-row">
            <div className="grid-label" style={{ width: '20%', backgroundColor: '#f3f4f6' }}>AI Rec</div>
            <div className="grid-value font-extrabold text-base uppercase tracking-widest" style={{ width: '30%' }}>{bidDecision}</div>
            <div className="grid-label" style={{ width: '20%', backgroundColor: '#f3f4f6' }}>Win Prob</div>
            <div className="grid-value font-bold text-sm" style={{ width: '30%' }}>{d.win_probability}</div>
          </div>
          <div className="grid-row">
            <div className="grid-label" style={{ width: '20%' }}>Profit Forecast</div>
            <div className="grid-value font-bold text-sm" style={{ width: '30%' }}>{d.profit_forecast}</div>
            <div className="grid-label" style={{ width: '20%' }}>PQ Status</div>
            <div className="grid-value font-bold text-sm" style={{ width: '30%' }}>{d.pq_status}</div>
          </div>
        </div>
      </div>

      {/* --- SECTION 3.0: FINANCIAL & TECHNICAL --- */}
      <div className="mb-6">
        <h3 className="text-lg font-bold mb-2 border-b border-black pb-1 uppercase">3.0 Qualification & Scope</h3>
        <div className="grid-table">
          {/* Using grid-row directly guarantees this single block moves down as a unit if it doesn't fit */}
          <div className="grid-row">
            <div className="grid-label">Financial Requirements</div>
            <div className="grid-value">{renderFormalContent(d.financial_qualification)}</div>
          </div>
          <div className="grid-row">
            <div className="grid-label">Technical Experience</div>
            <div className="grid-value">{renderFormalContent(d.technical_qualification)}</div>
          </div>
          <div className="grid-row">
            <div className="grid-label">Scope of Work</div>
            <div className="grid-value">{renderFormalContent(d.scope_of_work)}</div>
          </div>
          <div className="grid-row">
            <div className="grid-label">Manpower Allocation</div>
            <div className="grid-value leading-relaxed">
              <strong>Headcount Breakdown:</strong> <br/>
              {renderFormalContent(d.manpower_count)}
              <div className="mt-2 border-t border-gray-200 pt-1">
                <strong>Shifts:</strong> {d.shift_duty}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* --- SECTION 4.0: COMPLIANCE & RISK --- */}
      <div className="mb-6">
        <h3 className="text-lg font-bold mb-2 border-b  border-black pb-1 uppercase">4.0 Risk Assessment & Compliance</h3>
        <div className="grid-table">
          <div className="grid-row">
            <div className="grid-label">Mandatory Compliance</div>
            <div className="grid-value">
              <strong className="mb-2 block text-sm">Status: {d.compliance_status}</strong>
              {renderFormalContent(d.mandatory_compliance)}
            </div>
          </div>
          <div className="grid-row">
            <div className="grid-label">Payment Terms</div>
            <div className="grid-value">{renderFormalContent(d.payment_terms)}</div>
          </div>
          <div className="grid-row">
            <div className="grid-label">Penalty & LD Clauses</div>
            <div className="grid-value font-bold">{renderFormalContent(d.penalty_terms)}</div>
          </div>
        </div>
      </div>

      {/* --- SECTION 5.0: HISTORICAL COMPETITOR INTELLIGENCE (DYNAMIC) --- */}
      {hasHistory && (
        <div className="mb-6 section-block">
          <h3 className="text-lg font-bold mb-2 border-b border-black pb-1 uppercase">5.0 Historical Competitor Intelligence</h3>
          <div className="grid-table" style={{ backgroundColor: 'rgba(251, 146, 60, 0.05)' }}>
            <div className="grid-row">
              <div className="grid-label" style={{ backgroundColor: '#f3f4f6' }}>Client Win/Loss Record</div>
              <div className="grid-value font-semibold">{renderFormalContent(d.win_loss_kpi)}</div>
            </div>
            <div className="grid-row">
              <div className="grid-label" style={{ backgroundColor: '#f3f4f6' }}>Client-Specific Competitor History</div>
              <div className="grid-value text-red-900">{renderFormalContent(d.historical_competitors)}</div>
            </div>
          </div>
        </div>
      )}

      {/* --- SECTION 6.0: CONSULTANT ADVICE --- */}
      <div className="section-block">
        <h3 className="text-lg font-bold mb-2 border-b border-black pb-1 uppercase">
          {hasHistory ? "6.0" : "5.0"} Executive Strategic Advice
        </h3>
        <div className="px-4 py-4 border-2 border-black bg-gray-50 text-left text-[13px]">
          {renderFormalContent(d.strategic_advice)}
        </div>
      </div>

      {/* --- FOOTER --- */}
      <div className="mt-8 pt-3 border-t border-black text-center text-[10px] font-mono uppercase tracking-widest section-block">
        <p>*** Strictly Confidential - Internal Use Only - Aarvi Encon AI Engine ***</p>
        <p className="mt-1 text-gray-500">System generated report. Not for external circulation.</p>
      </div>

    </div>
  );
};

export default PrintableTenderReport;