'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'

type Account = {
  id: string
  name: string
  currency: string
}

type Category = {
  id: string
  name: string
}

type TransactionLine = {
  categoryId: string
  amount: string
}

type Transaction = {
  id: string
  kind: 'EXPENSE' | 'INCOME' | 'TRANSFER'
  status: 'PLANNED' | 'PAID'
  paidAt: string
  effectiveForMonth: string | null
  description: string
  notes: string | null
  lines: Array<{
    accountId: string
    categoryId: string | null
    amount: string
  }>
}

export default function EditTransactionPage({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter()
  const [transactionId, setTransactionId] = useState<string>('')
  const [transaction, setTransaction] = useState<Transaction | null>(null)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  // Form state
  const [status, setStatus] = useState<'PLANNED' | 'PAID'>('PAID')
  const [paidAt, setPaidAt] = useState('')
  const [effectiveFor, setEffectiveFor] = useState('')
  const [description, setDescription] = useState('')
  const [notes, setNotes] = useState('')
  const [accountId, setAccountId] = useState('')
  const [amount, setAmount] = useState('')
  const [isSplit, setIsSplit] = useState(false)
  const [lines, setLines] = useState<TransactionLine[]>([{ categoryId: '', amount: '' }])
  
  // Transfer-specific state
  const [fromAccountId, setFromAccountId] = useState('')
  const [toAccountId, setToAccountId] = useState('')
  const [transferAmount, setTransferAmount] = useState('')

  useEffect(() => {
    params.then(p => {
      setTransactionId(p.id)
      fetchData(p.id)
    })
  }, [])

  const fetchData = async (id: string) => {
    setLoading(true)
    try {
      const [txRes, accountsRes, categoriesRes] = await Promise.all([
        fetch(`/api/transactions/${id}`),
        fetch('/api/accounts'),
        fetch('/api/categories')
      ])
      
      if (txRes.ok) {
        const tx = await txRes.json()
        setTransaction(tx)
        
        // Pre-fill form
        setStatus(tx.status)
        setPaidAt(tx.paidAt.split('T')[0])
        setEffectiveFor(tx.effectiveForMonth ? tx.effectiveForMonth.slice(0, 7) : '')
        setDescription(tx.description || '')
        setNotes(tx.notes || '')
        
        if (tx.kind === 'TRANSFER') {
          // For transfers, extract from/to accounts and amount
          const fromLine = tx.lines.find((l: any) => Number(l.amount) < 0)
          const toLine = tx.lines.find((l: any) => Number(l.amount) > 0)
          setFromAccountId(fromLine?.accountId || '')
          setToAccountId(toLine?.accountId || '')
          setTransferAmount(Math.abs(Number(fromLine?.amount || 0)).toString())
        } else if (tx.kind === 'EXPENSE' || tx.kind === 'INCOME') {
          setAccountId(tx.lines[0]?.accountId || '')
          const totalAmount = tx.lines.reduce((sum: number, l: any) => sum + Math.abs(Number(l.amount)), 0)
          setAmount(totalAmount.toString())
          
          if (tx.lines.length > 1) {
            setIsSplit(true)
            setLines(tx.lines.map((l: any) => ({
              categoryId: l.categoryId || '',
              amount: Math.abs(Number(l.amount)).toString()
            })))
          } else {
            setLines([{
              categoryId: tx.lines[0]?.categoryId || '',
              amount: Math.abs(Number(tx.lines[0]?.amount || 0)).toString()
            }])
          }
        }
      }
      if (accountsRes.ok) setAccounts(await accountsRes.json())
      if (categoriesRes.ok) setCategories(await categoriesRes.json())
    } catch (err) {
      console.error('Failed to fetch data', err)
      setError('Failed to load transaction')
    } finally {
      setLoading(false)
    }
  }

  const addLine = () => {
    setLines([...lines, { categoryId: '', amount: '' }])
  }

  const removeLine = (index: number) => {
    setLines(lines.filter((_, i) => i !== index))
  }

  const updateLine = (index: number, field: 'categoryId' | 'amount', value: string) => {
    const newLines = [...lines]
    newLines[index][field] = value
    setLines(newLines)
  }

  const calculateRemaining = () => {
    const total = parseFloat(amount) || 0
    const allocated = lines.reduce((sum, line) => sum + (parseFloat(line.amount) || 0), 0)
    return total - allocated
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSaving(true)

    try {
      if (!transaction) return

      // Validation for expense/income
      if (transaction.kind !== 'TRANSFER') {
        if (!accountId) throw new Error('Please select an account')
        
        if (isSplit) {
          if (lines.some(l => !l.categoryId || !l.amount)) {
            throw new Error('Please fill in all split lines')
          }
          if (calculateRemaining() !== 0) {
            throw new Error('Split amounts must equal total amount')
          }
        } else {
          if (!lines[0].categoryId || !amount) {
            throw new Error('Please select a category and enter an amount')
          }
        }
      } else {
        // Validation for transfer
        if (!fromAccountId || !toAccountId || !transferAmount) {
          throw new Error('Please fill in all transfer fields')
        }
        if (fromAccountId === toAccountId) {
          throw new Error('From and To accounts must be different')
        }
      }

      const payload = transaction.kind === 'TRANSFER' ? {
        status,
        paidAt: new Date(paidAt),
        effectiveForMonth: effectiveFor ? new Date(`${effectiveFor}-01`) : null,
        description: description || transaction.description,
        notes: notes || null,
        fromAccountId,
        toAccountId,
        transferAmount: parseFloat(transferAmount),
      } : {
        status,
        paidAt: new Date(paidAt),
        effectiveForMonth: effectiveFor ? new Date(`${effectiveFor}-01`) : null,
        description: description || transaction.description,
        notes: notes || null,
        accountId: transaction.kind !== 'TRANSFER' ? accountId : undefined,
        amount: transaction.kind !== 'TRANSFER' ? parseFloat(amount) : undefined,
        lines: transaction.kind !== 'TRANSFER' ? (isSplit ? lines.map(l => ({
          categoryId: l.categoryId,
          amount: parseFloat(l.amount)
        })) : [{
          categoryId: lines[0].categoryId,
          amount: parseFloat(amount)
        }]) : undefined,
      }

      const response = await fetch(`/api/transactions/${transactionId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || 'Failed to update transaction')
      }

      router.push('/transactions')
      router.refresh()
    } catch (err: any) {
      setError(err.message || 'Failed to update transaction')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this transaction?')) return

    try {
      const response = await fetch(`/api/transactions/${transactionId}`, {
        method: 'DELETE',
      })

      if (!response.ok) {
        throw new Error('Failed to delete transaction')
      }

      router.push('/transactions')
      router.refresh()
    } catch (err: any) {
      setError(err.message || 'Failed to delete transaction')
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">Loading...</p>
      </div>
    )
  }

  if (!transaction) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">Transaction not found</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-3xl mx-auto p-6">
        <div className="mb-6">
          <a href="/transactions" className="text-blue-600 hover:text-blue-700">
            ← Back to Transactions
          </a>
        </div>

        <div className="bg-white rounded-lg shadow p-8">
          <h1 className="text-2xl font-bold mb-6">Edit Transaction</h1>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Status */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Status *
              </label>
              <div className="flex gap-4">
                {(['PAID', 'PLANNED'] as const).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setStatus(s)}
                    className={`flex-1 py-2 px-4 rounded-md border-2 ${
                      status === s
                        ? 'border-blue-600 bg-blue-50 text-blue-700'
                        : 'border-gray-300 hover:border-gray-400'
                    }`}
                  >
                    {s.charAt(0) + s.slice(1).toLowerCase()}
                  </button>
                ))}
              </div>
            </div>

            {/* Dates */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="paidAt" className="block text-sm font-medium text-gray-700 mb-1">
                  Paid At (Date) *
                </label>
                <input
                  type="date"
                  id="paidAt"
                  value={paidAt}
                  onChange={(e) => setPaidAt(e.target.value)}
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              <div>
                <label htmlFor="effectiveFor" className="block text-sm font-medium text-gray-700 mb-1">
                  Effective For (Month) *
                </label>
                <input
                  type="month"
                  id="effectiveFor"
                  value={effectiveFor}
                  onChange={(e) => setEffectiveFor(e.target.value)}
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
            </div>

            {/* Description */}
            <div>
              <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-1">
                {transaction.kind === 'EXPENSE' ? 'Store / Merchant' : transaction.kind === 'INCOME' ? 'Source' : 'Description'}
              </label>
              <input
                type="text"
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={transaction.kind === 'EXPENSE' ? 'e.g., Netto' : transaction.kind === 'INCOME' ? 'e.g., Salary' : 'e.g., Moving funds'}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>

            {/* Transfer Fields */}
            {transaction.kind === 'TRANSFER' && (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="fromAccount" className="block text-sm font-medium text-gray-700 mb-1">
                      From Account *
                    </label>
                    <select
                      id="fromAccount"
                      value={fromAccountId}
                      onChange={(e) => setFromAccountId(e.target.value)}
                      required
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    >
                      <option value="">Select account</option>
                      {accounts.map(acc => (
                        <option key={acc.id} value={acc.id}>{acc.name} ({acc.currency})</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label htmlFor="toAccount" className="block text-sm font-medium text-gray-700 mb-1">
                      To Account *
                    </label>
                    <select
                      id="toAccount"
                      value={toAccountId}
                      onChange={(e) => setToAccountId(e.target.value)}
                      required
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    >
                      <option value="">Select account</option>
                      {accounts.map(acc => (
                        <option key={acc.id} value={acc.id}>{acc.name} ({acc.currency})</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label htmlFor="transferAmount" className="block text-sm font-medium text-gray-700 mb-1">
                    Amount *
                  </label>
                  <input
                    type="number"
                    id="transferAmount"
                    value={transferAmount}
                    onChange={(e) => setTransferAmount(e.target.value)}
                    step="0.01"
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  />
                </div>
              </>
            )}

            {/* Expense/Income Fields */}
            {transaction.kind !== 'TRANSFER' && (
              <>
                {/* Account & Amount */}
                <div>
                  <label htmlFor="account" className="block text-sm font-medium text-gray-700 mb-1">
                    Account *
                  </label>
                  <select
                    id="account"
                    value={accountId}
                    onChange={(e) => setAccountId(e.target.value)}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  >
                    <option value="">Select account</option>
                    {accounts.map(acc => (
                      <option key={acc.id} value={acc.id}>{acc.name} ({acc.currency})</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label htmlFor="amount" className="block text-sm font-medium text-gray-700 mb-1">
                    Amount *
                  </label>
                  <input
                    type="number"
                    id="amount"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    step="0.01"
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  />
                </div>

                {/* Split Toggle */}
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="split"
                    checked={isSplit}
                    onChange={(e) => setIsSplit(e.target.checked)}
                    className="rounded"
                  />
                  <label htmlFor="split" className="text-sm font-medium text-gray-700">
                    Split across multiple categories
                  </label>
                </div>

                {/* Category/Split Lines */}
                {isSplit ? (
                  <div className="space-y-3 p-4 bg-gray-50 rounded-lg">
                <div className="flex justify-between items-center">
                  <p className="text-sm font-medium text-gray-700">Split by category:</p>
                  <p className={`text-sm font-semibold ${calculateRemaining() === 0 ? 'text-green-600' : 'text-red-600'}`}>
                    Remaining: {calculateRemaining().toFixed(2)}
                  </p>
                </div>
                
                {lines.map((line, index) => (
                  <div key={index} className="flex gap-2">
                    <select
                      value={line.categoryId}
                      onChange={(e) => updateLine(index, 'categoryId', e.target.value)}
                      required
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-md"
                    >
                      <option value="">Select category</option>
                      {categories.map(cat => (
                        <option key={cat.id} value={cat.id}>{cat.name}</option>
                      ))}
                    </select>
                    <input
                      type="number"
                      value={line.amount}
                      onChange={(e) => updateLine(index, 'amount', e.target.value)}
                      step="0.01"
                      required
                      className="w-32 px-3 py-2 border border-gray-300 rounded-md"
                    />
                    {lines.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeLine(index)}
                        className="px-3 py-2 text-red-600 hover:bg-red-50 rounded-md"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                ))}
                
                <button
                  type="button"
                  onClick={addLine}
                  className="text-sm text-blue-600 hover:text-blue-700"
                >
                  + Add line
                </button>
              </div>
            ) : (
              <div>
                <label htmlFor="category" className="block text-sm font-medium text-gray-700 mb-1">
                  Category *
                </label>
                <select
                  id="category"
                  value={lines[0].categoryId}
                  onChange={(e) => updateLine(0, 'categoryId', e.target.value)}
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                >
                  <option value="">Select category</option>
                  {categories.map(cat => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
                </select>
              </div>
            )}
              </>
            )}

            {/* Notes */}
            <div>
              <label htmlFor="notes" className="block text-sm font-medium text-gray-700 mb-1">
                Notes (optional)
              </label>
              <textarea
                id="notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={2}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>

            {/* Actions */}
            <div className="flex gap-4 pt-4">
              <button
                type="submit"
                disabled={saving}
                className="flex-1 py-2 px-4 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
              <button
                type="button"
                onClick={handleDelete}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
              >
                Delete
              </button>
              <button
                type="button"
                onClick={() => router.push('/transactions')}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
