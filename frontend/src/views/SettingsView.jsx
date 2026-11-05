import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function SettingsView() {
  const [config, setConfig] = useState({ daily_target_hours: '8' })
  const [hours, setHours] = useState('8')
  const [saved, setSaved] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    api.getConfig().then((c) => {
      setConfig(c)
      setHours(c.daily_target_hours || '8')
    }).catch((e) => setMsg(e.message))
  }, [])

  const save = async (e) => {
    e.preventDefault()
    setMsg('')
    setSaved(false)
    const value = parseFloat(hours)
    if (isNaN(value) || value <= 0 || value > 24) {
      setMsg('Daily target must be a number between 0 and 24.')
      return
    }
    try {
      await api.setConfig('daily_target_hours', String(value))
      setConfig({ ...config, daily_target_hours: String(value) })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      setMsg(err.message)
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-8">
        <h1 className="page-title">Settings</h1>
        <p className="mt-1 text-sm text-slate-400">Configure reporting defaults and sync behaviour</p>
      </div>

      {msg && <div className="card mb-4 border-rose-500/40 px-4 py-3 text-sm text-rose-300">{msg}</div>}

      <form onSubmit={save} className="card p-6">
        <h2 className="mb-1 text-lg font-semibold">Daily target hours</h2>
        <p className="mb-5 text-sm text-slate-400">The calendar marks a day as "met" when worklog hours reach this value. Default: 8.</p>
        <div className="flex items-end gap-3">
          <div className="w-40">
            <label className="label">Hours per day</label>
            <div className="relative">
              <input type="number" min="0.5" step="0.5" className="input pr-8" value={hours} onChange={(e) => setHours(e.target.value)} />
              <span className="pointer-events-none absolute inset-y-0 right-3 grid place-items-center text-sm text-slate-500">h</span>
            </div>
          </div>
          <button type="submit" className="btn-primary">{saved ? 'Saved ✓' : 'Save'}</button>
        </div>
        {config.daily_target_hours && (
          <p className="mt-4 text-xs text-slate-500">Current stored value: {config.daily_target_hours}h/day</p>
        )}
      </form>

      <div className="card mt-6 p-6 text-sm text-slate-400">
        <h2 className="mb-2 text-base font-semibold text-slate-200">Sync behaviour</h2>
        <p>Worklogs are fetched from each enabled instance on a background schedule and on demand via <em>Sync now</em> on the Calendar page. Only saved (selected) users per instance are pulled. Credentials are stored encrypted at rest.</p>
      </div>
    </div>
  )
}
