import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../utils/api';
import BracketView from '../components/BracketView';
import MatchActions from '../components/MatchActions';

export default function DivisionView({ isAdmin, isStaff }) {
  const { tid, did } = useParams();
  const [division, setDivision] = useState(null);
  const [competitors, setCompetitors] = useState([]);
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [tab, setTab] = useState('bracket');
  const [showAddComp, setShowAddComp] = useState(false);
  const [selectedMatch, setSelectedMatch] = useState(null);

  const load = useCallback(async () => {
    try {
      const [d, c, m] = await Promise.all([
        api.getDivision(tid, did),
        api.getCompetitors(tid, did),
        api.getBracket(tid, did).catch(() => []),
      ]);
      setDivision(d);
      setCompetitors(c);
      setMatches(m);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [tid, did]);

  useEffect(() => { load(); }, [load]);

  const clearMessages = () => { setError(''); setSuccess(''); };

  const handleGenerateBracket = async (seeding, confirmRegenerate) => {
    clearMessages();
    try {
      const result = await api.generateBracket(tid, did, seeding, confirmRegenerate);
      setMatches(result);
      setSuccess(`Bracket generated with ${result.length} matches.`);
      load();
    } catch (e) {
      if (e.message.includes('confirm_regenerate')) {
        if (window.confirm('Bracket already exists. Regenerating will DELETE all current results. Proceed?')) {
          handleGenerateBracket(seeding, true);
        }
      } else {
        setError(e.message);
      }
    }
  };

  if (loading) return <div className="loading-center"><div className="spinner"></div></div>;
  if (!division) return <div className="alert alert-error">Division not found</div>;

  return (
    <div>
      <div className="flex-between mb-1">
        <div>
          <Link to={`/tournament/${tid}`} className="text-sm text-light">&larr; Back to Tournament</Link>
          <h2>{division.name}</h2>
          <p className="text-sm text-light">
            {division.weight_class_min ? Math.round(division.weight_class_min * 2.20462) : '?'}-{division.weight_class_max ? Math.round(division.weight_class_max * 2.20462) : '?'} lbs
            {division.gender ? ` | ${division.gender}` : ''}
            &middot; {competitors.filter(c => c.status === 'active').length} active competitor(s)
          </p>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      <div className="tabs">
        {['bracket', 'competitors', 'matches'].map(t => (
          <button key={t} className={`tab ${tab === t ? 'active' : ''}`}
            onClick={() => { setTab(t); clearMessages(); }}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === 'bracket' && (
        <div>
          {isAdmin && (
            <div className="flex gap-sm mb-1 flex-wrap">
              <button className="btn btn-primary" onClick={() => handleGenerateBracket('random', false)}>
                Generate (Random)
              </button>
              <button className="btn btn-outline" onClick={() => handleGenerateBracket('separate_gyms', false)}>
                Generate (Separate Gyms)
              </button>
              <button className="btn btn-outline" onClick={() => handleGenerateBracket('manual', false)}>
                Generate (Manual Seeds)
              </button>
            </div>
          )}
          {matches.length === 0 ? (
            <div className="card text-center text-light" style={{ padding: '3rem' }}>
              No bracket generated yet. Add competitors and generate the bracket.
            </div>
          ) : (
            <BracketView matches={matches} onMatchClick={setSelectedMatch} />
          )}
        </div>
      )}

      {tab === 'competitors' && (
        <CompetitorsTab tid={tid} did={did} competitors={competitors}
          isAdmin={isAdmin} division={division}
          onRefresh={load} showAddComp={showAddComp}
          setShowAddComp={setShowAddComp}
          setError={setError} setSuccess={setSuccess} />
      )}

      {tab === 'matches' && (
        <MatchesTab matches={matches} isStaff={isStaff} isAdmin={isAdmin}
          tid={tid} did={did} onRefresh={load}
          setError={setError} setSuccess={setSuccess} />
      )}

      {selectedMatch && (
        <MatchActions match={selectedMatch} tid={tid} did={did}
          isAdmin={isAdmin} isStaff={isStaff} division={division}
          onClose={() => setSelectedMatch(null)}
          onRefresh={() => { setSelectedMatch(null); load(); }}
          setError={setError} setSuccess={setSuccess} />
      )}
    </div>
  );
}

function CompetitorsTab({ tid, did, competitors, isAdmin, division, onRefresh,
  showAddComp, setShowAddComp, setError, setSuccess }) {
  const [form, setForm] = useState({ full_name: '', declared_weight: '', gym_team: '' });

  const handleAdd = async (e) => {
    e.preventDefault();
    try {
      const weightLbs = form.declared_weight ? parseFloat(form.declared_weight) : null;
      await api.createCompetitor(tid, did, {
        full_name: form.full_name,
        declared_weight: weightLbs ? Math.round(weightLbs * 0.453592 * 10) / 10 : null,
        gym_team: form.gym_team || null,
        waiver_signed: true,
      });
      setForm({ full_name: '', declared_weight: '', gym_team: '' });
      setSuccess('Competitor added.');
      onRefresh();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleDelete = async (cid) => {
    if (!window.confirm('Remove this competitor?')) return;
    try {
      await api.deleteCompetitor(tid, did, cid);
      setSuccess('Competitor removed.');
      onRefresh();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div>
      {isAdmin && (
        <div className="card mb-1">
          <h3>Quick Add Competitor</h3>
          <form onSubmit={handleAdd} className="form-row" style={{ alignItems: 'end' }}>
            <div className="form-group">
              <label>Name *</label>
              <input required value={form.full_name} onChange={e => setForm({ ...form, full_name: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Weight (lbs)</label>
              <input type="number" step="0.1" value={form.declared_weight}
                onChange={e => setForm({ ...form, declared_weight: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Gym/Team</label>
              <input value={form.gym_team} onChange={e => setForm({ ...form, gym_team: e.target.value })} />
            </div>
            <div className="form-group">
              <button type="submit" className="btn btn-primary">Add</button>
            </div>
          </form>
        </div>
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Name</th><th>Weight</th><th>Gym</th><th>Seed</th><th>Status</th>
              {isAdmin && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {competitors.map(c => (
              <tr key={c.id}>
                <td>{c.full_name}</td>
                <td>{c.declared_weight ? `${Math.round(c.declared_weight * 2.20462)} lbs` : '-'}</td>
                <td>{c.gym_team || '-'}</td>
                <td>{c.seed || '-'}</td>
                <td><span className={`badge badge-${c.status}`}>{c.status}</span></td>
                {isAdmin && (
                  <td>
                    <button className="btn btn-sm btn-danger" onClick={() => handleDelete(c.id)}>
                      Remove
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MatchesTab({ matches, isStaff, isAdmin, tid, did, onRefresh, setError, setSuccess }) {
  const handleStatusChange = async (match, newStatus) => {
    try {
      await api.updateMatchStatus(tid, did, match.id, {
        status: newStatus,
        ring_number: match.ring_number,
      });
      setSuccess(`Match status updated to ${newStatus}.`);
      onRefresh();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleQuickResult = async (match, winnerId, method) => {
    try {
      await api.recordResult(tid, did, match.id, {
        winner_id: winnerId,
        result_method: method,
      });
      setSuccess('Result recorded.');
      onRefresh();
    } catch (e) {
      setError(e.message);
    }
  };

  const nonByeMatches = matches.filter(m => !m.is_bye);

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Round</th><th>Competitor 1</th><th>Competitor 2</th>
            <th>Status</th><th>Winner</th><th>Method</th>
            {isStaff && <th>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {nonByeMatches.map(m => (
            <tr key={m.id}>
              <td>R{m.round_number}</td>
              <td>{m.competitor1_name || 'TBD'}</td>
              <td>{m.competitor2_name || 'TBD'}</td>
              <td><span className={`badge badge-${m.status}`}>{m.status}</span></td>
              <td>{m.winner_name || '-'}</td>
              <td>{m.result_method || '-'}</td>
              {isStaff && (
                <td>
                  <div className="flex gap-sm flex-wrap">
                    {m.status === 'pending' && m.competitor1_id && m.competitor2_id && (
                      <>
                        <button className="btn btn-sm btn-outline"
                          onClick={() => handleStatusChange(m, 'queued')}>Queue</button>
                        <button className="btn btn-sm btn-outline"
                          onClick={() => handleStatusChange(m, 'in_progress')}>Start</button>
                      </>
                    )}
                    {(m.status === 'queued' || m.status === 'on_deck') && (
                      <button className="btn btn-sm btn-warning"
                        onClick={() => handleStatusChange(m, 'in_progress')}>Start</button>
                    )}
                    {m.status === 'in_progress' && (
                      <div className="flex gap-sm flex-wrap">
                        {m.competitor1_id && (
                          <button className="btn btn-sm btn-success"
                            onClick={() => handleQuickResult(m, m.competitor1_id, 'decision')}>
                            {m.competitor1_name} Wins
                          </button>
                        )}
                        {m.competitor2_id && (
                          <button className="btn btn-sm btn-success"
                            onClick={() => handleQuickResult(m, m.competitor2_id, 'decision')}>
                            {m.competitor2_name} Wins
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
