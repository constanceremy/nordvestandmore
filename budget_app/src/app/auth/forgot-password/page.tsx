'use client';

import { useState } from 'react';
import { createClient } from '@/lib/supabase/client';
import Link from 'next/link';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const supabase = createClient();

  const handleResetRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/auth/reset-password`,
      });

      if (error) throw error;

      setSuccess(true);
    } catch (err: any) {
      setError(err.message || 'Failed to send reset email');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-zen-stone p-4">
      <div className="max-w-md w-full">
        <div className="bg-white rounded-2xl shadow-lg p-8">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-zen-charcoal mb-2">Reset Password</h1>
            <p className="text-zen-charcoal/60">
              {success
                ? "We've sent you a reset link!"
                : 'Enter your email to receive a password reset link'}
            </p>
          </div>

          {success ? (
            <div className="space-y-6">
              <div className="bg-zen-sage/10 border border-zen-sage/30 rounded-lg p-4">
                <p className="text-zen-sage-dark text-center">
                  ✉️ Check your email inbox for a password reset link. It may take a few minutes to arrive.
                </p>
              </div>

              <div className="text-center space-y-4">
                <p className="text-sm text-zen-charcoal/60">Didn't receive the email?</p>
                <button
                  onClick={() => {
                    setSuccess(false);
                    setEmail('');
                  }}
                  className="text-zen-sage-dark hover:text-zen-sage font-medium"
                >
                  Try again
                </button>
              </div>

              <Link
                href="/login"
                className="block text-center text-zen-charcoal/60 hover:text-zen-charcoal text-sm"
              >
                ← Back to login
              </Link>
            </div>
          ) : (
            <form onSubmit={handleResetRequest} className="space-y-6">
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                  {error}
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

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 px-4 bg-zen-sage text-white rounded-lg font-medium hover:bg-zen-sage-dark transition-colors disabled:opacity-50"
              >
                {loading ? 'Sending...' : 'Send Reset Link'}
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

        <p className="text-xs text-center text-zen-charcoal/50 mt-6">
          The reset link will expire in 1 hour for security.
        </p>
      </div>
    </div>
  );
}
