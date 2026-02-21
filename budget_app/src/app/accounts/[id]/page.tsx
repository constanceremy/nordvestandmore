'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import LoadingSpinner from '@/components/LoadingSpinner'

type Account = {
  id: string
  name: string
  type: string
  currency: string
  openingBalance: string
  openingBalanceDate: string
}

type LineWithBalance = {
  id: string
  amount: string
  runningBalance: number
  transaction: {
    id: string
    paidAt: string
    description: string
    notes: string | null
    status: string
  }
  category: { name: string } | null
}

export default function AccountDetailPage({ 
  params 
}: { 
  params: Promise<{ id: string }> 
}) {
  const router = useRouter()
  const [accountId, setAccountId] = useState('')
  const [account, setAccount] = useState<Account | null>(null)
  const [linesWithBalance, setLinesWithBalance] = useState<LineWithBalance[]>([])
  const [currentBalance, setCurrentBalance] = useState(0)
  const [expectedBalance, setExpectedBalance] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    params.then(p => {
      setAccountId(p.id)
      fetchData(p.id)
    })
  }, [])

  const fetchData = async (id: string) => {
    setLoading(true)
    try {
      const response = await fetch(`/api/accounts/${id}`)
      if (response.ok) {
        const data = await response.json()
        setAccount(data.account)
        setLinesWithBalance(data.linesWithBalance)
        setCurrentBalance(data.currentBalance)
        setExpectedBalance(data.expectedBalance)
      } else {
        router.push('/accounts')
      }
    } catch (error) {
      console.error('Failed to fetch account data', error)
      router.push('/accounts')
    } finally {
      setLoading(false)
    }
  }

  const handleMarkAsPaid = async (transactionId: string) => {
    try {
      const response = await fetch(`/api/transactions/${transactionId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          status: 'PAID',
          paidAt: new Date(),
        }),
      })

      if (response.ok) {
        fetchData(accountId) // Refresh
      } else {
        alert('Failed to mark as paid')
      }
    } catch (error) {
      console.error('Error marking as paid:', error)
      alert('Failed to mark as paid')
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-zen-stone flex items-center justify-center">
        <LoadingSpinner size="lg" text="Loading account ledger..." />
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
      <div className="max-w-5xl mx-auto p-6">
        <div className="mb-6">
          <a href="/accounts" className="text-zen-sage-dark hover:text-zen-sage">
            ← Back to Accounts
          </a>
        </div>

        {/* Account Header */}
        <div className="bg-gradient-to-br from-zen-stone-light to-white rounded-xl shadow-md p-8 mb-6 border border-zen-stone-dark">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-3xl font-bold mb-2 text-zen-charcoal">{account.name}</h1>
              <p className="text-zen-charcoal-light mb-4 uppercase tracking-wide text-sm">{account.type} • {account.currency}</p>
              <div className="text-sm text-zen-charcoal-light bg-zen-stone rounded-lg p-3 inline-block">
                <p>Opening Balance: <span className="font-semibold text-zen-charcoal">{Number(account.openingBalance).toFixed(2)} {account.currency}</span></p>
                <p>As of: <span className="font-semibold text-zen-charcoal">{new Date(account.openingBalanceDate).toLocaleDateString('en-GB')}</span></p>
              </div>
            </div>
            <div className="text-right">
              <div className="mb-4 bg-zen-sage rounded-lg p-4 text-white">
                <p className="text-sm opacity-90">Current Balance</p>
                <p className="text-4xl font-bold">
                  {currentBalance.toFixed(2)}
                </p>
                <p className="text-sm opacity-90">{account.currency}</p>
              </div>
              {expectedBalance !== currentBalance && (
                <div className="bg-zen-sand-light rounded-lg p-4">
                  <p className="text-sm text-zen-charcoal-light">Expected Balance</p>
                  <p className="text-2xl font-bold text-zen-charcoal">
                    {expectedBalance.toFixed(2)}
                  </p>
                  <p className="text-xs text-zen-charcoal-light">(including planned)</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Transactions */}
        <div className="bg-zen-stone-light rounded-xl shadow-md overflow-hidden">
          <div className="px-6 py-4 border-b border-zen-stone-dark">
            <h2 className="text-xl font-semibold text-zen-charcoal">Transaction Ledger</h2>
          </div>

          {linesWithBalance.length === 0 ? (
            <div className="p-12 text-center">
              <div className="text-6xl mb-4">📖</div>
              <h3 className="text-lg font-semibold text-zen-charcoal mb-2">No Transactions Yet</h3>
              <p className="text-zen-charcoal/60 text-sm mb-6">
                This account doesn't have any transactions yet. Add one to get started!
              </p>
              <a
                href="/transactions/add"
                className="inline-block px-6 py-3 bg-zen-sage text-white rounded-lg hover:bg-zen-sage-dark transition-colors shadow-md"
              >
                + Add Transaction
              </a>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-zen-stone border-b border-zen-stone-dark">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-zen-charcoal uppercase">Date</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-zen-charcoal uppercase">Description</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-zen-charcoal uppercase">Category</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-zen-charcoal uppercase">Status</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-zen-charcoal uppercase">Amount</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-zen-charcoal uppercase">Balance</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-zen-charcoal uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zen-stone-dark">
                  {linesWithBalance.map((line) => {
                    const amount = Number(line.amount)
                    const isNegative = amount < 0

                    return (
                      <tr key={line.id} className="hover:bg-zen-stone transition-colors">
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-zen-charcoal">
                          {new Date(line.transaction.paidAt).toLocaleDateString('en-GB')}
                        </td>
                        <td className="px-6 py-4 text-sm text-zen-charcoal">
                          <div className="font-medium">{line.transaction.description}</div>
                          {line.transaction.notes && (
                            <div className="text-xs text-zen-charcoal-light">{line.transaction.notes}</div>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-zen-charcoal-light">
                          {line.category?.name || '—'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                            line.transaction.status === 'PAID' 
                              ? 'bg-zen-sage-light text-zen-charcoal' 
                              : 'bg-zen-sand text-zen-charcoal'
                          }`}>
                            {line.transaction.status === 'PAID' ? 'Paid' : 'Planned'}
                          </span>
                        </td>
                        <td className={`px-6 py-4 whitespace-nowrap text-sm text-right font-semibold ${
                          isNegative ? 'text-red-600' : 'text-green-600'
                        }`}>
                          {isNegative ? '−' : '+'}{Math.abs(amount).toFixed(2)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right font-bold text-zen-charcoal">
                          {line.runningBalance.toFixed(2)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right space-x-2">
                          {line.transaction.status === 'PLANNED' && (
                            <button
                              onClick={() => handleMarkAsPaid(line.transaction.id)}
                              className="text-green-600 hover:text-green-800 text-xs font-medium"
                              title="Mark as paid"
                            >
                              ✓ Paid
                            </button>
                          )}
                          <button
                            onClick={() => router.push(`/transactions/${line.transaction.id}/edit`)}
                            className="text-zen-sage-dark hover:text-zen-sage text-xs font-medium"
                          >
                            Edit
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
