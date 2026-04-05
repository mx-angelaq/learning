import React, { useState } from 'react';

export default function LoginModal({ onLogin, onClose, error }) {
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('admin');

  const handleSubmit = (e) => {
    e.preventDefault();
    onLogin(password, role);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h2>Login</h2>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Role</label>
            <select value={role} onChange={e => setRole(e.target.value)}>
              <option value="admin">Admin / Organizer</option>
              <option value="staff">Staff / Scorekeeper</option>
            </select>
          </div>
          <div className="form-group">
            <label>Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)}
              autoFocus placeholder="Enter password" />
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-outline" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary">Login</button>
          </div>
        </form>
      </div>
    </div>
  );
}
