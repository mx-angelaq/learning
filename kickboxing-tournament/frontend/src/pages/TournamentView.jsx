import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import api from '../utils/api';
import useLiveUpdates from '../hooks/useLiveUpdates';

export default function TournamentView({ isAdmin, isStaff }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const [tournament, setTournament] = useState(null);
  const [divisions, setDivisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tab, setTab] = useState('divisions');
  const [showAddDiv, setShowAddDiv] = useState(false);
  const [auditLog, setAuditLog] = useState([]);
  const [schedule, setSchedule] = useState([]);

  const load = useCallback(async () => {
    try {
      const [t, d] = await Promise.all([
        api.getTournament(id),
        api.getDivisions(id),
      ]);
      setTournament(t);
      setDivisions(d);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  useLiveUpdates(id, () => { load(); });

  const loadAudit = async () => {
    try {
      const data = await api.getAuditLog(id);
      setAuditLog(data);
    } catch (e) { setError(e.message); }
  };

  const loadSchedule = async () => {
    try {
      const data = await api.getScheduleEstimate(id);
      setSchedule(data);
    } catch (e) { setError(e.message); }
  };

  useEffect(() => {
    if (tab === 'audit') loadAudit();
    if (tab === 'schedule') loadSchedule();
  }, [tab]);

  if (loading) return <div className="loading-center"><div className="spinner"></div></div>;
  if (!tournament) return <div className="alert alert-error">Tournament not found</div>;

  return (
    <div>
      <div className="flex-between mb-1">
        <div>
          <h2>{tournament.name}</h2>
          <p className="text-sm text-light">
            {tournament.date} &middot; {tournament.venue} &middot; {tournament.num_rings} ring(s) &middot; Start: {tournament.start_time}
          </p>
        </div>
        <div className="flex gap-sm">
          <Link to={`/register/${id}`} className="btn btn-sm btn-success">Registration Link</Link>
          <Link to={`/public/${id}`} className="btn btn-sm btn-outline">Public View</Link>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="tabs">
        {['divisions', ...(isAdmin ? ['registrations', 'settings'] : []), 'schedule', 'audit'].map(t => (
          <button key={t} className={`tab ${tab === t ? 'active' : ''}`}
            onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === 'divisions' && (
        <div>
          {isAdmin && (
            <div className="mb-1">
              <button className="btn btn-primary" onClick={() => setShowAddDiv(true)}>
                + Add Division
              </button>
            </div>
          )}
          {divisions.length === 0 ? (
            <div className="card text-center text-light">No divisions yet.</div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
              {divisions.map(d => (
                <div key={d.id} className="card" style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/tournament/${id}/division/${d.id}`)}>
                  <h3>{d.name}</h3>
                  <p className="text-sm text-light">
                    {d.weight_class_min && d.weight_class_max
                      ? `${Math.round(d.weight_class_min * 2.20462)}-${Math.round(d.weight_class_max * 2.20462)} lbs`
                      : d.weight_class_max ? `Up to ${Math.round(d.weight_class_max * 2.20462)} lbs` : d.weight_class_min ? `${Math.round(d.weight_class_min * 2.20462)}+ lbs` : ''}
                    {d.gender ? ` | ${d.gender}` : ''}
                    {d.experience_level ? ` | ${d.experience_level}` : ''}
                  </p>
                  <p className="text-sm mt-1">
                    {d.competitor_count} competitor(s)
                    {d.bracket_generated && <span className="badge badge-active" style={{ marginLeft: '0.5rem' }}>Bracket</span>}
                    {d.bracket_started && <span className="badge badge-in_progress" style={{ marginLeft: '0.5rem' }}>Started</span>}
                  </p>
                </div>
              ))}
            </div>
          )}

          {showAddDiv && (
            <AddDivisionModal
              tournamentId={id}
              onClose={() => setShowAddDiv(false)}
              onCreated={() => { setShowAddDiv(false); load(); }}
            />
          )}
        </div>
      )}

      {tab === 'registrations' && isAdmin && (
        <RegistrationsTab tournamentId={id} tournament={tournament} onRefresh={load} />
      )}

      {tab === 'settings' && isAdmin && (
        <SettingsTab tournament={tournament} onSaved={load} />
      )}

      {tab === 'schedule' && (
        <ScheduleTab tournamentId={id} tournament={tournament} schedule={schedule}
          isStaff={isStaff} onRefresh={loadSchedule} />
      )}

      {tab === 'audit' && (
        <div>
          <h3>Audit Log</h3>
          {auditLog.length === 0 ? (
            <p className="text-light">No audit entries yet.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Time</th><th>Action</th><th>Type</th><th>ID</th><th>By</th><th>Reason</th><th>Details</th></tr>
                </thead>
                <tbody>
                  {auditLog.map(a => (
                    <tr key={a.id}>
                      <td className="text-sm">{a.created_at ? new Date(a.created_at).toLocaleString() : ''}</td>
                      <td><span className="badge badge-pending">{a.action}</span></td>
                      <td>{a.entity_type}</td>
                      <td>{a.entity_id}</td>
                      <td>{a.performed_by}</td>
                      <td className="text-sm">{a.reason || '-'}</td>
                      <td className="text-sm">{a.details ? JSON.stringify(a.details) : '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AddDivisionModal({ tournamentId, onClose, onCreated }) {
  const [form, setForm] = useState({
    name: '', weight_class_min: '', weight_class_max: '',
    gender: '', age_group: '', experience_level: '',
  });
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const data = {
        ...form,
        weight_class_min: form.weight_class_min ? Math.round(parseFloat(form.weight_class_min) * 0.453592 * 10) / 10 : null,
        weight_class_max: form.weight_class_max ? Math.round(parseFloat(form.weight_class_max) * 0.453592 * 10) / 10 : null,
        gender: form.gender || null,
        age_group: form.age_group || null,
        experience_level: form.experience_level || null,
      };
      await api.createDivision(tournamentId, data);
      onCreated();
    } catch (e) {
      setError(e.message);
    }
  };

  const set = (k, v) => setForm({ ...form, [k]: v });

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h2>Add Division</h2>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Name *</label>
            <input required value={form.name} onChange={e => set('name', e.target.value)}
              placeholder="e.g., Men's Lightweight" />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Min Weight (lbs)</label>
              <input type="number" step="0.1" value={form.weight_class_min}
                onChange={e => set('weight_class_min', e.target.value)} />
            </div>
            <div className="form-group">
              <label>Max Weight (lbs)</label>
              <input type="number" step="0.1" value={form.weight_class_max}
                onChange={e => set('weight_class_max', e.target.value)} />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Gender</label>
              <select value={form.gender} onChange={e => set('gender', e.target.value)}>
                <option value="">Any</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </div>
            <div className="form-group">
              <label>Experience Level</label>
              <select value={form.experience_level} onChange={e => set('experience_level', e.target.value)}>
                <option value="">Any</option>
                <option value="novice">Novice</option>
                <option value="intermediate">Intermediate</option>
                <option value="advanced">Advanced</option>
                <option value="open">Open</option>
              </select>
            </div>
          </div>
          <div className="form-group">
            <label>Age Group</label>
            <input value={form.age_group} onChange={e => set('age_group', e.target.value)}
              placeholder="e.g., 18-35, Youth, Masters" />
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary">Create</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ScheduleTab({ tournamentId, tournament, schedule, isStaff, onRefresh }) {
  const rings = tournament ? Array.from({ length: tournament.num_rings }, (_, i) => i + 1) : [];
  const [ringQueues, setRingQueues] = useState({});

  useEffect(() => {
    rings.forEach(async (ring) => {
      try {
        const data = await api.getRingQueue(tournamentId, ring);
        setRingQueues(prev => ({ ...prev, [ring]: data }));
      } catch (e) { /* ignore */ }
    });
  }, [schedule]);

  return (
    <div>
      <div className="flex-between mb-1">
        <h3>Schedule &amp; Ring Queues</h3>
        <button className="btn btn-sm btn-outline" onClick={onRefresh}>Refresh Schedule</button>
      </div>
      <div className="ring-queue">
        {rings.map(ring => {
          const q = ringQueues[ring] || { in_progress: [], on_deck: [], queued: [], completed: [] };
          return (
            <div key={ring} className="card">
              <h3>Ring {ring}</h3>
              <div className="queue-section">
                <h4>In Progress</h4>
                {q.in_progress.length === 0 ? <p className="text-sm text-light">None</p> :
                  q.in_progress.map(m => (
                    <div key={m.id} className="queue-item">
                      <span>{m.competitor1_name} vs {m.competitor2_name}</span>
                      <span className="badge badge-in_progress">Live</span>
                    </div>
                  ))
                }
              </div>
              <div className="queue-section mt-1">
                <h4>On Deck</h4>
                {q.on_deck.length === 0 ? <p className="text-sm text-light">None</p> :
                  q.on_deck.map(m => (
                    <div key={m.id} className="queue-item">
                      <span>{m.competitor1_name} vs {m.competitor2_name}</span>
                      <span className="text-sm text-light">{m.scheduled_time || ''}</span>
                    </div>
                  ))
                }
              </div>
              <div className="queue-section mt-1">
                <h4>Queued ({q.queued.length})</h4>
                {q.queued.slice(0, 5).map(m => (
                  <div key={m.id} className="queue-item">
                    <span>{m.competitor1_name} vs {m.competitor2_name}</span>
                    <span className="text-sm text-light">{m.scheduled_time || ''}</span>
                  </div>
                ))}
                {q.queued.length > 5 && <p className="text-sm text-light">+{q.queued.length - 5} more</p>}
              </div>
              <div className="queue-section mt-1">
                <h4>Completed ({q.completed.length})</h4>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RegistrationsTab({ tournamentId, tournament, onRefresh }) {
  const [registrations, setRegistrations] = useState([]);
  const [filter, setFilter] = useState('pending');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [reviewNotes, setReviewNotes] = useState({});

  const loadRegs = async () => {
    try {
      const data = await api.getRegistrations(tournamentId, filter === 'all' ? '' : filter);
      setRegistrations(data);
    } catch (e) {
      setError(e.message);
    }
  };

  useEffect(() => { loadRegs(); }, [filter]);

  const handleReview = async (regId, action) => {
    setError('');
    setSuccess('');
    try {
      await api.reviewRegistration(tournamentId, regId, action, reviewNotes[regId] || '');
      setSuccess(`Registration ${action === 'approve' ? 'approved' : 'rejected'}.`);
      loadRegs();
      if (action === 'approve') onRefresh();
    } catch (e) {
      setError(e.message);
    }
  };

  const pendingCount = registrations.filter(r => r.status === 'pending').length;

  return (
    <div>
      <div className="flex-between mb-1 flex-wrap gap-sm">
        <h3>Registrations {filter === 'pending' && pendingCount > 0 && `(${pendingCount} pending)`}</h3>
        <div className="flex gap-sm">
          {['pending', 'approved', 'rejected', 'all'].map(f => (
            <button key={f} className={`btn btn-sm ${filter === f ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => setFilter(f)}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {registrations.length === 0 ? (
        <div className="card text-center text-light" style={{ padding: '2rem' }}>
          No {filter !== 'all' ? filter : ''} registrations.
          {!tournament.registration_open && (
            <p className="mt-1">Registration is currently closed. Enable it in tournament settings.</p>
          )}
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th><th>Email</th><th>Division</th><th>Weight</th>
                <th>Gym</th><th>Status</th><th>Submitted</th>
                {filter === 'pending' && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {registrations.map(r => (
                <tr key={r.id}>
                  <td>{r.full_name}</td>
                  <td className="text-sm">{r.email}</td>
                  <td>{r.division_name || `Division #${r.division_id}`}</td>
                  <td>{r.declared_weight ? `${Math.round(r.declared_weight * 2.20462)} lbs` : '-'}</td>
                  <td>{r.gym_team || '-'}</td>
                  <td><span className={`badge badge-${r.status}`}>{r.status}</span></td>
                  <td className="text-sm">{r.created_at ? new Date(r.created_at).toLocaleString() : ''}</td>
                  {filter === 'pending' && (
                    <td>
                      <div className="flex gap-sm" style={{ alignItems: 'center' }}>
                        <input
                          placeholder="Notes"
                          value={reviewNotes[r.id] || ''}
                          onChange={e => setReviewNotes({ ...reviewNotes, [r.id]: e.target.value })}
                          style={{ width: '100px', padding: '0.25rem 0.5rem', fontSize: '0.8rem' }}
                        />
                        <button className="btn btn-sm btn-success" onClick={() => handleReview(r.id, 'approve')}>
                          Approve
                        </button>
                        <button className="btn btn-sm btn-danger" onClick={() => handleReview(r.id, 'reject')}>
                          Reject
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function SettingsTab({ tournament, onSaved }) {
  const [form, setForm] = useState({
    name: tournament.name,
    date: tournament.date,
    venue: tournament.venue,
    num_rings: tournament.num_rings,
    start_time: tournament.start_time,
    bout_duration_minutes: tournament.bout_duration_minutes,
    break_duration_minutes: tournament.break_duration_minutes,
    buffer_minutes: tournament.buffer_minutes,
    weighin_tolerance_lbs: Math.round(tournament.weighin_tolerance_kg * 2.20462 * 10) / 10,
    substitution_cutoff_round: tournament.substitution_cutoff_round,
    no_show_policy: tournament.no_show_policy,
    registration_open: tournament.registration_open,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const set = (k, v) => { setForm({ ...form, [k]: v }); setSuccess(''); };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setSaving(true);
    try {
      const { weighin_tolerance_lbs, ...rest } = form;
      await api.updateTournament(tournament.id, {
        ...rest,
        weighin_tolerance_kg: Math.round(weighin_tolerance_lbs * 0.453592 * 10) / 10,
      });
      setSuccess('Settings saved.');
      onSaved();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <h3>Tournament Settings</h3>
      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      <form onSubmit={handleSubmit}>
        <div className="card">
          <h3>Registration</h3>
          <div className="form-group">
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
              <input type="checkbox" checked={form.registration_open}
                onChange={e => set('registration_open', e.target.checked)} />
              Open registrations (allow public self-registration)
            </label>
            <p className="text-sm text-light" style={{ marginTop: '0.25rem' }}>
              {form.registration_open
                ? 'Competitors can register via the public registration link.'
                : 'Registration is closed. Competitors cannot self-register.'}
            </p>
          </div>
        </div>

        <div className="card">
          <h3>General</h3>
          <div className="form-group">
            <label>Tournament Name</label>
            <input required value={form.name} onChange={e => set('name', e.target.value)} />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Date</label>
              <input type="date" required value={form.date} onChange={e => set('date', e.target.value)} />
            </div>
            <div className="form-group">
              <label>Start Time</label>
              <input type="time" value={form.start_time} onChange={e => set('start_time', e.target.value)} />
            </div>
          </div>
          <div className="form-group">
            <label>Venue</label>
            <input required value={form.venue} onChange={e => set('venue', e.target.value)} />
          </div>
          <div className="form-group">
            <label>Number of Rings</label>
            <input type="number" min="1" max="20" value={form.num_rings}
              onChange={e => set('num_rings', parseInt(e.target.value) || 1)} />
          </div>
        </div>

        <div className="card">
          <h3>Timing</h3>
          <div className="form-row">
            <div className="form-group">
              <label>Bout Duration (min)</label>
              <input type="number" min="1" max="30" value={form.bout_duration_minutes}
                onChange={e => set('bout_duration_minutes', parseInt(e.target.value) || 3)} />
            </div>
            <div className="form-group">
              <label>Break Between Bouts (min)</label>
              <input type="number" min="0" max="30" value={form.break_duration_minutes}
                onChange={e => set('break_duration_minutes', parseInt(e.target.value) || 0)} />
            </div>
            <div className="form-group">
              <label>Buffer (min)</label>
              <input type="number" min="0" max="15" value={form.buffer_minutes}
                onChange={e => set('buffer_minutes', parseInt(e.target.value) || 0)} />
            </div>
          </div>
        </div>

        <div className="card">
          <h3>Rules</h3>
          <div className="form-row">
            <div className="form-group">
              <label>Weigh-in Tolerance (lbs)</label>
              <input type="number" step="0.1" min="0" value={form.weighin_tolerance_lbs}
                onChange={e => set('weighin_tolerance_lbs', parseFloat(e.target.value) || 0)} />
            </div>
            <div className="form-group">
              <label>Substitution Cutoff Round</label>
              <input type="number" min="1" value={form.substitution_cutoff_round}
                onChange={e => set('substitution_cutoff_round', parseInt(e.target.value) || 1)} />
            </div>
            <div className="form-group">
              <label>No-Show Policy</label>
              <select value={form.no_show_policy} onChange={e => set('no_show_policy', e.target.value)}>
                <option value="walkover">Walkover</option>
                <option value="dq">Disqualification</option>
                <option value="reschedule">Reschedule</option>
              </select>
            </div>
          </div>
        </div>

        <button type="submit" className="btn btn-primary btn-lg" disabled={saving}>
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
      </form>
    </div>
  );
}
