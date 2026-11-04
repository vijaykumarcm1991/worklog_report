import { useEffect, useState } from 'react'
import { api } from '../api.js'
import icons from '../icons.jsx'

const emptyForm = {
  name: '',
  instance_type: 'cloud',
  base_url: '',
  username: '',
  token: '',
  label: '#6366f1',
  days_to_fetch: 30,
  enabled: true,
}

export default function InstancesView() {
  const [instances, setInstances] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null) // instance id being edited
  const [form, setForm] = useState(emptyForm)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [testResult, setTestResult] = useState(null)

  const load = async () => {
    setInstances(await api.listInstances())
  }

  useEffect(() => {
    load().catch((e) => setMsg(e.message))
  }, [])

  const resetForm = () => {
    setForm(emptyForm)
    setEditing(null)
    setTestResult(null)
  }

  const startEdit = (inst) => {
    setEditing(inst.id)
    setForm({
      name: inst.name,
      instance_type: inst.instance_type,
      base_url: inst.base_url,
      username: inst.username,
      token: '',
      label: inst.label || '#6366f1',
      days_to_fetch: inst.days_to_fetch,
      enabled: inst.enabled,
    })
    setTestResult(null)
    setShowForm(true)
  }

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const setNum = (k) => (e) => setForm((f) => ({ ...f, [k]: Number(e.target.value) }))

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setMsg('')
    try {
      if (editing) {
        await api.updateInstance(editing, form)
      } else {
        await api.createInstance(form)
      }
      resetForm()
      setShowForm(false)
      await load()
    } catch (err) {
      setMsg(err.message)
    } finally {
      setBusy(false)
    }
  }

  const remove = async (inst) => {
    if (!confirm(`Delete instance "${inst.name}"? This also removes its saved users and worklogs.`)) return
    await api.deleteInstance(inst.id)
    if (editing === inst.id) resetForm()
    await load()
  }

  const testConn = async (inst) => {
    setMsg('')
    setTestResult(null)
    try {
      const r = await api.testInstance(inst.id)
      setTestResult(r)
    } catch (err) {
      setMsg(err.message)
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="page-title">Instances</h1>
          <p className="mt-1 text-sm text-slate-400">Configure your Jira Cloud and on-prem Server/DC connections</p>
        </div>
        <button className="btn-primary" onClick={() => { resetForm(); setShowForm((s) => !s) }}>
          {icons.plus} {showForm && !editing ? 'Cancel' : 'Add instance'}
        </button>
      </div>

      {msg && <div className="card mb-4 border-rose-500/40 px-4 py-3 text-sm text-rose-300">{msg}</div>}
      {testResult && (
        <div className={`card mb-4 border px-4 py-3 text-sm ${testResult.ok ? 'border-emerald-500/40 text-emerald-300' : 'border-rose-500/40 text-rose-300'}`}>
          {testResult.ok ? icons.check : icons.x} {testResult.message}
        </div>
      )}

      {/* Add / edit form */}
      {showForm && (
        <form onSubmit={submit} className="card mb-8 p-6">
          <h2 className="mb-5 text-lg font-semibold">{editing ? 'Edit instance' : 'New instance'}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="label">Name</label>
              <input required className="input" value={form.name} onChange={set('name')} placeholder="e.g. Corporate Cloud" />
            </div>
            <div>
              <label className="label">Type</label>
              <select className="input" value={form.instance_type} onChange={set('instance_type')}>
                <option value="cloud">Jira Cloud</option>
                <option value="onprem">Jira On-prem (Server/DC)</option>
              </select>
            </div>
            <div>
              <label className="label">{form.instance_type === 'cloud' ? 'Site URL' : 'Base URL'}</label>
              <input required className="input" value={form.base_url} onChange={set('base_url')}
                placeholder={form.instance_type === 'cloud' ? 'https://your-site.atlassian.net' : 'https://jira.corp.example.com'} />
            </div>
            <div>
              <label className="label">{form.instance_type === 'cloud' ? 'Email' : 'Username'}</label>
              <input required className="input" value={form.username} onChange={set('username')}
                placeholder={form.instance_type === 'cloud' ? 'you@company.com' : 'jira-username'} />
            </div>
            <div>
              <label className="label">API token / password</label>
              <input type="password" className="input" value={form.token} onChange={set('token')}
                placeholder={editing ? 'Leave blank to keep current' : 'Atlassian API token or on-prem password'} />
            </div>
            <div>
              <label className="label">Days to fetch</label>
              <input type="number" min="1" max="365" className="input" value={form.days_to_fetch} onChange={setNum('days_to_fetch')} />
            </div>
            <div>
              <label className="label">Label color</label>
              <div className="flex items-center gap-2">
                <input type="color" className="h-10 w-12 rounded-lg border border-white/10 bg-slate-900" value={form.label} onChange={set('label')} />
                <span className="text-sm text-slate-400">{form.label}</span>
              </div>
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.enabled} onChange={(e) => setForm((f) => ({ ...f, enabled: e.target.checked }))} className="h-4 w-4 accent-brand-500" />
                Enabled (included in sync &amp; calendar)
              </label>
            </div>
          </div>
          <div className="mt-6 flex gap-3">
            <button type="submit" className="btn-primary" disabled={busy}>Save {busy ? '…' : ''}</button>
            <button type="button" className="btn-ghost" onClick={() => { resetForm(); setShowForm(false) }}>Cancel</button>
          </div>
        </form>
      )}

      {/* List */}
      {instances.length === 0 && !showForm ? (
        <div className="card p-10 text-center text-slate-400">No instances yet. Add your first Jira connection above.</div>
      ) : (
        <div className="space-y-3">
          {instances.map((inst) => (
            <div key={inst.id} className="card flex flex-wrap items-center gap-4 p-5">
              <span className="h-10 w-1.5 rounded-full" style={{ backgroundColor: inst.label || '#6366f1' }} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-semibold">{inst.name}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${inst.instance_type === 'cloud' ? 'bg-sky-500/15 text-sky-300' : 'bg-emerald-500/15 text-emerald-300'}`}>
                    {inst.instance_type === 'cloud' ? 'Cloud' : 'On-prem'}
                  </span>
                  {!inst.enabled && <span className="rounded-full bg-white/10 px-2 py-0.5 text-[11px] text-slate-400">disabled</span>}
                </div>
                <div className="mt-0.5 truncate text-xs text-slate-500">{inst.base_url} · {inst.username}</div>
                <div className="mt-0.5 text-xs text-slate-500">Fetch {inst.days_to_fetch}d · {inst.has_credential ? '🔒 credential stored' : '⚠ no credential'}</div>
              </div>
              <div className="flex items-center gap-2">
                <button className="btn-ghost !py-1.5" onClick={() => testConn(inst)}>{icons.plug} Test</button>
                <button className="btn-ghost !py-1.5" onClick={() => startEdit(inst)}>Edit</button>
                <button className="btn-danger !py-1.5" onClick={() => remove(inst)}>{icons.trash}</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
