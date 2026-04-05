import React, { useState } from 'react';
import api from '../utils/api';

/**
 * Modal for match actions: record result, withdrawal, no-show,
 * substitution, rollback, correction.
 */
export default function MatchActions({ match, tid, did, isAdmin, isStaff,
  division, onClose, onRefresh, setError, setSuccess }) {
  const [action, setAction] = useState('result');
  const [resultMethod, setResultMethod] = useState('decision');
  const [winnerId, setWinnerId] = useState(match.competitor1_id || '');
  const [reason, setReason] = useState('');
  const [subName, setSubName] = useState('');
  const [subWeight, setSubWeight] = useState('');
  const [subGym, setSubGym] = useState('');
  const [targetCompetitor, setTargetCompetitor] = useState(match.competitor1_id || '');
  const [loading, setLoading] = useState(false);

  const methods = ['decision', 'ko', 'tko', 'dq', 'withdrawal', 'walkover', 'no_contest'];

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      switch (action) {
        case 'result':
          await api.recordResult(tid, did, match.id, {
            winner_id: parseInt(winnerId),
            result_method: resultMethod,
            notes: reason || undefined,
          });
          setSuccess('Result recorded successfully.');
          break;

        case 'withdrawal':
          await api.withdrawal(tid, did, match.id, parseInt(targetCompetitor), reason);
          setSuccess('Withdrawal processed. Opponent advances.');
          break;

        case 'no_show':
          await api.noShow(tid, did, match.id, parseInt(targetCompetitor), reason);
          setSuccess('No-show processed.');
          break;

        case 'substitution':
          if (!subName.trim()) { setError('Substitute name is required.'); return; }
          await api.substitution(tid, did, match.id, parseInt(targetCompetitor), {
            full_name: subName,
            declared_weight: subWeight ? parseFloat(subWeight) : null,
            gym_team: subGym || null,
          }, reason);
          setSuccess('Substitution complete.');
          break;

        case 'rollback':
          if (!reason.trim()) { setError('Reason is required for rollback.'); return; }
          await api.rollback(tid, did, match.id, reason);
          setSuccess('Result rolled back.');
          break;

        case 'correction':
          if (!reason.trim()) { setError('Reason is required for correction.'); return; }
          await api.correctResult(tid, did, match.id, {
            correct_winner_id: parseInt(winnerId),
            result_method: resultMethod,
            reason: reason,
          });
          setSuccess('Result corrected.');
          break;

        case 'status':
          await api.updateMatchStatus(tid, did, match.id, {
            status: resultMethod, // reusing field for status
            ring_number: match.ring_number,
          });
          setSuccess('Status updated.');
          break;
      }
      onRefresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const canAct = isStaff || isAdmin;
  const statuses = ['pending', 'queued', 'on_deck', 'in_progress'];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h2>Match: {match.competitor1_name || 'TBD'} vs {match.competitor2_name || 'TBD'}</h2>
        <p className="text-sm text-light mb-1">
          Round {match.round_number} &middot; Status: <span className={`badge badge-${match.status}`}>{match.status}</span>
        </p>

        {!canAct ? (
          <p className="text-light">Login as admin or staff to manage this match.</p>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label>Action</label>
              <select value={action} onChange={e => setAction(e.target.value)}>
                {match.status !== 'completed' && <option value="result">Record Result</option>}
                {match.status !== 'completed' && <option value="status">Change Status</option>}
                <option value="withdrawal">Withdrawal/Injury</option>
                <option value="no_show">No-Show</option>
                {isAdmin && <option value="substitution">Substitution</option>}
                {isAdmin && match.status === 'completed' && <option value="rollback">Rollback Result</option>}
                {isAdmin && match.status === 'completed' && <option value="correction">Correct Result</option>}
              </select>
            </div>

            {(action === 'result' || action === 'correction') && (
              <>
                <div className="form-group">
                  <label>Winner</label>
                  <select value={winnerId} onChange={e => setWinnerId(e.target.value)}>
                    {match.competitor1_id && <option value={match.competitor1_id}>{match.competitor1_name}</option>}
                    {match.competitor2_id && <option value={match.competitor2_id}>{match.competitor2_name}</option>}
                  </select>
                </div>
                <div className="form-group">
                  <label>Method</label>
                  <select value={resultMethod} onChange={e => setResultMethod(e.target.value)}>
                    {methods.map(m => <option key={m} value={m}>{m.toUpperCase()}</option>)}
                  </select>
                </div>
              </>
            )}

            {action === 'status' && (
              <div className="form-group">
                <label>New Status</label>
                <select value={resultMethod} onChange={e => setResultMethod(e.target.value)}>
                  {statuses.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            )}

            {(action === 'withdrawal' || action === 'no_show' || action === 'substitution') && (
              <div className="form-group">
                <label>Affected Competitor</label>
                <select value={targetCompetitor} onChange={e => setTargetCompetitor(e.target.value)}>
                  {match.competitor1_id && <option value={match.competitor1_id}>{match.competitor1_name}</option>}
                  {match.competitor2_id && <option value={match.competitor2_id}>{match.competitor2_name}</option>}
                </select>
              </div>
            )}

            {action === 'substitution' && (
              <div className="card" style={{ background: '#f8fafc' }}>
                <h4 className="text-sm">Replacement Competitor</h4>
                <div className="form-group">
                  <label>Name *</label>
                  <input required value={subName} onChange={e => setSubName(e.target.value)} />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Weight (kg)</label>
                    <input type="number" step="0.1" value={subWeight}
                      onChange={e => setSubWeight(e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label>Gym</label>
                    <input value={subGym} onChange={e => setSubGym(e.target.value)} />
                  </div>
                </div>
              </div>
            )}

            {(action !== 'result' && action !== 'status') && (
              <div className="form-group">
                <label>Reason {(action === 'rollback' || action === 'correction') ? '*' : ''}</label>
                <textarea rows="2" value={reason} onChange={e => setReason(e.target.value)}
                  placeholder="Explain the action..." />
              </div>
            )}

            {action === 'result' && (
              <div className="form-group">
                <label>Notes (optional)</label>
                <textarea rows="2" value={reason} onChange={e => setReason(e.target.value)}
                  placeholder="Optional notes..." />
              </div>
            )}

            <div className="modal-actions">
              <button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button>
              <button type="submit" className="btn btn-primary" disabled={loading}>
                {loading ? 'Processing...' : 'Submit'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
