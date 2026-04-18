import { Link, NavLink, Outlet } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';

interface RunSummary {
  id: number;
  status: string;
  current_step: string | null;
}

const navItems = [
  { to: '/', label: 'Console', icon: DashboardIcon, badgeKey: null },
  { to: '/dashboard', label: 'Dashboard', icon: ActivityIcon, badgeKey: null },
  { to: '/activity', label: 'Activity', icon: ActivityIcon, badgeKey: 'pending_review' as const },
  { to: '/review', label: 'Image Review', icon: ReviewIcon, badgeKey: 'image_review' as const },
  { to: '/concepts', label: 'Concepts', icon: ConceptsIcon, badgeKey: null },
];

function useSidebarBadges() {
  const { data } = useQuery<RunSummary[]>({
    queryKey: ['sidebar-badges'],
    queryFn: () => fetch('/api/runs?limit=50').then(r => r.ok ? r.json() : []),
    refetchInterval: 15000,
  });
  const runs = data || [];
  return {
    pending_review: runs.filter(r => r.status === 'pending_review').length,
    image_review: runs.filter(r => r.status === 'running' && r.current_step === 'images ready for review').length,
  };
}

export default function Layout() {
  const badges = useSidebarBadges();

  return (
    <div className="flex min-h-screen bg-[#0f0f0f]">
      {/* Sidebar */}
      <aside className="w-60 bg-[#1a1a1a] border-r border-[#2a2a2a] flex flex-col shrink-0">
        <Link to="/" className="px-5 py-5 border-b border-[#2a2a2a] no-underline">
          <h1 className="text-base font-semibold text-white tracking-tight m-0">
            Content Factory
          </h1>
          <p className="text-xs text-gray-500 mt-0.5">Multi-Channel Automation</p>
        </Link>
        <nav className="flex-1 p-3 space-y-1">
          {navItems.map((item) => {
            const count = item.badgeKey ? badges[item.badgeKey] : 0;
            return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors no-underline ${
                  isActive
                    ? 'bg-purple-600/15 text-purple-400'
                    : 'text-gray-400 hover:bg-[#2a2a2a] hover:text-gray-200'
                }`
              }
            >
              <item.icon />
              <span className="flex-1">{item.label}</span>
              {count > 0 && (
                <span className="ml-auto inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-purple-600 text-white text-[10px] font-bold">
                  {count}
                </span>
              )}
            </NavLink>
            );
          })}
        </nav>
        <div className="p-4 border-t border-[#2a2a2a]">
          <p className="text-xs text-gray-600">v2.0.0</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-6xl mx-auto p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

function ActivityIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
    </svg>
  );
}

function ConceptsIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
    </svg>
  );
}

function ReviewIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>
  );
}

function DashboardIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
    </svg>
  );
}
