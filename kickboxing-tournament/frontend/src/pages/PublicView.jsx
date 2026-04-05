import React, { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import api from '../utils/api';
import BracketView from '../components/BracketView';
import useLiveUpdates from '../hooks/useLiveUpdates';

/**
 * Read-only public view. No login required.
 * Shows brackets, ring queues, and results.
 */
export default function PublicView() {
  const { id } = useParams();
  const [tournament, setTournament] = useState(null);
  const [divisions, setDivisions] = useState([]);
  const [selectedDiv, setSelectedDiv] = useState(null);
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(new Date());

  const load = useCallback(async () => {
    try {
      const [t, d] = await Promise.all([
        api.getTournament(id),
        api.getDivisions(id),
      ]);
      setTournament(t);
      setDivisions(d);
      if (d.length > 0 && !selectedDiv) {
        setSelectedDiv(d[0].id);
      }
      setLastUpdated(new Date());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (selectedDiv) {
      api.getBracket(id, selectedDiv).then(setMatches).catch(() => setMatches([]));
    }
  }, [selectedDiv, lastUpdated]);

  // Auto-refresh every 15 seconds
  useEffect(() => {
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, [load]);

  // Live updates via SSE
  useLiveUpdates(id, () => { load(); });

  if (loading) return <div className="loading-center"><div className="spinner"></div></div>;
  if (!tournament) return <div className="alert alert-error">Tournament not found</div>;

  const completedMatches = matches.filter(m => m.status === 'completed' && !m.is_bye);
  const inProgress = matches.filter(m => m.status === 'in_progress');

  return (
    <div>
      <div className="text-center mb-1">
        <h2>{tournament.name}</h2>
        <p className="text-light">{tournament.date} &middot; {tournament.venue}</p>
        <p className="text-sm text-light">
          Last updated: {lastUpdated.toLocaleTimeString()}
          &middot; Auto-refreshing
        </p>
      </div>

      {/* Division tabs */}
      <div className="tabs" style={{ justifyContent: 'center' }}>
        {divisions.map(d => (
          <button key={d.id}
            className={`tab ${selectedDiv === d.id ? 'active' : ''}`}
            onClick={() => setSelectedDiv(d.id)}>
            {d.name} ({d.competitor_count})
          </button>
        ))}
      </div>

      {/* Live matches */}
      {inProgress.length > 0 && (
        <div className="card mb-1" style={{ borderLeft: '4px solid var(--warning)' }}>
          <h3>LIVE NOW</h3>
          {inProgress.map(m => (
            <div key={m.id} className="queue-item" style={{ fontSize: '1.1rem', fontWeight: 600 }}>
              <span>{m.competitor1_name || 'TBD'} vs {m.competitor2_name || 'TBD'}</span>
              <span className="badge badge-in_progress">In Progress</span>
            </div>
          ))}
        </div>
      )}

      {/* Bracket */}
      {matches.length > 0 ? (
        <BracketView matches={matches} />
      ) : (
        <div className="card text-center text-light" style={{ padding: '3rem' }}>
          Bracket not yet generated for this division.
        </div>
      )}

      {/* Recent results */}
      {completedMatches.length > 0 && (
        <div className="card mt-1">
          <h3>Completed Results</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Round</th><th>Competitors</th><th>Winner</th><th>Method</th></tr>
              </thead>
              <tbody>
                {completedMatches.map(m => (
                  <tr key={m.id}>
                    <td>R{m.round_number}</td>
                    <td>{m.competitor1_name} vs {m.competitor2_name}</td>
                    <td style={{ fontWeight: 700 }}>{m.winner_name}</td>
                    <td>{m.result_method ? m.result_method.toUpperCase() : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
