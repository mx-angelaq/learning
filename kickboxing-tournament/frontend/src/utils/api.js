/**
 * API client with auth token management.
 */

const BASE = '/api';

function getToken() {
  return localStorage.getItem('token');
}

function getRole() {
  return localStorage.getItem('role');
}

function setAuth(token, role) {
  localStorage.setItem('token', token);
  localStorage.setItem('role', role);
}

function clearAuth() {
  localStorage.removeItem('token');
  localStorage.removeItem('role');
}

async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const resp = await fetch(`${BASE}${path}`, { ...options, headers });
  if (resp.status === 401 || resp.status === 403) {
    // Don't clear auth on public endpoints
    if (options.requireAuth !== false) {
      // Let caller handle
    }
  }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || JSON.stringify(err));
  }
  if (resp.status === 204) return null;
  return resp.json();
}

const api = {
  getToken, getRole, setAuth, clearAuth,

  // Auth
  login: (password, role) =>
    apiFetch('/auth/login', { method: 'POST', body: JSON.stringify({ password, role }) }),

  // Tournaments
  getTournaments: () => apiFetch('/tournaments'),
  getTournament: (id) => apiFetch(`/tournaments/${id}`),
  createTournament: (data) =>
    apiFetch('/tournaments', { method: 'POST', body: JSON.stringify(data) }),
  updateTournament: (id, data) =>
    apiFetch(`/tournaments/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteTournament: (id) =>
    apiFetch(`/tournaments/${id}`, { method: 'DELETE' }),
  getWeightPresets: (id) => apiFetch(`/tournaments/${id}/weight-presets`),

  // Divisions
  getDivisions: (tid) => apiFetch(`/tournaments/${tid}/divisions`),
  getDivision: (tid, did) => apiFetch(`/tournaments/${tid}/divisions/${did}`),
  createDivision: (tid, data) =>
    apiFetch(`/tournaments/${tid}/divisions`, { method: 'POST', body: JSON.stringify(data) }),
  updateDivision: (tid, did, data) =>
    apiFetch(`/tournaments/${tid}/divisions/${did}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteDivision: (tid, did) =>
    apiFetch(`/tournaments/${tid}/divisions/${did}`, { method: 'DELETE' }),

  // Competitors
  getCompetitors: (tid, did) =>
    apiFetch(`/tournaments/${tid}/divisions/${did}/competitors`),
  createCompetitor: (tid, did, data, force = false) =>
    apiFetch(`/tournaments/${tid}/divisions/${did}/competitors?force=${force}`, {
      method: 'POST', body: JSON.stringify(data),
    }),
  bulkCreateCompetitors: (tid, did, competitors, force = false) =>
    apiFetch(`/tournaments/${tid}/divisions/${did}/competitors/bulk?force=${force}`, {
      method: 'POST', body: JSON.stringify({ competitors }),
    }),
  updateCompetitor: (tid, did, cid, data) =>
    apiFetch(`/tournaments/${tid}/divisions/${did}/competitors/${cid}`, {
      method: 'PUT', body: JSON.stringify(data),
    }),
  deleteCompetitor: (tid, did, cid) =>
    apiFetch(`/tournaments/${tid}/divisions/${did}/competitors/${cid}`, { method: 'DELETE' }),
  changeDivision: (tid, did, cid, data) =>
    apiFetch(`/tournaments/${tid}/divisions/${did}/competitors/${cid}/change-division`, {
      method: 'POST', body: JSON.stringify(data),
    }),

  // Bracket
  generateBracket: (tid, did, seeding = 'random', confirmRegenerate = false) =>
    apiFetch(`/tournaments/${tid}/divisions/${did}/bracket`, {
      method: 'POST',
      body: JSON.stringify({ seeding, confirm_regenerate: confirmRegenerate }),
    }),
  getBracket: (tid, did) =>
    apiFetch(`/tournaments/${tid}/divisions/${did}/bracket`),

  // Match actions
  recordResult: (tid, did, mid, data) =>
    apiFetch(`/tournaments/${tid}/divisions/${did}/matches/${mid}/result`, {
      method: 'POST', body: JSON.stringify(data),
    }),
  updateMatchStatus: (tid, did, mid, data) =>
    apiFetch(`/tournaments/${tid}/divisions/${did}/matches/${mid}/status`, {
      method: 'PUT', body: JSON.stringify(data),
    }),

  // Chaos
  withdrawal: (tid, did, mid, competitorId, reason) =>
    apiFetch(`/tournaments/${tid}/divisions/${did}/matches/${mid}/withdrawal?competitor_id=${competitorId}`, {
      method: 'POST', body: JSON.stringify({ reason }),
    }),
  noShow: (tid, did, mid, competitorId, reason) =>
    apiFetch(`/tournaments/${tid}/divisions/${did}/matches/${mid}/no-show?competitor_id=${competitorId}`, {
      method: 'POST', body: JSON.stringify({ reason: reason || 'No show' }),
    }),
  substitution: (tid, did, mid, competitorId, newCompetitor, reason) =>
    apiFetch(`/tournaments/${tid}/divisions/${did}/matches/${mid}/substitution?competitor_id=${competitorId}`, {
      method: 'POST', body: JSON.stringify({ new_competitor: newCompetitor, reason }),
    }),
  rollback: (tid, did, mid, reason) =>
    apiFetch(`/tournaments/${tid}/divisions/${did}/matches/${mid}/rollback?reason=${encodeURIComponent(reason)}`, {
      method: 'POST',
    }),
  correctResult: (tid, did, mid, data) =>
    apiFetch(`/tournaments/${tid}/divisions/${did}/matches/${mid}/correct`, {
      method: 'POST', body: JSON.stringify(data),
    }),

  // Scheduling
  getScheduleEstimate: (tid) => apiFetch(`/tournaments/${tid}/scheduling/estimate`),
  getRingQueue: (tid, ring) => apiFetch(`/tournaments/${tid}/scheduling/rings/${ring}`),
  reorderRing: (tid, ring, matchIds) =>
    apiFetch(`/tournaments/${tid}/scheduling/rings/${ring}/reorder`, {
      method: 'PUT', body: JSON.stringify({ match_ids: matchIds }),
    }),

  // Audit
  getAuditLog: (tid) => apiFetch(`/tournaments/${tid}/audit`),

  // Sync
  exportSnapshot: (tid) => apiFetch(`/sync/export/${tid}`, { method: 'POST' }),
  pushSync: (tid, targetUrl, apiKey) =>
    apiFetch(`/sync/push/${tid}`, {
      method: 'POST',
      body: JSON.stringify({ target_url: targetUrl, api_key: apiKey }),
    }),

  // Registration (self-signup)
  submitRegistration: (tid, data) =>
    apiFetch(`/tournaments/${tid}/registrations`, {
      method: 'POST', body: JSON.stringify(data),
    }),
  checkRegistration: (tid, email) =>
    apiFetch(`/tournaments/${tid}/registrations/check?email=${encodeURIComponent(email)}`),
  getRegistrations: (tid, status) =>
    apiFetch(`/tournaments/${tid}/registrations${status ? `?status=${status}` : ''}`),
  reviewRegistration: (tid, rid, action, adminNotes) =>
    apiFetch(`/tournaments/${tid}/registrations/${rid}/review`, {
      method: 'POST',
      body: JSON.stringify({ action, admin_notes: adminNotes || null }),
    }),
};

export default api;
