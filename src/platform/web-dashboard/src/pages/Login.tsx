import React, { useState } from 'react';
import { Video } from 'lucide-react';

export const Login: React.FC = () => {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();

    // Simple password check (in production, this should be a real API call)
    if (password === 'admin' || password === 'footballvision') {
      localStorage.setItem('access_token', 'demo-token');
      window.location.href = '/';
    } else {
      setError('Invalid password');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 to-gray-800 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl p-8 w-full max-w-md">
        <div className="flex items-center justify-center mb-8">
          <Video className="w-12 h-12 text-green-500 mr-3" />
          <h1 className="text-3xl font-bold text-gray-900">FootballVision Pro</h1>
        </div>

        <form onSubmit={handleLogin} className="space-y-6">
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
              Password
            </label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent"
              placeholder="Enter password"
              autoFocus
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="w-full bg-green-500 hover:bg-green-600 text-white font-semibold py-3 rounded-lg transition-colors"
          >
            Sign In
          </button>

          <p className="text-xs text-gray-500 text-center">
            Demo: Use 'admin' or 'footballvision' as password
          </p>
        </form>
      </div>
    </div>
  );
};
