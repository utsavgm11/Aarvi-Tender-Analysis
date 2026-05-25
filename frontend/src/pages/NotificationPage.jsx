import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { ArrowLeft, Bell, Calendar, AlertCircle, Clock, Globe, MapPin, Edit3, Save, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const NotificationPage = () => {
  const [tenders, setTenders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editData, setEditData] = useState(null);
  const navigate = useNavigate();

 const fetchUpcoming = async () => {
  setLoading(true);
  try {
    const res = await axios.get("http://127.0.0.1:8001/tenders/upcoming-prebid");
    
    // Get today's date in YYYY-MM-DD format for comparison
    const today = new Date().toISOString().split('T')[0];

    // Filter: Only keep tenders where pre_bidding_date is today or in the future
    const filteredTenders = res.data.filter(t => {
      if (!t.pre_bidding_date) return false;
      return t.pre_bidding_date >= today;
    });

    setTenders(filteredTenders);
  } catch (err) {
    console.error("Error fetching notifications:", err);
  } finally {
    setLoading(false);
  }
};
  useEffect(() => { fetchUpcoming(); }, []);

  const openEditModal = (tender) => {
    setEditData({ ...tender });
    setIsModalOpen(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    try {
      await axios.put(`http://127.0.0.1:8001/tenders/${encodeURIComponent(editData.tender_no)}`, editData);
      setIsModalOpen(false);
      fetchUpcoming(); // Refresh list
    } catch (err) {
      alert("Failed to update: " + err.message);
    }
  };

  return (
    <div className="p-4 sm:p-6 md:p-8 max-w-7xl mx-auto h-full overflow-y-auto">
      {/* Header */}
      <div className="flex items-center gap-3 sm:gap-4 mb-6 sm:mb-8">
        <button onClick={() => navigate(-1)} className="p-1.5 sm:p-2 bg-white border border-slate-200 rounded-full hover:bg-slate-50 shadow-sm transition-colors">
          <ArrowLeft className="text-slate-600 w-5 h-5 sm:w-6 sm:h-6" />
        </button>
        <div>
          <h2 className="text-xl sm:text-2xl font-black text-slate-800 flex items-center gap-2">
            <Bell className="text-rose-500 w-5 h-5 sm:w-6 sm:h-6" /> Upcoming Pre-Bids
          </h2>
        </div>
      </div>

      {/* Table Container with Horizontal Scroll */}
      <div className="bg-white rounded-2xl sm:rounded-3xl border border-slate-200 shadow-sm overflow-x-auto custom-scrollbar w-full">
        <table className="w-full text-left min-w-[700px]">
          <thead className="bg-slate-50 border-b border-slate-100">
            <tr>
              <th className="p-4 sm:p-5 text-[10px] sm:text-xs font-bold text-slate-400 uppercase whitespace-nowrap">Client / Tender</th>
              <th className="p-4 sm:p-5 text-[10px] sm:text-xs font-bold text-slate-400 uppercase whitespace-nowrap">Schedule</th>
              <th className="p-4 sm:p-5 text-[10px] sm:text-xs font-bold text-slate-400 uppercase whitespace-nowrap">Mode</th>
              <th className="p-4 sm:p-5 text-[10px] sm:text-xs font-bold text-slate-400 uppercase whitespace-nowrap">Venue / Link</th>
              <th className="p-4 sm:p-5 text-[10px] sm:text-xs font-bold text-slate-400 uppercase whitespace-nowrap">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {tenders.length === 0 && !loading ? (
              <tr>
                <td colSpan="5" className="p-8 text-center text-slate-400 italic">No upcoming pre-bids scheduled.</td>
              </tr>
            ) : (
              tenders.map((t) => (
                <tr key={t.tender_no} className="hover:bg-slate-50 transition-colors">
                  <td className="p-4 sm:p-5">
                    <div className="font-bold text-slate-800 text-sm sm:text-base max-w-[200px] sm:max-w-[250px] truncate" title={t.name_of_client}>{t.name_of_client}</div>
                    <div className="font-mono text-[10px] sm:text-xs text-slate-400 mt-0.5">{t.tender_no}</div>
                  </td>
                  <td className="p-4 sm:p-5">
                    <div className="text-xs sm:text-sm font-bold text-slate-700 whitespace-nowrap">{t.pre_bidding_date}</div>
                    <div className="text-[10px] sm:text-xs text-slate-500 whitespace-nowrap">{t.pre_bid_time || '--:--'}</div>
                  </td>
                  <td className="p-4 sm:p-5">
                    <span className="px-2.5 sm:px-3 py-1 bg-slate-100 rounded-full text-[10px] sm:text-xs font-bold whitespace-nowrap">{t.mode_of_conduct || 'N/A'}</span>
                  </td>
                  <td className="p-4 sm:p-5 text-xs sm:text-sm text-slate-600 max-w-[150px] sm:max-w-[200px] truncate" title={t.platform_or_address}>
                    {t.platform_or_address || 'N/A'}
                  </td>
                  <td className="p-4 sm:p-5">
                    <button onClick={() => openEditModal(t)} className="text-indigo-600 hover:text-indigo-800 p-1.5 sm:p-2 hover:bg-indigo-50 rounded-lg transition-colors">
                      <Edit3 size={18} className="w-4 h-4 sm:w-[18px] sm:h-[18px]" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Edit Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-white rounded-[1.5rem] sm:rounded-3xl w-full max-w-md p-6 sm:p-8 shadow-2xl max-h-[95vh] overflow-y-auto custom-scrollbar animate-in zoom-in-95 duration-200">
            <div className="flex justify-between items-center mb-5 sm:mb-6">
              <h3 className="text-lg sm:text-xl font-black text-slate-800">Edit Details</h3>
              <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-slate-600 transition-colors bg-slate-50 hover:bg-slate-100 p-1.5 rounded-full"><X size={20} /></button>
            </div>
            
            <form onSubmit={handleSave} className="space-y-4">
              {/* Stack vertically on mobile, side-by-side on sm+ screens */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-[10px] sm:text-xs font-bold text-slate-400 uppercase mb-1.5 block">Date</label>
                  <input type="date" value={editData.pre_bidding_date || ''} onChange={e => setEditData({...editData, pre_bidding_date: e.target.value})} className="w-full p-2.5 sm:p-2 border border-slate-200 rounded-xl sm:rounded-lg outline-none focus:ring-2 focus:ring-indigo-500 text-sm sm:text-base" />
                </div>
                <div>
                  <label className="text-[10px] sm:text-xs font-bold text-slate-400 uppercase mb-1.5 block">Time</label>
                  <input type="time" value={editData.pre_bid_time || ''} onChange={e => setEditData({...editData, pre_bid_time: e.target.value})} className="w-full p-2.5 sm:p-2 border border-slate-200 rounded-xl sm:rounded-lg outline-none focus:ring-2 focus:ring-indigo-500 text-sm sm:text-base" />
                </div>
              </div>

              <div>
                <label className="text-[10px] sm:text-xs font-bold text-slate-400 uppercase mb-1.5 block">Mode</label>
                <select value={editData.mode_of_conduct || ''} onChange={e => setEditData({...editData, mode_of_conduct: e.target.value})} className="w-full p-2.5 sm:p-2 border border-slate-200 rounded-xl sm:rounded-lg outline-none focus:ring-2 focus:ring-indigo-500 bg-white text-sm sm:text-base cursor-pointer">
                  <option value="Online">Online</option>
                  <option value="Offline">Offline</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] sm:text-xs font-bold text-slate-400 uppercase mb-1.5 block">Venue / Link</label>
                <textarea value={editData.platform_or_address || ''} onChange={e => setEditData({...editData, platform_or_address: e.target.value})} className="w-full p-3 sm:p-2 border border-slate-200 rounded-xl sm:rounded-lg outline-none focus:ring-2 focus:ring-indigo-500 text-sm sm:text-base resize-none" rows="3" />
              </div>

              <button type="submit" className="w-full bg-indigo-600 text-white font-bold py-3.5 sm:py-3 rounded-xl hover:bg-indigo-700 flex items-center justify-center gap-2 transition-all active:scale-[0.98] mt-2">
                <Save size={18} className="w-[16px] h-[16px] sm:w-[18px] sm:h-[18px]" /> Save Changes
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationPage;