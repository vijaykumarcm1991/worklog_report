import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import icons from '../icons.jsx'

export default function UsersView() {
  const [instances, setInstances] = useState([])
  const [selectedInstance, setSelectedInstance] = useState('')
  const [saved, setSaved] = useState([])
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  const loadInstances = useCallback(async () => {
    const list = await api.listInstances()
    setInstances(list)
    return list
  }, [])

  useEffect(() => {
    loadInstances().catch((e) => setMsg(e.message))
  }, [loadInstances])

  // Load saved users whenever the selected instance changes
  useEffect(() => {
    if (!selectedInstance) {
      setSaved([])
      return
    }
    api.listUsers(selectedInstance).then(setSaved).catch((e) => setMsg(e.message))
  }, [selectedInstance])

  const debouncedSearch = useCallback(async (q) => {
    if (!selectedInstance) return
    setSearching(true)
    setMsg('')
    setResults([])
    try {
      const r = await api.searchUsers(selectedInstance, q)
      setResults(r)
    } catch (e) {
      setMsg(e.message)
    } finally {
      setSearching(false)
    }
  }, [selectedInstance])

  useEffect(() => {
    const t = setTimeout(() => {
      if (selectedInstance) debouncedSearch(query)
    }, 300)
    return () => clearTimeout(t)
  }, [query, selectedInstance, debouncedSearch])

  const save = async (user) => {
    setBusy(true)
    setMsg('')
    try {
      const savedUser = await api.saveUser(selectedInstance, user)
      setSaved((s) => {
        const existing = s.find((x) => x.user_key === savedUser.user_key)
        return existing ? s.map((x) => (x.user_key === savedUser.user_key ? savedUser : x)) : [...s, savedUser]
      })
    } catch (e) {
      setMsg(e.message)
    } finally {
      setBusy(false)
    }
  }

  const remove = async (user) => {
    if (!confirm(`Remove ${user.display_name} from this instance?`)) return
    await api.deleteUser(selectedInstance, user.id)
    setSaved((s) => s.filter((x) => x.id !== user.id))
  }

  const instance = instances.find((i) => String(i.id) === String(selectedInstance))

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-8">
        <h1 className="page-title">Users</h1>
        <p className="mt-1 text-sm text-slate-400">Pick users per instance from a live search dropdown and save them for reporting</p>
      </div>

      {msg && <div className="card mb-4 border-rose-500/40 px-4 py-3 text-sm text-rose-300">{msg}</div>}

      {/* Instance picker */}
      <div className="card mb-6 p-5">
        <label className="label">Select an instance</label>
        <select className="input" value={selectedInstance} onChange={(e) => setSelectedInstance(e.target.value)}>
          <option value="">Choose an instance…</option>
          {instances.map((i) => (
            <option key={i.id} value={i.id}>{i.name} ({i.instance_type})</option>
          ))}
        </select>
      </div>

      {selectedInstance && (
        <>
          {/* Search dropdown */}
          <div className="card mb-6 p-5">
            <div className="mb-3 flex items-center gap-2">
              {icons.search}
              <h2 className="text-sm font-semibold">Search users on <span className="text-brand-300">{instance?.name}</span></h2>
            </div>
            <div className="relative">
              <input
                className="input"
                placeholder="Type to search by name or email…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            {searching && <div className="mt-3 text-sm text-slate-400">Searching…</div>}
            {!searching && results.length > 0 && (
              <div className="mt-3 max-h-72 space-y-1 overflow-y-auto">
                {results.map((r) => {
                  const alreadySaved = saved.some((s) => s.user_key === r.user_key)
                  return (
                    <div key={r.user_key} className="flex items-center justify-between gap-3 rounded-xl bg-white/[0.03] px-3 py-2 hover:bg-white/[0.06]">
                      <div className="flex min-w-0 items-center gap-3">
                        {r.avatar_url ? (
                          <img src={r.avatar_url} alt="" className="h-8 w-8 rounded-full" referrerPolicy="no-referrer" />
                        ) : (
                          <div className="grid h-8 w-8 place-items-center rounded-full bg-brand-500/20 text-sm font-semibold text-brand-200">
                            {(r.display_name || '?').charAt(0).toUpperCase()}
                          </div>
                        )}
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium">{r.display_name}</div>
                          <div className="truncate text-xs text-slate-500">{r.email || r.user_key}</div>
                        </div>
                      </div>
                      <button
                        className={alreadySaved ? 'btn-ghost !py-1.5' : 'btn-primary !py-1.5'}
                        onClick={() => save(r)}
                        disabled={busy || alreadySaved}
                      >
                        {alreadySaved ? 'Saved' : 'Save'}
                      </button>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Saved users */}
          <div className="card p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold">Saved users ({saved.length})</h2>
              <span className="text-xs text-slate-500">Only users shown here are reported in the calendar</span>
            </div>
            {saved.length === 0 ? (
              <div className="py-6 text-center text-sm text-slate-400">No users saved for this instance yet. Search and save above.</div>
            ) : (
              <div className="space-y-2">
                {saved.map((u) => (
                  <div key={u.id} className="flex items-center justify-between gap-3 rounded-xl bg-white/[0.03] px-3 py-2">
                    <div className="flex min-w-0 items-center gap-3">
                      {u.avatar_url ? (
                        <img src={u.avatar_url} alt="" className="h-8 w-8 rounded-full" referrerPolicy="no-referrer" />
                      ) : (
                        <div className="grid h-8 w-8 place-items-center rounded-full bg-brand-500/20 text-sm font-semibold text-brand-200">
                          {(u.display_name || '?').charAt(0).toUpperCase()}
                        </div>
                      )}
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium">{u.display_name}</div>
                        <div className="truncate text-xs text-slate-500">{u.email || u.user_key}</div>
                      </div>
                    </div>
                    <button className="btn-danger !py-1.5" onClick={() => remove(u)}>Remove</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
