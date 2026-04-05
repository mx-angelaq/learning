import React from 'react';

/**
 * Visual bracket display. Groups matches by round and renders
 * the standard single-elimination bracket layout.
 */
export default function BracketView({ matches, onMatchClick }) {
  if (!matches || matches.length === 0) {
    return <p className="text-light">No bracket data.</p>;
  }

  // Group by round
  const rounds = {};
  let maxRound = 0;
  matches.forEach(m => {
    if (!rounds[m.round_number]) rounds[m.round_number] = [];
    rounds[m.round_number].push(m);
    maxRound = Math.max(maxRound, m.round_number);
  });

  // Sort each round by position
  Object.values(rounds).forEach(r => r.sort((a, b) => a.position - b.position));

  const roundNames = (round, total) => {
    if (round === total) return 'Final';
    if (round === total - 1) return 'Semifinals';
    if (round === total - 2) return 'Quarterfinals';
    return `Round ${round}`;
  };

  return (
    <div className="bracket-container">
      <div className="bracket">
        {Array.from({ length: maxRound }, (_, i) => i + 1).map(rnd => (
          <div key={rnd} className="bracket-round">
            <div className="bracket-round-title">{roundNames(rnd, maxRound)}</div>
            {(rounds[rnd] || []).map(match => (
              <div
                key={match.id}
                className={`bracket-match ${match.status} ${match.is_bye ? 'bye' : ''}`}
                onClick={() => !match.is_bye && onMatchClick && onMatchClick(match)}
                title={match.is_bye ? 'Bye' : `Click for match actions`}
              >
                <div className={`match-competitor ${match.winner_id === match.competitor1_id ? 'winner' : ''} ${!match.competitor1_name ? 'tbd' : ''}`}>
                  <span>{match.competitor1_name || 'TBD'}</span>
                  {match.winner_id === match.competitor1_id && <span>&#10003;</span>}
                </div>
                <div className={`match-competitor ${match.winner_id === match.competitor2_id ? 'winner' : ''} ${!match.competitor2_name ? 'tbd' : ''}`}>
                  <span>{match.competitor2_name || 'TBD'}</span>
                  {match.winner_id === match.competitor2_id && <span>&#10003;</span>}
                </div>
                {match.result_method && (
                  <div style={{ padding: '0.125rem 0.75rem', fontSize: '0.7rem', color: '#64748b', textAlign: 'center', borderTop: '1px solid #e2e8f0' }}>
                    {match.result_method.toUpperCase()}
                  </div>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
