'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';
import { toast } from 'sonner';
import LoadingSpinner from '@/components/LoadingSpinner';

type Profile = {
  id: string;
  primaryCurrency: string;
  timezone: string;
};

export default function ProfilePage() {
  const router = useRouter();
  const supabase = createClient();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // User data
  const [email, setEmail] = useState('');
  const [newEmail, setNewEmail] = useState('');
  
  // Profile data
  const [profile, setProfile] = useState<Profile | null>(null);
  const [primaryCurrency, setPrimaryCurrency] = useState('DKK');
  const [timezone, setTimezone] = useState('Europe/Copenhagen');

  // Password change
  const [showPasswordChange, setShowPasswordChange] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  // Delete account
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');

  useEffect(() => {
    loadUserData();
  }, []);

  const loadUserData = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        router.push('/login');
        return;
      }

      setEmail(user.email || '');
      setNewEmail(user.email || '');

      // Load profile
      const res = await fetch('/api/profile');
      if (res.ok) {
        const profileData = await res.json();
        setProfile(profileData);
        setPrimaryCurrency(profileData.primaryCurrency);
        setTimezone(profileData.timezone);
      }
    } catch (err) {
      console.error('Error loading user data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateEmail = async () => {
    if (newEmail === email) {
      setError('New email is the same as current email');
      return;
    }

    setSaving(true);
    setError('');
    setSuccess('');

    try {
      const { error } = await supabase.auth.updateUser({ email: newEmail });
      if (error) throw error;

      setEmail(newEmail);
      toast.success('Email update initiated!', {
        description: 'Check your new email for a confirmation link'
      });
    } catch (err: any) {
      setError(err.message || 'Failed to update email');
      toast.error('Failed to update email', {
        description: err.message
      });
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateProfile = async () => {
    setSaving(true);
    setError('');
    setSuccess('');

    try {
      const res = await fetch('/api/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ primaryCurrency, timezone }),
      });

      if (!res.ok) throw new Error('Failed to update profile');

      toast.success('Profile updated!', {
        description: 'Your preferences have been saved'
      });
    } catch (err: any) {
      setError(err.message || 'Failed to update profile');
      toast.error('Failed to update profile', {
        description: err.message
      });
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async () => {
    if (!currentPassword) {
      setError('Please enter your current password');
      return;
    }

    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters');
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setSaving(true);
    setError('');
    setSuccess('');

    try {
      // First, verify the current password by attempting to sign in
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email: email,
        password: currentPassword,
      });

      if (signInError) {
        throw new Error('Current password is incorrect');
      }

      // If current password is correct, update to new password
      const { error: updateError } = await supabase.auth.updateUser({ password: newPassword });
      if (updateError) throw updateError;

      toast.success('Password changed!', {
        description: 'Your password has been updated successfully'
      });
      setShowPasswordChange(false);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      setError(err.message || 'Failed to change password');
      toast.error('Failed to change password', {
        description: err.message
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (deleteConfirmText !== 'DELETE') {
      setError('Please type DELETE to confirm');
      return;
    }

    setSaving(true);
    setError('');

    try {
      console.log('Attempting to delete account...');
      const res = await fetch('/api/profile', {
        method: 'DELETE',
      });

      console.log('Delete response status:', res.status);
      const data = await res.json();
      console.log('Delete response data:', data);

      if (!res.ok) {
        throw new Error(data.error || 'Failed to delete account');
      }

      console.log('Account deleted successfully, signing out...');
      // Sign out and redirect
      await supabase.auth.signOut();
      router.push('/login');
    } catch (err: any) {
      console.error('Error deleting account:', err);
      setError(err.message || 'Failed to delete account');
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zen-stone flex items-center justify-center">
        <LoadingSpinner size="lg" text="Loading profile..." />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zen-stone py-8 px-4">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-3xl font-bold text-zen-charcoal mb-8">Profile Settings</h1>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        {success && (
          <div className="bg-zen-sage/10 border border-zen-sage/30 text-zen-sage-dark px-4 py-3 rounded-lg mb-6">
            {success}
          </div>
        )}

        {/* Email Section */}
        <div className="bg-white rounded-xl shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold text-zen-charcoal mb-4">Email Address</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-zen-charcoal mb-2">
                Current Email
              </label>
              <input
                type="email"
                value={email}
                disabled
                className="w-full px-4 py-2 border border-zen-stone-light rounded-lg bg-zen-stone-light/50 text-zen-charcoal/60"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-zen-charcoal mb-2">
                New Email
              </label>
              <input
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                className="w-full px-4 py-2 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
              />
            </div>
            <button
              onClick={handleUpdateEmail}
              disabled={saving || newEmail === email}
              className="px-4 py-2 bg-zen-sage text-white rounded-lg hover:bg-zen-sage-dark transition-colors disabled:opacity-50"
            >
              {saving ? 'Updating...' : 'Update Email'}
            </button>
            <p className="text-xs text-zen-charcoal/60">
              You'll need to verify your new email address before the change takes effect.
            </p>
          </div>
        </div>

        {/* Password Section */}
        <div className="bg-white rounded-xl shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold text-zen-charcoal mb-4">Password</h2>
          
          {!showPasswordChange ? (
            <button
              onClick={() => setShowPasswordChange(true)}
              className="px-4 py-2 bg-zen-stone-light text-zen-charcoal rounded-lg hover:bg-zen-stone transition-colors"
            >
              Change Password
            </button>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-zen-charcoal mb-2">
                  Current Password <span className="text-red-500">*</span>
                </label>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="w-full px-4 py-2 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                  placeholder="Enter your current password"
                />
                <p className="text-xs text-zen-charcoal/60 mt-1">
                  For security, we need to verify it's really you
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-zen-charcoal mb-2">
                  New Password <span className="text-red-500">*</span>
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full px-4 py-2 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                  placeholder="At least 8 characters"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-zen-charcoal mb-2">
                  Confirm New Password <span className="text-red-500">*</span>
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-4 py-2 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                />
              </div>
              <div className="flex gap-3">
                <button
                  onClick={handleChangePassword}
                  disabled={saving || !currentPassword || !newPassword || !confirmPassword}
                  className="px-4 py-2 bg-zen-sage text-white rounded-lg hover:bg-zen-sage-dark transition-colors disabled:opacity-50"
                >
                  {saving ? 'Saving...' : 'Save Password'}
                </button>
                <button
                  onClick={() => {
                    setShowPasswordChange(false);
                    setCurrentPassword('');
                    setNewPassword('');
                    setConfirmPassword('');
                    setError('');
                  }}
                  className="px-4 py-2 bg-zen-stone-light text-zen-charcoal rounded-lg hover:bg-zen-stone transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Profile Preferences */}
        <div className="bg-white rounded-xl shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold text-zen-charcoal mb-4">Preferences</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-zen-charcoal mb-2">
                Primary Currency
              </label>
              <select
                value={primaryCurrency}
                onChange={(e) => setPrimaryCurrency(e.target.value)}
                className="w-full px-4 py-2 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
              >
                <option value="DKK">DKK (kr)</option>
                <option value="USD">USD ($)</option>
                <option value="EUR">EUR (€)</option>
                <option value="GBP">GBP (£)</option>
                <option value="SEK">SEK (kr)</option>
                <option value="NOK">NOK (kr)</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-zen-charcoal mb-2">
                Timezone
              </label>
              <select
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="w-full px-4 py-2 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
              >
                <option value="Europe/Copenhagen">Europe/Copenhagen</option>
                <option value="Europe/London">Europe/London</option>
                <option value="Europe/Paris">Europe/Paris</option>
                <option value="America/New_York">America/New York</option>
                <option value="America/Los_Angeles">America/Los Angeles</option>
                <option value="Asia/Tokyo">Asia/Tokyo</option>
              </select>
            </div>
            <button
              onClick={handleUpdateProfile}
              disabled={saving}
              className="px-4 py-2 bg-zen-sage text-white rounded-lg hover:bg-zen-sage-dark transition-colors disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save Preferences'}
            </button>
          </div>
        </div>

        {/* Danger Zone - Delete Account */}
        <div className="bg-red-50 border-2 border-red-200 rounded-xl p-6">
          <h2 className="text-xl font-semibold text-red-700 mb-2">Danger Zone</h2>
          <p className="text-sm text-red-600 mb-4">
            Once you delete your account, there is no going back. All your data will be permanently deleted.
          </p>

          {!showDeleteConfirm ? (
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
            >
              Delete My Account
            </button>
          ) : (
            <div className="space-y-4">
              <div className="bg-white rounded-lg p-4 border border-red-300">
                <h3 className="font-semibold text-red-700 mb-2">⚠️ This action cannot be undone!</h3>
                <p className="text-sm text-red-600 mb-3">
                  This will permanently delete:
                </p>
                <ul className="text-sm text-red-600 space-y-1 ml-4 mb-3">
                  <li>• All your accounts and balances</li>
                  <li>• All your transactions</li>
                  <li>• All your categories and budgets</li>
                  <li>• Your profile and preferences</li>
                  <li>• Everything - no recovery possible</li>
                </ul>
                <p className="text-sm text-red-700 font-medium">
                  Type <strong>DELETE</strong> to confirm:
                </p>
                <input
                  type="text"
                  value={deleteConfirmText}
                  onChange={(e) => setDeleteConfirmText(e.target.value)}
                  placeholder="Type DELETE"
                  className="w-full px-4 py-2 border-2 border-red-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 mt-2"
                />
              </div>
              <div className="flex gap-3">
                <button
                  onClick={handleDeleteAccount}
                  disabled={saving || deleteConfirmText !== 'DELETE'}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
                >
                  {saving ? 'Deleting...' : 'Yes, Delete Everything'}
                </button>
                <button
                  onClick={() => {
                    setShowDeleteConfirm(false);
                    setDeleteConfirmText('');
                    setError('');
                  }}
                  className="px-4 py-2 bg-zen-stone-light text-zen-charcoal rounded-lg hover:bg-zen-stone transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
