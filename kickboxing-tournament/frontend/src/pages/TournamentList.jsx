import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api from '../utils/api';

export default function TournamentList({ isAdmin }) {
  const [tournaments, setTournaments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const navigate = useNavigate();

  useEffect(() => { loadTournaments(); }, []);

  async function loadTournaments() {
    try {
      const data = await api.getTournaments();
      setTournaments(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <div className="loading-center"><div className="spinner"></div></div>;

  return (
    <div>
      <div className="flex-between mb-1">
        <h2>Tournaments</h2>
        {isAdmin && (
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            + New Tournament
          </button>
        )}
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {tournaments.length === 0 ? (
        <div className="card text-center text-light" style={{ padding: '3rem' }}>
          No tournaments yet. {isAdmin ? 'Create one to get started.' : 'Login as admin to create one.'}
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem' }}>
          {tournaments.map(t => (
            <div key={t.id} className="card" style={{ cursor: 'pointer' }}
              onClick={() => navigate(`/tournament/${t.id}`)}>
              <h3>{t.name}</h3>
              <p className="text-sm text-light">{t.date} &middot; {t.venue}</p>
              <p className="text-sm text-light">{t.num_rings} ring(s) &middot; Starts at {t.start_time}</p>
              <div className="mt-1 flex gap-sm">
                <Link to={`/tournament/${t.id}`} className="btn btn-sm btn-primary"
                  onClick={e => e.stopPropagation()}>Manage</Link>
                <Link to={`/public/${t.id}`} className="btn btn-sm btn-outline"
                  onClick={e => e.stopPropagation()}>Public View</Link>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <CreateTournamentModal
          onClose={() => setShowCreate(false)}
          onCreated={(t) => { setShowCreate(false); navigate(`/tournament/${t.id}`); }}
        />
      )}
    </div>
  );
}

function CreateTournamentModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    name: '', date: '', venue: '', num_rings: 1,
    start_time: '09:00', bout_duration_minutes: 3,
    break_duration_minutes: 2, buffer_minutes: 1,
    weighin_tolerance_kg: 0.5, substitution_cutoff_round: 1,
    no_show_policy: 'walkover',
  });
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const t = await api.createTournament(form);
      onCreated(t);
    } catch (e) {
      setError(e.message);
    }
  };

  const set = (k, v) => setForm({ ...form, [k]: v });

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h2>Create Tournament</h2>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Name *</label>
            <input required value={form.name} onChange={e => set('name', e.target.value)} />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Date *</label>
              <input type="date" required value={form.date} onChange={e => set('date', e.target.value)} />
            </div>
            <div className="form-group">
              <label>Start Time</label>
              <input type="time" value={form.start_time} onChange={e => set('start_time', e.target.value)} />
            </div>
          </div>
          <div className="form-group">
            <label>Venue *</label>
            <input required value={form.venue} onChange={e => set('venue', e.target.value)} />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Rings/Areas</label>
              <input type="number" min="1" max="20" value={form.num_rings}
                onChange={e => set('num_rings', parseInt(e.target.value) || 1)} />
            </div>
            <div className="form-group">
              <label>Bout Duration (min)</label>
              <input type="number" min="1" max="30" value={form.bout_duration_minutes}
                onChange={e => set('bout_duration_minutes', parseInt(e.target.value) || 3)} />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Break (min)</label>
              <input type="number" min="0" max="30" value={form.break_duration_minutes}
                onChange={e => set('break_duration_minutes', parseInt(e.target.value) || 0)} />
            </div>
            <div className="form-group">
              <label>Buffer (min)</label>
              <input type="number" min="0" max="15" value={form.buffer_minutes}
                onChange={e => set('buffer_minutes', parseInt(e.target.value) || 0)} />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label>Weigh-in Tolerance (kg)</label>
              <input type="number" step="0.1" min="0" value={form.weighin_tolerance_kg}
                onChange={e => set('weighin_tolerance_kg', parseFloat(e.target.value) || 0)} />
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
          <div className="modal-actions">
            <button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary">Create</button>
          </div>
        </form>
      </div>
    </div>
  );
}
