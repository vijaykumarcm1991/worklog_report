import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import icons from '../icons.jsx'

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

// Distinct identity colors per user (dot + chip accent).
const USER_COLORS = ['#818cf8', '#34d399', '#f472b6', '#fbbf24', '#38bdf8', '#fb923c', '#a78bfa', '#2dd4bf', '#f87171', '#a3e635']

function fmtHours(h) {
  const hours = Math.floor(h)
  const mins = Math.round((h - hours) * 60)
  if (hours === 0 && mins === 0) return '0m'
  if (hours === 0) return `${mins}m`
  return mins === 0 ? `${hours}h` : `${hours}h ${mins}m`
}

const STATUS_TEXT = {
  ok: 'text-emerald-300',
  under: 'text-amber-300',
  over: 'text-sky-300',
  none: 'text-slate-500',
}

const pad = (n) => String(n).padStart(2, '0')
const dateKey = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

// Today's date in IST, whatever timezone the browser is in. Returned as a
// plain local Date for that calendar day (used only for its y/m/d).
function istToday() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const get = (t) => Number(parts.find((p) => p.type === t).value)
  return new Date(get('year'), get('month') - 1, get('day'))
}

function readPref(key) {
  try {
    return localStorage.getItem(key) || ''
  } catch {
    return ''
  }
}
function writePref(key, value) {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* ignore */
  }
}

export default function CalendarView() {
  const [today] = useState(istToday)
  const requestSeq = useRef(0)
  const [month, setMonth] = useState(() => new Date(today.getFullYear(), today.getMonth(), 1))
  const [instanceId, setInstanceId] = useState(() => readPref('wl.instance'))
  const [data, setData] = useState(null)
  const [hidden, setHidden] = useState(() => new Set())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState(null)

  const fetchCalendar = useCallback(async (m, instId) => {
    // Only the latest request may update state; a slow earlier response
    // (e.g. after clicking through months quickly) is discarded.
    const seq = ++requestSeq.current
    setLoading(true)
    setError('')
    const start = new Date(m.getFullYear(), m.getMonth(), 1)
    const end = new Date(m.getFullYear(), m.getMonth() + 1, 0)
    try {
      const d = await api.calendar(dateKey(start), dateKey(end), instId)
      if (seq === requestSeq.current) setData(d)
    } catch (e) {
      if (seq === requestSeq.current) setError(e.message)
    } finally {
      if (seq === requestSeq.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchCalendar(month, instanceId)
  }, [month, instanceId, fetchCalendar])

  // A stored instance that no longer exists falls back to "all".
  useEffect(() => {
    if (data && instanceId && !data.instances.some((i) => String(i.id) === String(instanceId))) {
      setInstanceId('')
    }
  }, [data, instanceId])

  const changeInstance = (value) => {
    setInstanceId(value)
    writePref('wl.instance', value)
    setHidden(new Set())
  }

  const users = useMemo(() => data?.users || [], [data])
  const colorOf = useMemo(() => {
    const map = {}
    users.forEach((u, i) => (map[u.user.id] = USER_COLORS[i % USER_COLORS.length]))
    return map
  }, [users])
  const visibleUsers = useMemo(() => users.filter((u) => !hidden.has(u.user.id)), [users, hidden])

  // date -> [{user, day}] for visible users only
  const byDate = useMemo(() => {
    const map = {}
    visibleUsers.forEach((u) => {
      u.days.forEach((d) => {
        if (d.seconds > 0) (map[d.date] ||= []).push({ u, d })
      })
    })
    return map
  }, [visibleUsers])

  const cells = useMemo(() => {
    const first = new Date(month.getFullYear(), month.getMonth(), 1)
    const offset = (first.getDay() + 6) % 7 // Monday-first
    const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()
    const list = []
    for (let i = 0; i < offset; i++) list.push(null)
    for (let d = 1; d <= daysInMonth; d++) list.push(new Date(month.getFullYear(), month.getMonth(), d))
    return list
  }, [month])

  const monthHours = visibleUsers.reduce((s, u) => s + u.total_hours, 0)
  const daysCount = Object.keys(byDate).length
  const target = data?.daily_target_hours || 8

  const toggleUser = (id) =>
    setHidden((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const handleSync = async () => {
    setSyncing(true)
    setError('')
    try {
      setSyncResult(null)
      const r = await api.sync(instanceId ? [Number(instanceId)] : null)
      setSyncResult(r)
      await fetchCalendar(month, instanceId)
    } catch (e) {
      setError(e.message)
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="page-title">Calendar</h1>
          <p className="mt-1 text-sm text-slate-400">
            Each user's daily worklog hours vs target
            {data ? (
              <>
                {' '}· target <span className="font-semibold text-brand-300">{data.daily_target_hours}h</span>/day
              </>
            ) : null}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <select
              className="input appearance-none !pr-9 font-medium"
              value={instanceId}
              onChange={(e) => changeInstance(e.target.value)}
              aria-label="Instance"
            >
              <option value="">All instances</option>
              {(data?.instances || []).map((i) => (
                <option key={i.id} value={i.id}>
                  {i.name} ({i.instance_type === 'cloud' ? 'Cloud' : 'On-prem'})
                </option>
              ))}
            </select>
            <span className="pointer-events-none absolute inset-y-0 right-3 grid place-items-center text-slate-400">▾</span>
          </div>
          <button className="btn-primary" onClick={handleSync} disabled={syncing}>
            {icons.refresh} {syncing ? 'Syncing…' : instanceId ? 'Sync instance' : 'Sync all'}
          </button>
        </div>
      </div>

      {error && <div className="card mb-6 border-rose-500/40 px-4 py-3 text-sm text-rose-300">{error}</div>}

      {syncResult && (
        <div className={`card animate-in mb-4 flex items-start justify-between gap-4 px-4 py-3 text-sm ${syncResult.errors.length ? 'border-amber-400/30' : 'border-emerald-400/30'}`}>
          <div>
            <div className={`font-semibold ${syncResult.errors.length ? 'text-amber-300' : 'text-emerald-300'}`}>
              Sync complete — {syncResult.worklogs} worklogs · {syncResult.users} user(s) · {syncResult.instances} instance(s)
            </div>
            {syncResult.errors.length > 0 && (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-amber-200/90">
                {syncResult.errors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            )}
          </div>
          <button className="text-slate-400 hover:text-white" onClick={() => setSyncResult(null)} aria-label="Dismiss">{icons.x}</button>
        </div>
      )}

      {/* Summary cards */}
      {data && (
        <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-4">
          {[
            { label: 'Month total', value: `${monthHours.toFixed(1)}h`, sub: 'selected users combined', glow: 'from-brand-500/25' },
            { label: 'Days logged', value: `${daysCount}`, sub: 'days with any worklog', glow: 'from-emerald-500/20' },
            { label: 'Daily target', value: `${data.daily_target_hours}h`, sub: 'per user, change in Settings', glow: 'from-sky-500/20' },
            { label: 'Users shown', value: `${visibleUsers.length}/${users.length}`, sub: instanceId ? 'in this instance' : 'across instances', glow: 'from-fuchsia-500/20' },
          ].map((s) => (
            <div key={s.label} className="card relative overflow-hidden p-4">
              <div className={`pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full bg-gradient-to-br ${s.glow} to-transparent blur-2xl`} />
              <div className="relative text-[11px] font-semibold uppercase tracking-wider text-slate-400">{s.label}</div>
              <div className="relative mt-1.5 text-3xl font-extrabold tracking-tight text-white">{s.value}</div>
              <div className="relative text-xs text-slate-500">{s.sub}</div>
            </div>
          ))}
        </div>
      )}

      {/* User chips (click to show/hide) */}
      {users.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          {users.map((u) => {
            const off = hidden.has(u.user.id)
            return (
              <button
                key={u.user.id}
                onClick={() => toggleUser(u.user.id)}
                title={off ? 'Show on calendar' : 'Hide from calendar'}
                className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs transition ${
                  off ? 'border-white/5 bg-white/[0.02] text-slate-600' : 'border-white/15 bg-white/[0.06] text-slate-200 hover:bg-white/10'
                }`}
              >
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: off ? '#475569' : colorOf[u.user.id] }} />
                <span className="font-semibold">{u.user.display_name}</span>
                {!instanceId && <span className="text-slate-500">· {u.instance_name}</span>}
                <span className="tabular-nums text-slate-400">{u.total_hours.toFixed(1)}h</span>
              </button>
            )
          })}
        </div>
      )}

      {/* Month navigation + legend */}
      <div className="card mb-4 flex flex-wrap items-center justify-between gap-3 p-3">
        <div className="flex items-center gap-2">
          <button className="btn-ghost !px-3" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))} aria-label="Previous month">‹</button>
          <span className="min-w-36 text-center text-base font-semibold">{MONTHS[month.getMonth()]} {month.getFullYear()}</span>
          <button className="btn-ghost !px-3" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))} aria-label="Next month">›</button>
          <button className="btn-ghost !py-1.5" onClick={() => setMonth(new Date(today.getFullYear(), today.getMonth(), 1))}>Today</button>
        </div>
        <div className="flex items-center gap-4 text-xs text-slate-400">
          <span>Hours vs target:</span>
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-emerald-400" /> Met</span>
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-amber-400" /> Under</span>
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-sky-400" /> Over</span>
        </div>
      </div>

      {data && users.length === 0 && (
        <div className="card mb-4 p-8 text-center text-sm text-slate-400">
          No users to show{instanceId ? ' for this instance' : ''}. Add some on the{' '}
          <Link to="/users" className="font-semibold text-brand-300 hover:underline">Users</Link> page.
        </div>
      )}

      {/* Calendar grid */}
      <div className="card overflow-hidden">
        {loading && !data && <div className="skeleton m-4 h-72 rounded-xl" />}
        <div className="grid grid-cols-7 gap-px bg-white/5">
          {WEEKDAYS.map((d) => (
            <div key={d} className="bg-slate-950/60 px-2 py-2.5 text-center text-[11px] font-semibold uppercase tracking-wider text-slate-500">{d}</div>
          ))}
          {cells.map((date, i) => {
            if (!date) return <div key={`empty-${i}`} className="min-h-28 bg-slate-950/40" />
            const key = dateKey(date)
            const entries = byDate[key] || []
            const isToday = date.toDateString() === today.toDateString()
            const isWeekend = date.getDay() === 0 || date.getDay() === 6
            return (
              <div
                key={key}
                className={`min-h-28 bg-slate-950/30 p-1.5 transition hover:bg-white/[0.04] ${isWeekend && !entries.length ? 'opacity-50' : ''} ${isToday ? 'ring-1 ring-inset ring-brand-400/60' : ''}`}
              >
                <span className={`mb-1 grid h-6 w-6 place-items-center rounded-full text-xs font-semibold ${isToday ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/40' : 'text-slate-400'}`}>
                  {date.getDate()}
                </span>
                <div className="space-y-1">
                  {entries.map(({ u, d }) => (
                    <div
                      key={u.user.id}
                      title={`${u.user.display_name}: ${fmtHours(d.hours)} of ${target}h target`}
                      className="rounded-md bg-white/[0.05] px-1.5 py-1"
                    >
                      <div className="flex items-center gap-1.5 text-[11px] leading-none">
                        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: colorOf[u.user.id] }} />
                        <span className="min-w-0 flex-1 truncate text-slate-300">{u.user.display_name.split(' ')[0]}</span>
                        <span className={`font-bold tabular-nums ${STATUS_TEXT[d.status]}`}>{fmtHours(d.hours)}</span>
                      </div>
                      <div className="mt-1 h-0.5 overflow-hidden rounded-full bg-white/10">
                        <div
                          className="h-full rounded-full"
                          style={{ width: `${Math.min(100, (d.hours / target) * 100)}%`, background: colorOf[u.user.id] }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
