import { useState, useCallback } from 'react';
import api from '../utils/api';

export default function useAuth() {
  const [role, setRole] = useState(api.getRole());
  const [error, setError] = useState('');

  const login = useCallback(async (password, loginRole) => {
    setError('');
    try {
      const res = await api.login(password, loginRole);
      api.setAuth(res.access_token, res.role);
      setRole(res.role);
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    }
  }, []);

  const logout = useCallback(() => {
    api.clearAuth();
    setRole(null);
  }, []);

  return { role, login, logout, error, isAdmin: role === 'admin', isStaff: role === 'staff' || role === 'admin' };
}
