// Small fetch wrapper for the backend API.
const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (res.status === 204) return null
  const text = await res.text()
  const data = text ? JSON.parse(text) : null
  if (!res.ok) {
    throw new Error(typeof data?.detail === 'string' ? data.detail : `Request failed (${res.status})`)
  }
  return data
}

export const api = {
  // instances
  listInstances: () => request('/instances'),
  createInstance: (b) => request('/instances', { method: 'POST', body: JSON.stringify(b) }),
  updateInstance: (id, b) => request(`/instances/${id}`, { method: 'PUT', body: JSON.stringify(b) }),
  deleteInstance: (id) => request(`/instances/${id}`, { method: 'DELETE' }),
  testInstance: (id) => request(`/instances/${id}/test`, { method: 'POST' }),

  // users
  listUsers: (instanceId) => request(`/instances/${instanceId}/users`),
  searchUsers: (instanceId, q) =>
    request(`/instances/${instanceId}/users/search?q=${encodeURIComponent(q)}`),
  saveUser: (instanceId, user) =>
    request(`/instances/${instanceId}/users`, { method: 'POST', body: JSON.stringify(user) }),
  deleteUser: (instanceId, userId) =>
    request(`/instances/${instanceId}/users/${userId}`, { method: 'DELETE' }),

  // config
  getConfig: () => request('/config'),
  setConfig: (key, value) => request('/config', { method: 'PUT', body: JSON.stringify({ key, value }) }),

  // sync
  sync: (instanceIds) => request('/sync', { method: 'POST', body: JSON.stringify({ instance_ids: instanceIds || null }) }),

  // calendar
  calendar: (start, end, instanceId) =>
    request(`/calendar?start=${start}&end=${end}${instanceId ? `&instance_id=${instanceId}` : ''}`),
}
