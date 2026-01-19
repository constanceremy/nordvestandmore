'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import { useEffect, useState } from 'react'

type Transaction = {
  id: string
  kind: string
  status: string
  paidAt: string
  description: string
  notes: string | null
  recurrenceRule?: {
    id: string
    frequency: string
  } | null
  lines: Array<{
    id: string
    amount: string
    category: { name: string } | null
    account: { name: string }
  }>
}

type Account = {
  id: string
  name: string
}

type Category = {
  id: string
  name: string
}

export default function TransactionsPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)

  // Batch delete state
  const [batchDeleteMode, setBatchDeleteMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [lastClickedIndex, setLastClickedIndex] = useState<number | null>(null)

  const accountId = searchParams.get('account') || ''
  const categoryId = searchParams.get('category') || ''
  const status = searchParams.get('status') || ''

  useEffect(() => {
    fetchData()
    // Auto-generate recurring transactions in the background
    fetch('/api/transactions/generate-recurring', { method: 'POST' }).catch(() => {
      // Silent fail - don't block the UI
    })
  }, [accountId, categoryId, status])

  const fetchData = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (accountId) params.set('account', accountId)
      if (categoryId) params.set('category', categoryId)
      if (status) params.set('status', status)
      
      const [txRes, accountsRes, categoriesRes] = await Promise.all([
        fetch(`/api/transactions?${params.toString()}`),
        fetch('/api/accounts'),
        fetch('/api/categories')
      ])
      
      if (txRes.ok) setTransactions(await txRes.json())
      if (accountsRes.ok) setAccounts(await accountsRes.json())
      if (categoriesRes.ok) setCategories(await categoriesRes.json())
    } catch (error) {
      console.error('Failed to fetch data', error)
    } finally {
      setLoading(false)
    }
  }

  const updateFilter = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString())
    if (value) {
      params.set(key, value)
    } else {
      params.delete(key)
    }
    router.push(`?${params.toString()}`)
  }

  const clearFilters = () => {
    router.push('/transactions')
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
        fetchData() // Refresh the list
      } else {
        alert('Failed to mark as paid')
      }
    } catch (error) {
      console.error('Error marking as paid:', error)
      alert('Failed to mark as paid')
    }
  }

  const handleGenerateRecurring = async () => {
    try {
      const response = await fetch('/api/transactions/generate-recurring', {
        method: 'POST',
      })

      if (response.ok) {
        const data = await response.json()
        if (data.created > 0) {
          alert(`✅ Generated ${data.created} new recurring transactions!`)
          fetchData() // Refresh the list
        } else {
          alert('✓ All recurring transactions are up to date!')
        }
      } else {
        alert('Failed to generate recurring transactions')
      }
    } catch (error) {
      console.error('Error generating recurring transactions:', error)
      alert('Failed to generate recurring transactions')
    }
  }

  const toggleBatchDeleteMode = () => {
    setBatchDeleteMode(!batchDeleteMode)
    setSelectedIds(new Set()) // Clear selections when toggling
    setLastClickedIndex(null) // Reset last clicked
  }

  const toggleSelection = (id: string, index: number, shiftKey: boolean) => {
    const newSelected = new Set(selectedIds)
    
    // Shift-click range selection
    if (shiftKey && lastClickedIndex !== null) {
      const start = Math.min(lastClickedIndex, index)
      const end = Math.max(lastClickedIndex, index)
      
      // Select all transactions in the range
      for (let i = start; i <= end; i++) {
        newSelected.add(transactions[i].id)
      }
    } else {
      // Normal click - toggle single item
      if (newSelected.has(id)) {
        newSelected.delete(id)
      } else {
        newSelected.add(id)
      }
    }
    
    setSelectedIds(newSelected)
    setLastClickedIndex(index)
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === transactions.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(transactions.map(tx => tx.id)))
    }
  }

  const handleBatchDelete = async () => {
    setDeleting(true)
    try {
      await Promise.all(
        Array.from(selectedIds).map(id =>
          fetch(`/api/transactions/${id}`, { method: 'DELETE' })
        )
      )
      setShowDeleteConfirm(false)
      setSelectedIds(new Set())
      setBatchDeleteMode(false)
      fetchData()
    } catch (error) {
      console.error('Failed to delete transactions', error)
      alert('Failed to delete some transactions')
    } finally {
      setDeleting(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">Loading transactions...</p>
      </div>
    )
  }

  const hasFilters = accountId || categoryId || status

  // Format date nicely: "Jan 1st, 2026"
  const formatNiceDate = (dateStr: string | Date) => {
    const date = new Date(dateStr)
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    const day = date.getDate()
    const suffix = day === 1 || day === 21 || day === 31 ? 'st' : day === 2 || day === 22 ? 'nd' : day === 3 || day === 23 ? 'rd' : 'th'
    return `${months[date.getMonth()]} ${day}${suffix}, ${date.getFullYear()}`
  }

  // Format month only: "Jan 2026"
  const formatMonth = (dateStr: string | Date) => {
    const date = new Date(dateStr)
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    return `${months[date.getMonth()]} ${date.getFullYear()}`
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto p-6">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold">Transactions</h1>
          <div className="flex gap-2">
            {batchDeleteMode && selectedIds.size > 0 && (
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm flex items-center gap-2"
              >
                🗑️ Delete {selectedIds.size} Selected
              </button>
            )}
            <button
              onClick={toggleBatchDeleteMode}
              className={`px-4 py-2 rounded-md text-sm flex items-center gap-2 ${
                batchDeleteMode 
                  ? 'bg-gray-200 text-gray-700 hover:bg-gray-300' 
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {batchDeleteMode ? '✕ Cancel Selection' : '☑️ Batch Delete'}
            </button>
            <button
              onClick={handleGenerateRecurring}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm flex items-center gap-2"
              title="Generate missing recurring transactions for the next 24 months"
            >
              🔄 Refresh Recurring
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label htmlFor="account" className="block text-sm font-medium text-gray-700 mb-1">
                Account
              </label>
              <select
                id="account"
                value={accountId}
                onChange={(e) => updateFilter('account', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              >
                <option value="">All accounts</option>
                {accounts.map(acc => (
                  <option key={acc.id} value={acc.id}>{acc.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="category" className="block text-sm font-medium text-gray-700 mb-1">
                Category
              </label>
              <select
                id="category"
                value={categoryId}
                onChange={(e) => updateFilter('category', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              >
                <option value="">All categories</option>
                {categories.map(cat => (
                  <option key={cat.id} value={cat.id}>{cat.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="status" className="block text-sm font-medium text-gray-700 mb-1">
                Status
              </label>
              <select
                id="status"
                value={status}
                onChange={(e) => updateFilter('status', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              >
                <option value="">All</option>
                <option value="PAID">Paid</option>
                <option value="PLANNED">Planned</option>
              </select>
            </div>

            {hasFilters && (
              <div className="flex items-end">
                <button
                  onClick={clearFilters}
                  className="w-full px-4 py-2 text-sm text-blue-600 border border-blue-600 rounded-md hover:bg-blue-50"
                >
                  Clear Filters
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Transactions List */}
        <div className="bg-white rounded-lg shadow">
          {transactions.length === 0 ? (
            <div className="p-8 text-center text-gray-600">
              No transactions found.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    {batchDeleteMode && (
                      <th className="px-4 py-3 text-left">
                        <input
                          type="checkbox"
                          checked={selectedIds.size === transactions.length && transactions.length > 0}
                          onChange={toggleSelectAll}
                          className="w-4 h-4 rounded border-gray-300"
                          title="Select all"
                        />
                      </th>
                    )}
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Paid At</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Effective For</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Account</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Amount</th>
                    {!batchDeleteMode && (
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {transactions.map((tx, index) => {
                    const totalAmount = tx.lines.reduce((sum, line) => sum + Math.abs(Number(line.amount)), 0)
                    const isExpense = tx.kind === 'EXPENSE'
                    const categories = tx.lines.map(l => l.category?.name).filter(Boolean).join(', ')
                    const accounts = [...new Set(tx.lines.map(l => l.account.name))].join(' → ')

                    return (
                      <tr key={tx.id} className={`hover:bg-gray-50 ${selectedIds.has(tx.id) ? 'bg-blue-50' : ''}`}>
                        {batchDeleteMode && (
                          <td className="px-4 py-4">
                            <input
                              type="checkbox"
                              checked={selectedIds.has(tx.id)}
                              onClick={(e) => toggleSelection(tx.id, index, e.shiftKey)}
                              onChange={() => {}} // Prevent warning, actual logic in onClick
                              className="w-4 h-4 rounded border-gray-300 cursor-pointer"
                            />
                          </td>
                        )}
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {formatNiceDate(tx.paidAt)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                          {tx.effectiveForMonth ? formatMonth(tx.effectiveForMonth) : '—'}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-900">
                          <div className="flex items-center gap-2">
                            {tx.recurrenceRule && (
                              <span className="text-blue-600" title={`Recurring ${tx.recurrenceRule.frequency.toLowerCase()}`}>
                                🔄
                              </span>
                            )}
                            <span>{tx.description}</span>
                          </div>
                          {tx.notes && (
                            <div className="text-xs text-gray-500">{tx.notes}</div>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                          {accounts}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-600">
                          {categories || '—'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                            tx.status === 'PAID' 
                              ? 'bg-green-100 text-green-800' 
                              : 'bg-yellow-100 text-yellow-800'
                          }`}>
                            {tx.status === 'PAID' ? 'Paid' : 'Planned'}
                          </span>
                        </td>
                        <td className={`px-6 py-4 whitespace-nowrap text-sm text-right font-medium ${
                          isExpense ? 'text-red-600' : tx.kind === 'INCOME' ? 'text-green-600' : 'text-gray-900'
                        }`}>
                          {isExpense ? '−' : tx.kind === 'INCOME' ? '+' : ''}{totalAmount.toFixed(2)}
                        </td>
                        {!batchDeleteMode && (
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-right space-x-2">
                            {tx.status === 'PLANNED' && (
                              <button
                                onClick={() => handleMarkAsPaid(tx.id)}
                                className="text-green-600 hover:text-green-800 text-xs font-medium"
                                title="Mark as paid"
                              >
                                ✓ Paid
                              </button>
                            )}
                            <button
                              onClick={() => router.push(`/transactions/${tx.id}/edit`)}
                              className="text-blue-600 hover:text-blue-800 text-xs font-medium"
                            >
                              Edit
                            </button>
                          </td>
                        )}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Confirm Deletion</h2>
            <p className="text-gray-600 mb-6">
              Are you sure you want to delete {selectedIds.size} transaction{selectedIds.size !== 1 ? 's' : ''}? 
              This action cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                disabled={deleting}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-100 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleBatchDelete}
                disabled={deleting}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
