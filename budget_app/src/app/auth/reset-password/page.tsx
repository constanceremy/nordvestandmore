'use client';

import { useState, useEffect } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

export default function ResetPasswordPage() {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [passwordStrength, setPasswordStrength] = useState<
    'weak' | 'medium' | 'strong' | null
  >(null);
  const router = useRouter();
  const supabase = createClient();

  useEffect(() => {
    // Check if user has a valid session from the reset link
    const checkSession = async () => {
      const { data } = await supabase.auth.getSession();
      if (!data.session) {
        setError('Invalid or expired reset link. Please request a new one.');
      }
    };
    checkSession();
  }, [supabase]);

  useEffect(() => {
    if (password.length === 0) {
      setPasswordStrength(null);
      return;
    }

    // Password strength checker
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
  }, [password]);

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validation
    if (password.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (passwordStrength === 'weak') {
      setError('Please choose a stronger password');
      return;
    }

    setLoading(true);

    try {
      const { error } = await supabase.auth.updateUser({
        password: password,
      });

      if (error) throw error;

      setSuccess(true);
      setTimeout(() => {
        router.push('/login');
      }, 2000);
    } catch (err: any) {
      setError(err.message || 'Failed to reset password');
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
            <h1 className="text-3xl font-bold text-zen-charcoal mb-2">Set New Password</h1>
            <p className="text-zen-charcoal/60">Choose a strong password for your account</p>
          </div>

          {success ? (
            <div className="text-center space-y-6">
              <div className="w-16 h-16 bg-zen-sage/20 rounded-full flex items-center justify-center mx-auto">
                <span className="text-3xl">✓</span>
              </div>
              <div>
                <h2 className="text-xl font-semibold text-zen-charcoal mb-2">Password Updated!</h2>
                <p className="text-zen-charcoal/60">Redirecting you to login...</p>
              </div>
            </div>
          ) : (
            <form onSubmit={handleResetPassword} className="space-y-6">
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                  {error}
                </div>
              )}

              <div>
                <label htmlFor="password" className="block text-sm font-medium text-zen-charcoal mb-2">
                  New Password
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

                {/* Password Strength Indicator */}
                {password.length > 0 && (
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
                  </div>
                )}

                <div className="mt-3 space-y-1">
                  <p className="text-xs text-zen-charcoal/60">Password must contain:</p>
                  <ul className="text-xs text-zen-charcoal/60 space-y-1 ml-4">
                    <li className={password.length >= 8 ? 'text-green-600' : ''}>
                      {password.length >= 8 ? '✓' : '○'} At least 8 characters
                    </li>
                    <li className={/[A-Z]/.test(password) ? 'text-green-600' : ''}>
                      {/[A-Z]/.test(password) ? '✓' : '○'} One uppercase letter
                    </li>
                    <li className={/[a-z]/.test(password) ? 'text-green-600' : ''}>
                      {/[a-z]/.test(password) ? '✓' : '○'} One lowercase letter
                    </li>
                    <li className={/\d/.test(password) ? 'text-green-600' : ''}>
                      {/\d/.test(password) ? '✓' : '○'} One number
                    </li>
                    <li className={/[!@#$%^&*(),.?":{}|<>]/.test(password) ? 'text-green-600' : ''}>
                      {/[!@#$%^&*(),.?":{}|<>]/.test(password) ? '✓' : '○'} One special character
                    </li>
                  </ul>
                </div>
              </div>

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

              <button
                type="submit"
                disabled={loading || passwordStrength === 'weak' || password !== confirmPassword}
                className="w-full py-3 px-4 bg-zen-sage text-white rounded-lg font-medium hover:bg-zen-sage-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Updating...' : 'Update Password'}
              </button>

              <Link
                href="/login"
                className="block text-center text-zen-charcoal/60 hover:text-zen-charcoal text-sm"
              >
                ← Back to login
              </Link>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
