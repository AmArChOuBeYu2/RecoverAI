import React from 'react';
import { 
  LayoutDashboard, 
  RotateCcw, 
  Layers, 
  TrendingUp, 
  PlayCircle, 
  FileText, 
  Sparkles
} from 'lucide-react';

interface SidebarProps {
  currentPath: string;
  onNavigate: (path: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentPath, onNavigate }) => {
  const navItems = [
    { id: '/home', label: 'Overview', icon: LayoutDashboard },
    { id: '/recovery', label: 'Recovery', icon: RotateCcw },
    { id: '/segments', label: 'Segments', icon: Layers },
    { id: '/strategies', label: 'Strategies', icon: TrendingUp },
    { id: '/simulator', label: 'Simulator', icon: PlayCircle },
    { id: '/evidence', label: 'Evidence', icon: FileText },
  ];

  return (
    <aside className="w-64 bg-slate-900/90 border-r border-slate-800 flex flex-col justify-between h-screen sticky top-0 z-30 shrink-0">
      <div>
        {/* Brand Logo & Title */}
        <div className="p-6 border-b border-slate-800/80">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <h1 className="font-serif-title text-2xl font-normal text-slate-100 tracking-wider">
                NIVARAN
              </h1>
              <p className="text-[10px] text-slate-400 uppercase tracking-widest font-mono">
                Revenue Recovery System
              </p>
            </div>
          </div>
        </div>

        {/* Primary Navigation Links */}
        <nav className="p-4 space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentPath === item.id || (currentPath === '/overview' && item.id === '/home') || (item.id !== '/home' && currentPath.startsWith(item.id));
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all cursor-pointer ${
                  isActive
                    ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-emerald-400' : 'text-slate-500'}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Public Landing Link & Footer Tagline */}
      <div className="p-4 space-y-3">
        <button
          onClick={() => onNavigate('/')}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700 text-xs font-mono transition-all"
        >
          <span>← PUBLIC LANDING</span>
        </button>

        <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/80 text-center">
          <p className="text-xs font-serif italic text-slate-300">
            "Revenue recovery, resolved intelligently."
          </p>
          <p className="text-[10px] font-mono text-slate-500 mt-1">
            Razorpay Buildathon · Track 03
          </p>
        </div>
      </div>
    </aside>
  );
};
