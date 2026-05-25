import React, { useState, useEffect, useRef } from 'react';
import { Plus, Trash2, Save, TrendingDown } from 'lucide-react';

const PostBidForm = ({ tenderId, isOpen, onClose, onSubmitSuccess }) => {
  const [aarviRank, setAarviRank] = useState('');
  const [reasonForLoss, setReasonForLoss] = useState('');
  const [remarks, setRemarks] = useState('');
  const [competitors, setCompetitors] = useState([
    { rank: 'L1', company: '', amount: '', percent_diff: '' }
  ]);

  const modalRef = useRef(null);

  // --- ESC KEYBOARD INTERCEPTOR ---
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // --- CLICK OUTSIDE BACKDROP DETECTION ---
  const handleBackdropClick = (e) => {
    if (modalRef.current && !modalRef.current.contains(e.target)) {
      onClose();
    }
  };

  // Automatically track and sort Aarvi Encon placement row
  useEffect(() => {
    if (aarviRank && aarviRank !== 'Disqualified' && aarviRank !== 'L5+') {
      const exists = competitors.some(c => c.rank === aarviRank);
      if (!exists) {
        const filtered = competitors.filter(c => c.company.toLowerCase() !== 'aarvi encon');
        setCompetitors([
          ...filtered,
          { rank: aarviRank, company: 'Aarvi Encon', amount: '', percent_diff: '' }
        ].sort((a, b) => a.rank.localeCompare(b.rank)));
      }
    }
  }, [aarviRank]);

  const handleCompetitorChange = (index, field, value) => {
    const updated = [...competitors];
    updated[index][field] = value;
    setCompetitors(updated);
  };

  const addCompetitorRow = () => {
    if (competitors.length >= 5) {
      alert("You can record up to L5 leaderboard data matrix.");
      return;
    }
    const nextRank = `L${competitors.length + 1}`;
    setCompetitors([...competitors, { rank: nextRank, company: '', amount: '', percent_diff: '' }]);
  };

  const removeCompetitorRow = (index) => {
    if (competitors[index].company === 'Aarvi Encon') {
      alert("To alter Aarvi Encon positioning, please adjust the status rank selector directly.");
      return;
    }
    setCompetitors(competitors.filter((_, i) => i !== index));
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    const formattedCompetitors = competitors.map(c => ({
      rank: c.rank,
      company: c.company || "Unknown Competitor",
      amount: c.amount ? parseFloat(c.amount) : 0.00,
      percent_diff: c.percent_diff ? parseFloat(c.percent_diff) : 0.00
    }));

    const payload = {
      aarvi_rank: aarviRank,
      reason_for_loss: reasonForLoss,
      post_bid_remarks: remarks || "No Remarks",
      competitors: formattedCompetitors
    };

    if (onSubmitSuccess) {
      onSubmitSuccess(payload);
    }
  };

  if (!isOpen) return null;

  return (
    <div 
      onClick={handleBackdropClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-3 sm:p-4 animate-in fade-in duration-200"
    >
      <div 
        ref={modalRef}
        className="bg-white p-4 sm:p-6 rounded-2xl max-w-3xl w-full mx-auto font-sans text-slate-800 shadow-xl border border-slate-100 animate-in zoom-in-95 duration-200 relative max-h-[95vh] flex flex-col"
      >
        {/* Absolute Close Top Button Icon */}
        <button 
          onClick={onClose}
          className="absolute top-3 right-3 sm:top-4 sm:right-4 text-slate-400 hover:text-slate-600 font-bold transition-all p-2 text-sm z-10 bg-white rounded-full sm:bg-transparent shadow-sm sm:shadow-none"
        >
          ✕
        </button>

        {/* Header */}
        <div className="border-b border-slate-100 pb-3 mb-4 sm:mb-5 shrink-0 pr-8">
          <h2 className="text-lg sm:text-xl font-black text-slate-900 flex items-center gap-2">
            <TrendingDown className="text-rose-500 shrink-0" size={22} />
            <span className="truncate">Log Full Bid Leaderboard (L1 - L5)</span>
          </h2>
          <p className="text-[10px] sm:text-xs text-slate-500 mt-1 truncate">
            Tender Reference ID: <span className="font-mono font-bold text-slate-800">{tenderId}</span>
          </p>
        </div>

        {/* Scrollable Form Container */}
        <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-5 overflow-y-auto custom-scrollbar pr-1 pb-1">
          {/* Core Status Dropdowns */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
            <div>
              <label className="block text-[10px] sm:text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">
                Aarvi's Final Position
              </label>
              <select 
                value={aarviRank} 
                onChange={(e) => setAarviRank(e.target.value)}
                required
                className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none text-xs sm:text-sm font-semibold"
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
              <label className="block text-[10px] sm:text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">
                Primary Reason for Loss
              </label>
              <select 
                value={reasonForLoss} 
                onChange={(e) => setReasonForLoss(e.target.value)}
                required
                className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none text-xs sm:text-sm font-semibold"
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

          {/* Dynamic L1-L5 Array Grid Matrix */}
          <div>
            <div className="flex justify-between items-center mb-2 sm:mb-3">
              <label className="block text-[10px] sm:text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                Bidding Leaderboard Matrix
              </label>
              <button
                type="button"
                onClick={addCompetitorRow}
                className="flex items-center gap-1 text-[10px] sm:text-xs font-bold text-indigo-600 bg-indigo-50 hover:bg-indigo-100 px-2 sm:px-2.5 py-1.5 rounded-lg transition-all"
              >
                <Plus size={14} /> <span className="hidden sm:inline">Add Position Row</span><span className="sm:hidden">Add</span>
              </button>
            </div>

            <div className="space-y-3 sm:space-y-2 max-h-[40vh] sm:max-h-[250px] overflow-y-auto pr-1">
              {competitors.map((row, index) => (
                <div key={index} className="grid grid-cols-2 sm:grid-cols-12 gap-2 items-center bg-slate-50 p-3 sm:p-2 rounded-xl border border-slate-200/60">
                  
                  <div className="col-span-1 sm:col-span-2 order-1 sm:order-none">
                    <select
                      value={row.rank}
                      onChange={(e) => handleCompetitorChange(index, 'rank', e.target.value)}
                      className="w-full p-1.5 sm:p-2 bg-white border rounded-lg text-xs font-bold sm:text-center outline-none"
                    >
                      <option value="L1">L1</option>
                      <option value="L2">L2</option>
                      <option value="L3">L3</option>
                      <option value="L4">L4</option>
                      <option value="L5">L5</option>
                    </select>
                  </div>

                  <div className="col-span-2 sm:col-span-4 relative order-3 sm:order-none">
                    <input
                      type="text"
                      value={row.company}
                      disabled={row.company === 'Aarvi Encon'}
                      onChange={(e) => handleCompetitorChange(index, 'company', e.target.value)}
                      placeholder={row.rank === 'L1' ? "Winning Bidder Name" : "Company Name"}
                      required
                      className="w-full p-2 sm:p-1.5 pl-3 sm:pl-2 bg-white border rounded-lg text-xs outline-none disabled:bg-indigo-50 disabled:text-indigo-800 disabled:font-bold"
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

                  <div className="col-span-1 sm:col-span-1 flex justify-end sm:justify-center order-2 sm:order-none">
                    <button
                      type="button"
                      onClick={() => removeCompetitorRow(index)}
                      className="text-slate-400 hover:text-rose-500 transition-colors p-1.5 bg-white sm:bg-transparent border sm:border-none rounded-lg sm:rounded-none shadow-sm sm:shadow-none"
                    >
                      <Trash2 size={16} className="sm:w-[14px] sm:h-[14px]" />
                    </button>
                  </div>

                </div>
              ))}
            </div>
          </div>

          {/* Remarks */}
          <div>
            <label className="block text-[10px] sm:text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5 mt-2 sm:mt-0">
              Strategy Notes / Management Remarks
            </label>
            <textarea
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              rows="2"
              placeholder="Type any internal operational notes here..."
              className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none text-xs resize-none"
            ></textarea>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col-reverse sm:flex-row justify-end gap-2 sm:gap-3 pt-4 sm:pt-3 border-t border-slate-50 shrink-0 mt-2">
            <button 
              type="button" 
              onClick={onClose} 
              className="w-full sm:w-auto px-4 py-2.5 sm:py-2 text-xs font-bold text-slate-500 hover:bg-slate-100 bg-slate-50 sm:bg-transparent border sm:border-none rounded-xl transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="w-full sm:w-auto flex justify-center items-center gap-1.5 bg-slate-900 hover:bg-slate-800 text-white px-5 py-2.5 sm:py-2 rounded-xl text-xs font-bold transition-all shadow-sm"
            >
              <Save size={14} /> Save Leaderboard
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default PostBidForm;