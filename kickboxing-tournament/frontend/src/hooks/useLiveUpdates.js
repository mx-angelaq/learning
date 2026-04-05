import { useEffect, useRef } from 'react';

export default function useLiveUpdates(tournamentId, onEvent) {
  const esRef = useRef(null);

  useEffect(() => {
    if (!tournamentId) return;

    const es = new EventSource(`/api/events/${tournamentId}`);
    esRef.current = es;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type !== 'keepalive' && onEvent) {
          onEvent(data);
        }
      } catch (e) {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      // Reconnect is automatic with EventSource
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [tournamentId, onEvent]);
}
