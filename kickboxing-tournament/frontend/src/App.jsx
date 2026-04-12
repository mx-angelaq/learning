import React from 'react';
import { Routes, Route, Link, useNavigate } from 'react-router-dom';
import useAuth from './hooks/useAuth';
import TournamentList from './pages/TournamentList';
import TournamentView from './pages/TournamentView';
import DivisionView from './pages/DivisionView';
import PublicView from './pages/PublicView';
import RegisterPage from './pages/RegisterPage';
import LoginModal from './components/LoginModal';

export default function App() {
  const { role, login, logout, error, isAdmin, isStaff } = useAuth();
  const [showLogin, setShowLogin] = React.useState(false);
  const navigate = useNavigate();

  return (
    <div className="app">
      <nav className="navbar">
        <Link to="/" style={{ textDecoration: 'none', color: 'white' }}>
          <h1>Kickboxing Tournament Tracker</h1>
        </Link>
        <div className="nav-links">
          <Link to="/">Tournaments</Link>
          {role ? (
            <>
              <span className="text-sm" style={{ opacity: 0.7 }}>({role})</span>
              <button className="btn btn-sm btn-outline" style={{ color: 'white', borderColor: 'white' }}
                onClick={logout}>Logout</button>
            </>
          ) : (
            <button className="btn btn-sm btn-outline" style={{ color: 'white', borderColor: 'white' }}
              onClick={() => setShowLogin(true)}>Login</button>
          )}
        </div>
      </nav>

      <div className="container">
        <Routes>
          <Route path="/" element={<TournamentList isAdmin={isAdmin} />} />
          <Route path="/tournament/:id" element={<TournamentView isAdmin={isAdmin} isStaff={isStaff} />} />
          <Route path="/tournament/:tid/division/:did" element={<DivisionView isAdmin={isAdmin} isStaff={isStaff} />} />
          <Route path="/public/:id" element={<PublicView />} />
          <Route path="/register/:id" element={<RegisterPage />} />
        </Routes>
      </div>

      {showLogin && (
        <LoginModal
          onLogin={async (password, loginRole) => {
            const ok = await login(password, loginRole);
            if (ok) setShowLogin(false);
          }}
          onClose={() => setShowLogin(false)}
          error={error}
        />
      )}
    </div>
  );
}
