'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import { useEffect, useState, Fragment } from 'react'
import { toast } from 'sonner'
import LoadingSpinner from '@/components/LoadingSpinner'

type Transaction = {
  id: string
  kind: string
  status: string
  paidAt: string
  effectiveForMonth: string | null
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

  // Expandable split transactions
  const [expandedTxIds, setExpandedTxIds] = useState<Set<string>>(new Set())

  const toggleExpanded = (txId: string) => {
    const newExpanded = new Set(expandedTxIds)
    if (newExpanded.has(txId)) {
      newExpanded.delete(txId)
    } else {
      newExpanded.add(txId)
    }
    setExpandedTxIds(newExpanded)
  }

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
    const count = selectedIds.size
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
      
      toast.success('Transactions deleted', {
        description: `Successfully deleted ${count} transaction${count > 1 ? 's' : ''}`
      })
    } catch (error) {
      console.error('Failed to delete transactions', error)
      toast.error('Failed to delete transactions', {
        description: 'Please try again'
      })
    } finally {
      setDeleting(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-zen-stone flex items-center justify-center">
        <LoadingSpinner size="lg" text="Loading transactions..." />
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
    <div className="min-h-screen bg-gray-50" suppressHydrationWarning>
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
              className="px-4 py-2 bg-zen-sage text-white rounded-lg hover:bg-zen-sage-dark transition-colors text-sm flex items-center gap-2 shadow-md"
              title="Generate missing recurring transactions for the next 24 months"
            >
              🔄 Refresh Recurring
            </button>
          </div>
        </div>

        {/* Filters - Compact */}
        <div className="bg-white rounded-lg shadow p-3 md:p-4 mb-6">
          <div className="flex flex-wrap gap-3 md:gap-4 items-center">
            {/* Account Filter */}
            <div className="flex items-center gap-2">
              <label htmlFor="account" className="text-xs md:text-sm font-medium text-gray-700 whitespace-nowrap">
                Account:
              </label>
              <select
                id="account"
                value={accountId}
                onChange={(e) => updateFilter('account', e.target.value)}
                className="px-2 md:px-3 py-1 md:py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-zen-sage"
              >
                <option value="">All</option>
                {accounts.map(acc => (
                  <option key={acc.id} value={acc.id}>{acc.name}</option>
                ))}
              </select>
            </div>

            {/* Category Filter */}
            <div className="flex items-center gap-2">
              <label htmlFor="category" className="text-xs md:text-sm font-medium text-gray-700 whitespace-nowrap">
                Category:
              </label>
              <select
                id="category"
                value={categoryId}
                onChange={(e) => updateFilter('category', e.target.value)}
                className="px-2 md:px-3 py-1 md:py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-zen-sage"
              >
                <option value="">All</option>
                {categories.map(cat => (
                  <option key={cat.id} value={cat.id}>{cat.name}</option>
                ))}
              </select>
            </div>

            {/* Status Filter */}
            <div className="flex items-center gap-2">
              <label htmlFor="status" className="text-xs md:text-sm font-medium text-gray-700 whitespace-nowrap">
                Status:
              </label>
              <select
                id="status"
                value={status}
                onChange={(e) => updateFilter('status', e.target.value)}
                className="px-2 md:px-3 py-1 md:py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-zen-sage"
              >
                <option value="">All</option>
                <option value="PAID">Paid</option>
                <option value="PLANNED">Planned</option>
              </select>
            </div>

            {/* Clear Filters Button */}
            {hasFilters && (
              <button
                onClick={clearFilters}
                className="px-3 md:px-4 py-1 md:py-2 text-xs md:text-sm text-zen-sage-dark border border-zen-sage rounded-lg hover:bg-zen-sage-light transition-colors"
              >
                Clear
              </button>
            )}
          </div>
        </div>

        {/* Transactions List */}
        <div className="bg-white rounded-lg shadow">
          {transactions.length === 0 ? (
            <div className="p-12 text-center">
              <div className="text-6xl mb-4">💳</div>
              <h3 className="text-xl font-semibold text-zen-charcoal mb-3">No Transactions Yet</h3>
              <p className="text-zen-charcoal/60 mb-6 text-sm max-w-md mx-auto">
                Start tracking your finances by adding your first transaction.
              </p>
              <a
                href="/transactions/add"
                className="inline-block px-6 py-3 bg-zen-sage text-white rounded-lg hover:bg-zen-sage-dark transition-colors shadow-md"
              >
                + Add Your First Transaction
              </a>
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
                    const isExpense = tx.kind === 'EXPENSE'
                    const isTransfer = tx.kind === 'TRANSFER'
                    // For transfers, show just the amount transferred (not sum of both sides)
                    const totalAmount = isTransfer 
                      ? Math.abs(Number(tx.lines[0]?.amount || 0))
                      : tx.lines.reduce((sum, line) => sum + Math.abs(Number(line.amount)), 0)
                    // Only show split UI for non-transfers with multiple lines
                    const isSplit = !isTransfer && tx.lines.length > 1
                    const isExpanded = expandedTxIds.has(tx.id)
                    const categories = tx.lines.map(l => l.category?.name).filter(Boolean).join(', ')
                    const accounts = [...new Set(tx.lines.map(l => l.account.name))].join(' → ')

                    return (
                      <Fragment key={tx.id}>
                        {/* Main Transaction Row */}
                        <tr className={`hover:bg-zen-stone transition-colors ${selectedIds.has(tx.id) ? 'bg-zen-sage-light' : ''}`}>
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
                                <span className="text-zen-sage-dark" title={`Recurring ${tx.recurrenceRule.frequency.toLowerCase()}`}>
                                  🔄
                                </span>
                              )}
                              {isSplit && (
                                <button
                                  onClick={() => toggleExpanded(tx.id)}
                                  className="text-zen-charcoal-light hover:text-zen-charcoal transition-colors"
                                  title={isExpanded ? "Collapse split" : "Expand split"}
                                >
                                  {isExpanded ? '▼' : '▶'}
                                </button>
                              )}
                              <span>{tx.description}</span>
                              {isSplit && (
                                <span className="text-xs text-zen-charcoal-light">
                                  [Split: {tx.lines.length}]
                                </span>
                              )}
                            </div>
                            {tx.notes && (
                              <div className="text-xs text-gray-500">{tx.notes}</div>
                            )}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                            {accounts}
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-600">
                            {isTransfer ? (
                              <span className="text-zen-charcoal-light">—</span>
                            ) : isExpanded ? '—' : isSplit ? (
                              <span className="text-zen-charcoal-light italic">Multi category</span>
                            ) : (categories || '—')}
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
                                className="text-zen-sage-dark hover:text-zen-sage text-xs font-medium"
                              >
                                Edit
                              </button>
                            </td>
                          )}
                        </tr>

                        {/* Expanded Split Lines */}
                        {isSplit && isExpanded && tx.lines.map((line, lineIndex) => (
                          <tr key={`${tx.id}-line-${lineIndex}`} className="bg-zen-stone">
                            {batchDeleteMode && <td></td>}
                            <td></td>
                            <td></td>
                            <td className="px-6 py-2 text-sm text-gray-600">
                              <div className="flex items-center gap-2 pl-8">
                                <span className="text-zen-charcoal-light">└─</span>
                                <span className="text-xs">{line.account.name}</span>
                              </div>
                            </td>
                            <td></td>
                            <td className="px-6 py-2 text-sm text-gray-600">
                              <span className="text-xs">{line.category?.name || '—'}</span>
                            </td>
                            <td></td>
                            <td className={`px-6 py-2 text-sm text-right ${
                              isExpense ? 'text-red-600' : 'text-green-600'
                            }`}>
                              <span className="text-xs">
                                {Math.abs(Number(line.amount)).toFixed(2)}
                              </span>
                            </td>
                            {!batchDeleteMode && <td></td>}
                          </tr>
                        ))}
                      </Fragment>
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
