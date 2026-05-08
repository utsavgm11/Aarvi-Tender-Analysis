import React, { useMemo } from 'react';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend 
} from 'recharts';
import { format } from 'date-fns';

const BiddingTrendChart = ({ tenders }) => {
  
  const data = useMemo(() => {
    if (!tenders || tenders.length === 0) return [];

    const monthlyData = {};
    
    // 1. Define active participation statuses
    const PARTICIPATED_STATUSES = [
      'tender quoted', 
      'quoted', 
      'tender won', 
      'tender lost', 
      'tender regret'
    ];

    tenders.forEach(t => {
      if (!t.received_date) return;
      
      const status = (t.tender_status || '').toLowerCase().trim();

      // 2. FILTER LOGIC: Only proceed if status is in the participation list
      if (!PARTICIPATED_STATUSES.includes(status)) return;

      const date = new Date(t.received_date);
      if (isNaN(date.getTime())) return; 

      const sortKey = format(date, 'yyyy-MM');
      const displayMonth = format(date, 'MMM yyyy');

      if (!monthlyData[sortKey]) {
        monthlyData[sortKey] = {
          sortKey: sortKey, 
          month: displayMonth, 
          participated: 0, // Changed from 'count' to reflect active participation
          won: 0 
        };
      }

      // 3. Increment Participation Count
      monthlyData[sortKey].participated += 1;
      
      // 4. Increment Won Count
      if (status === 'tender won') {
        monthlyData[sortKey].won += 1;
      }
    });

    return Object.values(monthlyData).sort((a, b) => a.sortKey.localeCompare(b.sortKey));
    
  }, [tenders]); 

  if (!data || data.length === 0) {
    return (
      <div className="h-80 w-full flex flex-col justify-center items-center bg-slate-50 rounded-2xl border border-slate-200 border-dashed">
        <p className="text-slate-400 font-semibold uppercase tracking-widest text-[10px]">Tender Participation vs Wins</p>
        <p className="text-slate-500 mt-2 text-sm">No participation data available</p>
      </div>
    );
  }

  return (
    <div className="h-80 w-full flex flex-col">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xs font-black text-slate-400 uppercase tracking-widest">
          Tender Participation vs Wins
        </h2>
      </div>

      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="colorParticipated" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#6366f1" stopOpacity={0.2} />
              <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="colorWon" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10b981" stopOpacity={0.2} />
              <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
            </linearGradient>
          </defs>
          
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
          
          <XAxis 
            dataKey="month" 
            axisLine={false} 
            tickLine={false} 
            tick={{ fontSize: 11, fill: '#64748b' }} 
            dy={10} 
            minTickGap={25}
          />
          <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#64748b' }} />
          
          <Tooltip 
            contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
            labelStyle={{ fontWeight: '900', color: '#1e293b', marginBottom: '4px' }}
            formatter={(value, name) => [
              `${value} ${value === 1 ? 'tender' : 'tenders'}`, 
              name === 'participated' ? 'Total Participated' : 'Won'
            ]}
          />
          
          <Legend 
            verticalAlign="bottom" 
            height={36} 
            iconType="circle" 
            wrapperStyle={{ fontSize: '12px', paddingTop: '20px' }}
          />

          {/* Purple Line - Participation */}
          <Area 
            type="monotone" 
            dataKey="participated" 
            name="participated"
            stroke="#6366f1" 
            fillOpacity={1} 
            fill="url(#colorParticipated)" 
            strokeWidth={3} 
            dot={{ r: 4, strokeWidth: 2, fill: '#fff', stroke: '#6366f1' }}
            activeDot={{ r: 6, strokeWidth: 0, fill: '#6366f1' }}
          />

          {/* Green Line - Wins */}
          <Area 
            type="monotone" 
            dataKey="won" 
            name="won"
            stroke="#10b981" 
            fillOpacity={1} 
            fill="url(#colorWon)" 
            strokeWidth={3} 
            dot={{ r: 4, strokeWidth: 2, fill: '#fff', stroke: '#10b981' }}
            activeDot={{ r: 6, strokeWidth: 0, fill: '#10b981' }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

export default BiddingTrendChart;