'use client';

import { useState, useEffect } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [passwordStrength, setPasswordStrength] = useState<'weak' | 'medium' | 'strong' | null>(
    null
  );
  const router = useRouter();
  const supabase = createClient();

  // Password strength checker for signup
  useEffect(() => {
    if (mode !== 'signup' || password.length === 0) {
      setPasswordStrength(null);
      return;
    }

    let strength: 'weak' | 'medium' | 'strong' = 'weak';
    const hasLength = password.length >= 8;
    const hasUpperCase = /[A-Z]/.test(password);
    const hasLowerCase = /[a-z]/.test(password);
    const hasNumbers = /\d/.test(password);
    const hasSpecialChar = /[!@#$%^&*(),.?":{}|<>]/.test(password);

    const criteriaCount = [hasLength, hasUpperCase, hasLowerCase, hasNumbers, hasSpecialChar].filter(
      Boolean
    ).length;

    if (criteriaCount >= 4) strength = 'strong';
    else if (criteriaCount >= 3) strength = 'medium';

    setPasswordStrength(strength);
  }, [password, mode]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setMessage('');
    setLoading(true);

    try {
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (error) {
        if (error.message.includes('Invalid login credentials')) {
          throw new Error('Invalid email or password. Please try again.');
        }
        throw error;
      }

      router.push('/home');
      router.refresh();
    } catch (err: any) {
      setError(err.message || 'Failed to login');
    } finally {
      setLoading(false);
    }
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setMessage('');

    // Validation
    if (password.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }

    if (passwordStrength === 'weak') {
      setError('Please choose a stronger password (add uppercase, numbers, or special characters)');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);

    try {
      const { error, data } = await supabase.auth.signUp({
        email,
        password,
        options: {
          emailRedirectTo: `${typeof window !== 'undefined' ? window.location.origin : ''}/auth/callback`,
        },
      });

      if (error) throw error;

      // Check if email confirmation is required
      if (data.user && !data.session) {
        setMessage(
          '✉️ Please check your email to verify your account before logging in. The verification link will expire in 24 hours.'
        );
        setMode('login');
        setPassword('');
        setConfirmPassword('');
      } else {
        // Auto-login if email confirmation is disabled
        router.push('/home');
        router.refresh();
      }
    } catch (err: any) {
      if (err.message.includes('User already registered')) {
        setError('This email is already registered. Please login instead.');
      } else {
        setError(err.message || 'Failed to sign up');
      }
    } finally {
      setLoading(false);
    }
  };

  const getStrengthColor = () => {
    switch (passwordStrength) {
      case 'weak':
        return 'bg-red-500';
      case 'medium':
        return 'bg-yellow-500';
      case 'strong':
        return 'bg-green-500';
      default:
        return 'bg-gray-300';
    }
  };

  const getStrengthWidth = () => {
    switch (passwordStrength) {
      case 'weak':
        return 'w-1/3';
      case 'medium':
        return 'w-2/3';
      case 'strong':
        return 'w-full';
      default:
        return 'w-0';
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-zen-stone p-4">
      <div className="max-w-md w-full">
        <div className="bg-white rounded-2xl shadow-lg p-8">
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold text-zen-charcoal mb-2">Balance 🌿</h1>
            <p className="text-zen-charcoal/60">
              {mode === 'login' ? 'Welcome back!' : 'Create your account'}
            </p>
          </div>

          {/* Mode Toggle */}
          <div className="flex gap-2 mb-6 bg-zen-stone-light rounded-lg p-1">
            <button
              onClick={() => {
                setMode('login');
                setError('');
                setMessage('');
                setConfirmPassword('');
              }}
              className={`flex-1 py-2 rounded-lg font-medium transition-colors ${
                mode === 'login'
                  ? 'bg-white text-zen-charcoal shadow-sm'
                  : 'text-zen-charcoal/60 hover:text-zen-charcoal'
              }`}
            >
              Login
            </button>
            <button
              onClick={() => {
                setMode('signup');
                setError('');
                setMessage('');
              }}
              className={`flex-1 py-2 rounded-lg font-medium transition-colors ${
                mode === 'signup'
                  ? 'bg-white text-zen-charcoal shadow-sm'
                  : 'text-zen-charcoal/60 hover:text-zen-charcoal'
              }`}
            >
              Sign Up
            </button>
          </div>

          <form onSubmit={mode === 'login' ? handleLogin : handleSignup} className="space-y-6">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                {error}
              </div>
            )}

            {message && (
              <div className="bg-zen-sage/10 border border-zen-sage/30 text-zen-sage-dark px-4 py-3 rounded-lg text-sm">
                {message}
              </div>
            )}

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-zen-charcoal mb-2">
                Email Address
              </label>
              <input
                id="email"
                name="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-zen-charcoal mb-2">
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                placeholder="••••••••"
              />

              {/* Password Strength for Signup */}
              {mode === 'signup' && password.length > 0 && (
                <div className="mt-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-zen-charcoal/60">Password strength:</span>
                    <span className="text-xs font-medium text-zen-charcoal capitalize">
                      {passwordStrength}
                    </span>
                  </div>
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all duration-300 ${getStrengthColor()} ${getStrengthWidth()}`}
                    />
                  </div>
                  <p className="text-xs text-zen-charcoal/60 mt-2">
                    Use 8+ characters with uppercase, lowercase, numbers & symbols
                  </p>
                </div>
              )}
            </div>

            {mode === 'signup' && (
              <div>
                <label
                  htmlFor="confirmPassword"
                  className="block text-sm font-medium text-zen-charcoal mb-2"
                >
                  Confirm Password
                </label>
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-4 py-3 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                  placeholder="••••••••"
                />
                {confirmPassword.length > 0 && password !== confirmPassword && (
                  <p className="text-xs text-red-600 mt-1">Passwords do not match</p>
                )}
              </div>
            )}

            {mode === 'login' && (
              <div className="flex justify-end">
                <Link
                  href="/auth/forgot-password"
                  className="text-sm text-zen-sage-dark hover:text-zen-sage font-medium"
                >
                  Forgot password?
                </Link>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-zen-sage text-white rounded-lg font-medium hover:bg-zen-sage-dark transition-colors disabled:opacity-50"
            >
              {loading ? 'Loading...' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>
        </div>

        {mode === 'signup' && (
          <p className="text-xs text-center text-zen-charcoal/50 mt-6">
            By creating an account, you agree to keep your financial data secure and use this app
            responsibly.
          </p>
        )}
      </div>
    </div>
  );
}
