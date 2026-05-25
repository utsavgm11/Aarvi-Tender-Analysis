import React from 'react'
import { BarChart3 } from 'lucide-react'

const DashboardView = () => {
  return (
    <div className="flex flex-col items-center justify-center h-full text-slate-500 bg-slate-50 p-4 sm:p-8">
      <div className="max-w-md w-full bg-white border border-slate-200 rounded-2xl shadow-sm p-6 sm:p-10 text-center flex flex-col items-center">
        <div className="w-14 h-14 sm:w-16 sm:h-16 bg-blue-50 text-blue-500 rounded-full flex items-center justify-center mb-4 sm:mb-6 shrink-0">
          {/* Using Tailwind sizing classes here so the icon scales perfectly with the screen */}
          <BarChart3 className="w-7 h-7 sm:w-8 sm:h-8" />
        </div>
        <h2 className="text-xl sm:text-2xl font-bold text-slate-800 mb-2 sm:mb-3">Master Dashboard</h2>
        <p className="text-sm sm:text-base text-slate-500 leading-relaxed">
          Historical tender analytics and win-rate tracking are currently under development. Awaiting backend data integration.
        </p>
      </div>
    </div>
  )
}

export default DashboardView