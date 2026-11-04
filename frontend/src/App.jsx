import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import CalendarView from './views/CalendarView.jsx'
import InstancesView from './views/InstancesView.jsx'
import UsersView from './views/UsersView.jsx'
import SettingsView from './views/SettingsView.jsx'
import icons from './icons.jsx'

const nav = [
  { to: '/calendar', label: 'Calendar', icon: icons.calendar },
  { to: '/instances', label: 'Instances', icon: icons.server },
  { to: '/users', label: 'Users', icon: icons.users },
  { to: '/settings', label: 'Settings', icon: icons.gear },
]

export default function App() {
  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="sticky top-0 flex h-screen w-16 flex-col items-center gap-2 border-r border-white/[0.07] bg-slate-950/40 py-5 backdrop-blur-xl md:w-56 md:items-stretch md:px-4">
        <div className="mb-4 flex items-center justify-center gap-2.5 md:justify-start">
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-indigo-700 text-white shadow-lg shadow-brand-500/30">
            {icons.spark}
          </div>
          <div className="hidden md:block">
            <div className="text-sm font-extrabold leading-tight tracking-tight">Worklog</div>
            <div className="text-[11px] text-slate-400">Dashboard</div>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-1">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center justify-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors md:justify-start ${
                  isActive
                    ? 'bg-gradient-to-r from-brand-500/20 to-brand-500/5 text-white ring-1 ring-brand-400/30 shadow-[0_0_24px_-8px] shadow-brand-500/60'
                    : 'text-slate-400 hover:bg-white/5 hover:text-slate-100'
                }`
              }
            >
              <span className="shrink-0">{item.icon}</span>
              <span className="hidden md:inline">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto hidden rounded-xl border border-white/[0.08] bg-white/[0.03] p-3 text-[11px] leading-snug text-slate-400 md:block">
          Cloud + on-prem Jira worklogs, in one calendar.
        </div>
      </aside>

      {/* Main */}
      <main className="animate-in flex-1 overflow-x-hidden p-5 md:p-10">
        <Routes>
          <Route path="/" element={<Navigate to="/calendar" replace />} />
          <Route path="/calendar" element={<CalendarView />} />
          <Route path="/instances" element={<InstancesView />} />
          <Route path="/users" element={<UsersView />} />
          <Route path="/settings" element={<SettingsView />} />
        </Routes>
      </main>
    </div>
  )
}
