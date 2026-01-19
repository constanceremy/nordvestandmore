'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

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
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">Loading...</p>
      </div>
    )
  }

  if (!account) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">Account not found</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto p-6">
        <div className="mb-6">
          <a href="/accounts" className="text-blue-600 hover:text-blue-700">
            ← Back to Accounts
          </a>
        </div>

        {/* Account Header */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex justify-between items-start">
            <div>
              <h1 className="text-3xl font-bold mb-2">{account.name}</h1>
              <p className="text-gray-600 mb-4">{account.type} • {account.currency}</p>
              <div className="text-sm text-gray-500">
                <p>Opening Balance: {Number(account.openingBalance).toFixed(2)} {account.currency}</p>
                <p>As of: {new Date(account.openingBalanceDate).toLocaleDateString('en-GB')}</p>
              </div>
            </div>
            <div className="text-right">
              <div className="mb-4">
                <p className="text-sm text-gray-600">Current Balance</p>
                <p className="text-3xl font-bold">
                  {currentBalance.toFixed(2)} {account.currency}
                </p>
              </div>
              {expectedBalance !== currentBalance && (
                <div>
                  <p className="text-sm text-gray-600">Expected Balance</p>
                  <p className="text-xl font-semibold text-blue-600">
                    {expectedBalance.toFixed(2)} {account.currency}
                  </p>
                  <p className="text-xs text-gray-500">(including planned)</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Transactions */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-xl font-semibold">Transactions</h2>
          </div>

          {linesWithBalance.length === 0 ? (
            <div className="p-8 text-center text-gray-600">
              No transactions yet for this account.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Amount</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Balance</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {linesWithBalance.map((line) => {
                    const amount = Number(line.amount)
                    const isNegative = amount < 0

                    return (
                      <tr key={line.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {new Date(line.transaction.paidAt).toLocaleDateString('en-GB')}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-900">
                          <div>{line.transaction.description}</div>
                          {line.transaction.notes && (
                            <div className="text-xs text-gray-500">{line.transaction.notes}</div>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                          {line.category?.name || '—'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                            line.transaction.status === 'PAID' 
                              ? 'bg-green-100 text-green-800' 
                              : 'bg-yellow-100 text-yellow-800'
                          }`}>
                            {line.transaction.status === 'PAID' ? 'Paid' : 'Planned'}
                          </span>
                        </td>
                        <td className={`px-6 py-4 whitespace-nowrap text-sm text-right font-medium ${
                          isNegative ? 'text-red-600' : 'text-green-600'
                        }`}>
                          {isNegative ? '−' : '+'}{Math.abs(amount).toFixed(2)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right font-semibold text-gray-900">
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
                            className="text-blue-600 hover:text-blue-800 text-xs font-medium"
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
