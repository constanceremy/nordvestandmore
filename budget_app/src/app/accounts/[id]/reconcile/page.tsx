'use client'

import { useParams, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import LoadingSpinner from '@/components/LoadingSpinner'

export default function ReconcileAccountPage() {
  const params = useParams()
  const router = useRouter()
  const accountId = params.id as string

  const [account, setAccount] = useState<any>(null)
  const [currentBalance, setCurrentBalance] = useState(0)
  const [newBalance, setNewBalance] = useState('')
  const [reconcileDate, setReconcileDate] = useState(() => {
    const today = new Date()
    return today.toISOString().split('T')[0]
  })
  const [notes, setNotes] = useState('')
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
        setAccount(data.account)
        
        // Use the calculated balance from the API
        const balance = data.currentBalance
        setCurrentBalance(balance)
        setNewBalance(balance.toFixed(2))
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

    const difference = Number(newBalance) - currentBalance

    try {
      const response = await fetch(`/api/accounts/${accountId}/reconcile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          newBalance: Number(newBalance),
          reconcileDate,
          notes: notes || `Balance reconciliation - adjustment of ${difference.toFixed(2)} ${account.currency}`
        })
      })

      if (response.ok) {
        const diff = parseFloat(actualBalance) - data.currentBalance
        toast.success('Account reconciled!', {
          description: diff !== 0 
            ? `Adjustment of ${Math.abs(diff).toFixed(2)} ${data.account.currency} created`
            : 'Balance matches perfectly'
        })
        router.push(`/accounts/${accountId}`)
      } else {
        const error = await response.json()
        toast.error('Failed to reconcile', {
          description: error.error || 'Unknown error'
        })
      }
    } catch (error) {
      console.error('Error reconciling account', error)
      toast.error('Failed to reconcile account', {
        description: 'An error occurred'
      })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-zen-stone flex items-center justify-center">
        <LoadingSpinner size="lg" text="Loading account data..." />
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

  const difference = Number(newBalance) - currentBalance

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
          <h1 className="text-3xl font-bold text-zen-charcoal">Reconcile Account</h1>
          <p className="text-zen-charcoal-light mt-2">{account.name}</p>
        </div>

        <div className="bg-gradient-to-br from-zen-sage-light to-zen-sage rounded-xl shadow-md p-6 mb-6 text-white">
          <p className="text-sm opacity-90 mb-1">Current Balance (Calculated)</p>
          <p className="text-4xl font-bold">
            {currentBalance.toFixed(2)} {account.currency}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="bg-zen-stone-light rounded-xl shadow-md p-8">
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-zen-charcoal mb-2">
                Actual Balance (From Bank Statement)
              </label>
              <input
                type="number"
                step="0.01"
                value={newBalance}
                onChange={(e) => setNewBalance(e.target.value)}
                required
                className="w-full px-4 py-3 border border-zen-stone-dark rounded-lg focus:ring-2 focus:ring-zen-sage focus:border-zen-sage text-xl font-bold"
                placeholder="0.00"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-zen-charcoal mb-2">
                Reconciliation Date
              </label>
              <input
                type="date"
                value={reconcileDate}
                onChange={(e) => setReconcileDate(e.target.value)}
                required
                className="w-full px-4 py-3 border border-zen-stone-dark rounded-lg focus:ring-2 focus:ring-zen-sage focus:border-zen-sage"
              />
            </div>

            {difference !== 0 && (
              <div className={`rounded-lg p-4 ${
                difference > 0 
                  ? 'bg-green-50 border border-green-200' 
                  : 'bg-red-50 border border-red-200'
              }`}>
                <p className="text-sm font-medium text-zen-charcoal mb-1">Adjustment Required</p>
                <p className={`text-2xl font-bold ${difference > 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {difference > 0 ? '+' : ''}{difference.toFixed(2)} {account.currency}
                </p>
                <p className="text-sm text-zen-charcoal-light mt-2">
                  A reconciliation transaction will be created to adjust the balance.
                </p>
              </div>
            )}

            {difference === 0 && (
              <div className="bg-zen-sage-light rounded-lg p-4">
                <p className="text-sm font-medium text-zen-charcoal">
                  ✓ Balance matches! No adjustment needed.
                </p>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-zen-charcoal mb-2">
                Notes (Optional)
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                className="w-full px-4 py-3 border border-zen-stone-dark rounded-lg focus:ring-2 focus:ring-zen-sage focus:border-zen-sage"
                placeholder="Add any notes about this reconciliation..."
              />
            </div>

            <div className="bg-zen-sand-light border border-zen-sand rounded-lg p-4">
              <p className="text-sm text-zen-charcoal">
                <strong>How it works:</strong> This will create a "Reconciliation" transaction to adjust your balance 
                to match your bank statement, without losing any transaction history.
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
                disabled={saving || difference === 0}
                className="flex-1 px-6 py-3 bg-zen-sage text-white rounded-lg hover:bg-zen-sage-dark transition-colors shadow-md disabled:opacity-50"
              >
                {saving ? 'Reconciling...' : 'Reconcile Balance'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}
