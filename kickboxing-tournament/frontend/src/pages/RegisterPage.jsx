import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../utils/api';

/**
 * Public self-registration page. No login required.
 * URL: /register/:tournamentId
 */
export default function RegisterPage() {
  const { id } = useParams();
  const [tournament, setTournament] = useState(null);
  const [divisions, setDivisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Check-status mode
  const [checkMode, setCheckMode] = useState(false);
  const [checkEmail, setCheckEmail] = useState('');
  const [checkResult, setCheckResult] = useState(null);

  const [form, setForm] = useState({
    full_name: '',
    email: '',
    division_id: '',
    declared_weight: '',
    gym_team: '',
    phone: '',
    age: '',
    experience_level: '',
    waiver_agreed: false,
  });

  useEffect(() => {
    async function load() {
      try {
        const [t, d] = await Promise.all([
          api.getTournament(id),
          api.getDivisions(id),
        ]);
        setTournament(t);
        setDivisions(d);
        if (d.length > 0) {
          setForm(f => ({ ...f, division_id: d[0].id }));
        }
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  const set = (k, v) => setForm({ ...form, [k]: v });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setSubmitting(true);
    try {
      const payload = {
        full_name: form.full_name,
        email: form.email,
        division_id: parseInt(form.division_id),
        declared_weight: form.declared_weight ? parseFloat(form.declared_weight) : null,
        gym_team: form.gym_team || null,
        phone: form.phone || null,
        age: form.age ? parseInt(form.age) : null,
        experience_level: form.experience_level || null,
        waiver_agreed: form.waiver_agreed,
      };
      await api.submitRegistration(id, payload);
      setSuccess(
        'Registration submitted successfully! Your registration is pending review by the tournament organizer. ' +
        'You will be added to the bracket once approved.'
      );
      setForm({
        full_name: '', email: '', division_id: divisions[0]?.id || '',
        declared_weight: '', gym_team: '', phone: '', age: '',
        experience_level: '', waiver_agreed: false,
      });
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleCheckStatus = async (e) => {
    e.preventDefault();
    setError('');
    setCheckResult(null);
    try {
      const result = await api.checkRegistration(id, checkEmail);
      setCheckResult(result);
    } catch (e) {
      setError(e.message);
    }
  };

  if (loading) return <div className="loading-center"><div className="spinner"></div></div>;

  if (!tournament) return (
    <div className="container">
      <div className="alert alert-error">Tournament not found.</div>
      <Link to="/" className="btn btn-outline">Back to Tournaments</Link>
    </div>
  );

  if (!tournament.registration_open) return (
    <div className="container">
      <div className="card text-center" style={{ padding: '3rem' }}>
        <h2>{tournament.name}</h2>
        <p className="text-light mt-1">Registration is not currently open for this tournament.</p>
        <p className="text-light">Contact the tournament organizer for more information.</p>
        <Link to={`/public/${id}`} className="btn btn-outline mt-1">View Brackets</Link>
      </div>
    </div>
  );

  return (
    <div style={{ maxWidth: 600, margin: '0 auto' }}>
      <div className="text-center mb-1">
        <h2>{tournament.name}</h2>
        <p className="text-light">{tournament.date} &middot; {tournament.venue}</p>
      </div>

      {/* Toggle between register and check status */}
      <div className="tabs" style={{ justifyContent: 'center' }}>
        <button className={`tab ${!checkMode ? 'active' : ''}`} onClick={() => { setCheckMode(false); setError(''); }}>
          Register
        </button>
        <button className={`tab ${checkMode ? 'active' : ''}`} onClick={() => { setCheckMode(true); setError(''); }}>
          Check Status
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {checkMode ? (
        <div className="card">
          <h3>Check Registration Status</h3>
          <form onSubmit={handleCheckStatus}>
            <div className="form-group">
              <label>Email Address</label>
              <input type="email" required value={checkEmail}
                onChange={e => setCheckEmail(e.target.value)}
                placeholder="Enter the email you registered with" />
            </div>
            <button type="submit" className="btn btn-primary">Check Status</button>
          </form>
          {checkResult && (
            <div className="mt-1" style={{ padding: '1rem', background: '#f8fafc', borderRadius: 'var(--radius)' }}>
              <p><strong>Name:</strong> {checkResult.full_name}</p>
              <p><strong>Division:</strong> {checkResult.division_name}</p>
              <p><strong>Status:</strong> <span className={`badge badge-${checkResult.status}`}>{checkResult.status}</span></p>
              {checkResult.admin_notes && <p><strong>Notes:</strong> {checkResult.admin_notes}</p>}
              <p className="text-sm text-light mt-1">
                Submitted: {checkResult.created_at ? new Date(checkResult.created_at).toLocaleString() : 'N/A'}
              </p>
            </div>
          )}
        </div>
      ) : (
        <div className="card">
          <h3>Competitor Registration</h3>
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label>Full Name *</label>
              <input required value={form.full_name} onChange={e => set('full_name', e.target.value)}
                placeholder="Your full name" maxLength={200} />
            </div>
            <div className="form-group">
              <label>Email *</label>
              <input type="email" required value={form.email} onChange={e => set('email', e.target.value)}
                placeholder="your@email.com" maxLength={200} />
              <span className="text-sm text-light">Used for registration confirmation and duplicate prevention</span>
            </div>
            <div className="form-group">
              <label>Division *</label>
              <select required value={form.division_id} onChange={e => set('division_id', e.target.value)}>
                {divisions.map(d => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                    {d.weight_class_min && d.weight_class_max ? ` (${d.weight_class_min}-${d.weight_class_max} kg)` : ''}
                    {d.gender ? ` - ${d.gender}` : ''}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Declared Weight (kg)</label>
                <input type="number" step="0.1" value={form.declared_weight}
                  onChange={e => set('declared_weight', e.target.value)}
                  placeholder="e.g., 70.5" />
              </div>
              <div className="form-group">
                <label>Gym / Team</label>
                <input value={form.gym_team} onChange={e => set('gym_team', e.target.value)}
                  placeholder="Your gym or team name" maxLength={200} />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Phone</label>
                <input value={form.phone} onChange={e => set('phone', e.target.value)}
                  placeholder="Optional" maxLength={50} />
              </div>
              <div className="form-group">
                <label>Age</label>
                <input type="number" min="5" max="99" value={form.age}
                  onChange={e => set('age', e.target.value)} placeholder="Optional" />
              </div>
            </div>
            <div className="form-group">
              <label>Experience Level</label>
              <select value={form.experience_level} onChange={e => set('experience_level', e.target.value)}>
                <option value="">Select (optional)</option>
                <option value="novice">Novice</option>
                <option value="intermediate">Intermediate</option>
                <option value="advanced">Advanced</option>
              </select>
            </div>
            <div className="form-group">
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input type="checkbox" checked={form.waiver_agreed}
                  onChange={e => set('waiver_agreed', e.target.checked)} />
                I agree to the tournament waiver and rules *
              </label>
            </div>
            <button type="submit" className="btn btn-primary btn-lg" disabled={submitting}
              style={{ width: '100%' }}>
              {submitting ? 'Submitting...' : 'Submit Registration'}
            </button>
          </form>
        </div>
      )}

      <div className="text-center mt-1">
        <Link to={`/public/${id}`} className="text-sm text-light">View tournament brackets</Link>
      </div>
    </div>
  );
}
