'use client'

import { useParams, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import LoadingSpinner from '@/components/LoadingSpinner'

export default function EditAccountPage() {
  const params = useParams()
  const router = useRouter()
  const accountId = params.id as string

  const [account, setAccount] = useState<any>(null)
  const [name, setName] = useState('')
  const [currency, setCurrency] = useState('DKK')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetchAccount()
  }, [accountId])

  const fetchAccount = async () => {
    try {
      const response = await fetch(`/api/accounts/${accountId}`)
      if (response.ok) {
        const data = await response.json()
        setAccount(data)
        setName(data.name)
        setCurrency(data.currency)
      }
    } catch (error) {
      console.error('Failed to fetch account', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)

    try {
      const response = await fetch(`/api/accounts/${accountId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, currency })
      })

      if (response.ok) {
        toast.success('Account updated!', {
          description: 'Changes have been saved'
        })
        router.push('/accounts')
      } else {
        toast.error('Failed to update account', {
          description: 'Please try again'
        })
      }
    } catch (error) {
      console.error('Error updating account', error)
      toast.error('Failed to update account', {
        description: 'An error occurred'
      })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-zen-stone flex items-center justify-center">
        <LoadingSpinner size="lg" text="Loading account details..." />
      </div>
    )
  }

  if (!account) {
    return (
      <div className="min-h-screen bg-zen-stone flex items-center justify-center">
        <p className="text-zen-charcoal-light">Account not found</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-zen-stone">
      <div className="max-w-2xl mx-auto p-6">
        <div className="mb-6">
          <button
            onClick={() => router.back()}
            className="text-zen-charcoal-light hover:text-zen-charcoal mb-4"
          >
            ← Back
          </button>
          <h1 className="text-3xl font-bold text-zen-charcoal">Edit Account</h1>
        </div>

        <form onSubmit={handleSubmit} className="bg-zen-stone-light rounded-xl shadow-md p-8">
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-zen-charcoal mb-2">
                Account Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="w-full px-4 py-3 border border-zen-stone-dark rounded-lg focus:ring-2 focus:ring-zen-sage focus:border-zen-sage"
                placeholder="e.g., Constance Checkings"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-zen-charcoal mb-2">
                Currency
              </label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                required
                className="w-full px-4 py-3 border border-zen-stone-dark rounded-lg focus:ring-2 focus:ring-zen-sage focus:border-zen-sage"
              >
                <option value="DKK">DKK - Danish Krone</option>
                <option value="USD">USD - US Dollar</option>
                <option value="EUR">EUR - Euro</option>
                <option value="GBP">GBP - British Pound</option>
                <option value="SEK">SEK - Swedish Krona</option>
                <option value="NOK">NOK - Norwegian Krone</option>
              </select>
            </div>

            <div className="bg-zen-sand-light border border-zen-sand rounded-lg p-4">
              <p className="text-sm text-zen-charcoal">
                <strong>Note:</strong> Changing the currency will not convert existing transaction amounts. 
                This should only be changed if the currency was set incorrectly.
              </p>
            </div>

            <div className="flex gap-4">
              <button
                type="button"
                onClick={() => router.back()}
                className="flex-1 px-6 py-3 bg-zen-stone-dark text-zen-charcoal rounded-lg hover:bg-zen-sand transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="flex-1 px-6 py-3 bg-zen-sage text-white rounded-lg hover:bg-zen-sage-dark transition-colors shadow-md disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}
