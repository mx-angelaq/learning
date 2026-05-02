import { useState, useCallback, useEffect } from 'react';
import api from '../utils/api';

function isTokenExpired(token) {
    if (!token) return true;
    try {
          const parts = token.split('.');
          if (parts.length !== 3) return true;
          const payload = JSON.parse(atob(parts[1]));
          if (!payload.exp) return false;
          const now = Math.floor(Date.now() / 1000);
          return payload.exp < now;
    } catch (e) {
          return true;
    }
}

export default function useAuth() {
    const [role, setRole] = useState(() => {
          const token = api.getToken();
          if (isTokenExpired(token)) {
                  api.clearAuth();
                  return null;
          }
          return api.getRole();
    });
    const [error, setError] = useState('');

  useEffect(() => {
        const checkExpiry = () => {
                const token = api.getToken();
                if (token && isTokenExpired(token)) {
                          api.clearAuth();
                          setRole(null);
                }
        };
        checkExpiry();
        const interval = setInterval(checkExpiry, 60000);
        const handleAuthError = () => {
                api.clearAuth();
                setRole(null);
        };
        window.addEventListener('auth:expired', handleAuthError);
        return () => {
                clearInterval(interval);
                window.removeEventListener('auth:expired', handleAuthError);
        };
  }, []);

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
