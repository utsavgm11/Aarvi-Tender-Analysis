import React from 'react';
import { Hash, Percent, IndianRupee, Briefcase } from 'lucide-react';

const KPICard = ({ title, value, icon, color }) => {
  return (
    <div className={`p-6 bg-white rounded-[2rem] shadow-sm border-l-4 ${color} hover:shadow-md transition-all h-full flex flex-col justify-center`}>
      <div className="flex justify-between items-start">
        <div>
          <p className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest mb-1">{title}</p>
          <h3 className="text-2xl font-black text-slate-800 tracking-tight">{value}</h3>
        </div>
        <div className="p-2 bg-slate-50 rounded-xl text-slate-400">
          {icon}
        </div>
      </div>
    </div>
  );
};

const KPICardGroup = ({ stats = {} }) => {
  // Business Logic: Revenue is strictly formatted in Crores (Cr)
  // 1 Crore = 10,000,000
  const formatRevenue = (val) => {
    if (!val || val === 0) return "₹0.00 Cr";
    return `₹${(val / 10000000).toFixed(2)} Cr`;
  };

  return (
    // inside KPICardGroup.jsx
<div className="grid grid-cols-1 gap-6 mb-8 md:grid-cols-2 lg:grid-cols-4">
  <KPICard 
    title="Total Funnel" 
    value={stats.total_count || 0} 
    color="border-slate-300" 
    icon={<Hash size={18}/>} 
  />

   <KPICard 
  title="Active Pipeline" 
  value={stats.active_pipeline || 0} 
  color="border-blue-500" 
  icon={<Briefcase size={18} className="text-blue-500" />} 
/>
  
  <KPICard 
    title="Win Rate" 
    value={`${stats.win_rate || 0}%`} 
    color="border-emerald-500" 
    icon={<Percent size={18}/>} 
  />
  
  <KPICard 
    title="Revenue (Won)" 
    value={formatRevenue(stats.total_won_value)} 
    color="border-indigo-500" 
    icon={<IndianRupee size={18}/>} 
  />
  
 
</div>
  );
};

export default KPICardGroup;