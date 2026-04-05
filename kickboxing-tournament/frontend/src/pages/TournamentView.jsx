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
          <Link to={`/public/${id}`} className="btn btn-sm btn-outline">Public View</Link>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="tabs">
        {['divisions', 'schedule', 'audit'].map(t => (
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
                      ? `${d.weight_class_min}-${d.weight_class_max} kg`
                      : d.weight_class_max ? `Up to ${d.weight_class_max} kg` : d.weight_class_min ? `${d.weight_class_min}+ kg` : ''}
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
        weight_class_min: form.weight_class_min ? parseFloat(form.weight_class_min) : null,
        weight_class_max: form.weight_class_max ? parseFloat(form.weight_class_max) : null,
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
              <label>Min Weight (kg)</label>
              <input type="number" step="0.1" value={form.weight_class_min}
                onChange={e => set('weight_class_min', e.target.value)} />
            </div>
            <div className="form-group">
              <label>Max Weight (kg)</label>
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
