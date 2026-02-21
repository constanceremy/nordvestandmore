'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'

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

export default function AddTransactionPage() {
  const router = useRouter()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Form state
  const [kind, setKind] = useState<'EXPENSE' | 'INCOME' | 'TRANSFER'>('EXPENSE')
  const [status, setStatus] = useState<'PLANNED' | 'PAID'>('PAID')
  const [paidAt, setPaidAt] = useState(new Date().toISOString().split('T')[0])
  const [effectiveFor, setEffectiveFor] = useState(new Date().toISOString().slice(0, 7)) // YYYY-MM
  const [description, setDescription] = useState('')
  const [notes, setNotes] = useState('')
  
  // Expense/Income
  const [accountId, setAccountId] = useState('')
  const [amount, setAmount] = useState('')
  const [isSplit, setIsSplit] = useState(false)
  const [lines, setLines] = useState<TransactionLine[]>([{ categoryId: '', amount: '' }])
  
  // Transfer
  const [fromAccountId, setFromAccountId] = useState('')
  const [toAccountId, setToAccountId] = useState('')
  const [transferAmount, setTransferAmount] = useState('')

  // Recurrence
  const [isRecurring, setIsRecurring] = useState(false)
  const [frequency, setFrequency] = useState<'DAILY' | 'WEEKLY' | 'MONTHLY' | 'YEARLY'>('MONTHLY')
  const [interval, setInterval] = useState(1)
  const [repeatUntil, setRepeatUntil] = useState('')
  const [recurrencePattern, setRecurrencePattern] = useState<'simple' | 'nth-weekday'>('simple')
  const [dayOfWeek, setDayOfWeek] = useState<number | null>(null)
  const [weekOfMonth, setWeekOfMonth] = useState<number | null>(null)

  // Quick category creation
  const [showCategoryForm, setShowCategoryForm] = useState(false)
  const [newCategoryName, setNewCategoryName] = useState('')
  const [creatingCategory, setCreatingCategory] = useState(false)

  // Notes toggle
  const [showNotes, setShowNotes] = useState(false)

  // Recurring confirmation modal
  const [showRecurringPreview, setShowRecurringPreview] = useState(false)
  const [recurringPreview, setRecurringPreview] = useState<Array<{
    paidAt: string
    effectiveFor: string
    amount: number
  }>>([])

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [accountsRes, categoriesRes] = await Promise.all([
        fetch('/api/accounts'),
        fetch('/api/categories')
      ])
      
      if (accountsRes.ok) setAccounts(await accountsRes.json())
      if (categoriesRes.ok) setCategories(await categoriesRes.json())
    } catch (err) {
      console.error('Failed to fetch data', err)
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

  const handleCreateCategory = async () => {
    if (!newCategoryName.trim()) return
    
    setCreatingCategory(true)
    try {
      const response = await fetch('/api/categories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newCategoryName.trim() }),
      })

      if (response.ok) {
        const newCategory = await response.json()
        setCategories([...categories, newCategory])
        setNewCategoryName('')
        setShowCategoryForm(false)
        // Auto-select the new category
        if (!isSplit) {
          updateLine(0, 'categoryId', newCategory.id)
        }
      } else {
        alert('Failed to create category')
      }
    } catch (error) {
      console.error('Error creating category:', error)
      alert('Failed to create category')
    } finally {
      setCreatingCategory(false)
    }
  }

  const generateRecurringPreview = () => {
    const dates = generateRecurringDates(
      new Date(paidAt),
      frequency,
      interval,
      repeatUntil ? new Date(repeatUntil) : null,
      recurrencePattern === 'nth-weekday' ? dayOfWeek : null,
      recurrencePattern === 'nth-weekday' ? weekOfMonth : null
    )

    // Calculate month offset
    const originalPaidAt = new Date(paidAt)
    const originalEffectiveFor = new Date(`${effectiveFor}-01`)
    const monthOffset = (originalEffectiveFor.getFullYear() - originalPaidAt.getFullYear()) * 12 
                      + (originalEffectiveFor.getMonth() - originalPaidAt.getMonth())

    const totalAmount = kind === 'TRANSFER' 
      ? parseFloat(transferAmount) 
      : (isSplit ? lines.reduce((sum, l) => sum + parseFloat(l.amount || '0'), 0) : parseFloat(amount))

    const preview = dates.map(date => {
      const effectiveMonth = new Date(date)
      effectiveMonth.setMonth(effectiveMonth.getMonth() + monthOffset)
      return {
        paidAt: date.toISOString().split('T')[0],
        effectiveFor: `${effectiveMonth.getFullYear()}-${String(effectiveMonth.getMonth() + 1).padStart(2, '0')}`,
        amount: totalAmount
      }
    })

    setRecurringPreview(preview)
    setShowRecurringPreview(true)
  }

  // Helper function to generate recurring dates (same logic as backend)
  const generateRecurringDates = (
    startDate: Date,
    freq: 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'YEARLY',
    intv: number,
    until: Date | null,
    dow: number | null,
    wom: number | null
  ): Date[] => {
    const dates: Date[] = []
    const horizon = new Date()
    horizon.setMonth(horizon.getMonth() + 24) // 24 months
    const endDate = until && until < horizon ? until : horizon

    // Nth weekday pattern
    if (dow !== null && wom !== null) {
      let currentDate = new Date(startDate)
      currentDate.setDate(1)
      
      while (currentDate <= endDate) {
        const nthWeekday = getNthWeekdayOfMonth(currentDate.getFullYear(), currentDate.getMonth(), dow, wom)
        if (nthWeekday && nthWeekday >= startDate && nthWeekday <= endDate) {
          dates.push(new Date(nthWeekday))
        }
        currentDate.setMonth(currentDate.getMonth() + 1)
      }
      return dates
    }

    // Simple interval pattern
    let currentDate = new Date(startDate)
    while (currentDate <= endDate) {
      dates.push(new Date(currentDate))
      switch (freq) {
        case 'DAILY':
          currentDate.setDate(currentDate.getDate() + intv)
          break
        case 'WEEKLY':
          currentDate.setDate(currentDate.getDate() + (7 * intv))
          break
        case 'MONTHLY':
          currentDate.setMonth(currentDate.getMonth() + intv)
          break
        case 'YEARLY':
          currentDate.setFullYear(currentDate.getFullYear() + intv)
          break
      }
    }
    return dates
  }

  const getNthWeekdayOfMonth = (year: number, month: number, dayOfWeek: number, weekOfMonth: number): Date | null => {
    const firstDay = new Date(year, month, 1)
    if (weekOfMonth === -1) {
      const lastDay = new Date(year, month + 1, 0)
      const lastDayOfWeek = lastDay.getDay()
      const daysBack = (lastDayOfWeek - dayOfWeek + 7) % 7
      return new Date(year, month, lastDay.getDate() - daysBack)
    } else {
      const firstDayOfWeek = firstDay.getDay()
      const daysUntilTarget = (dayOfWeek - firstDayOfWeek + 7) % 7
      const targetDate = 1 + daysUntilTarget + ((weekOfMonth - 1) * 7)
      const result = new Date(year, month, targetDate)
      if (result.getMonth() !== month) return null
      return result
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    // If recurring and not yet confirmed, show preview instead of submitting
    if (isRecurring && recurringPreview.length === 0) {
      generateRecurringPreview()
      return
    }

    setLoading(true)

    try {
      // Validation
      if (kind === 'TRANSFER') {
        if (!fromAccountId || !toAccountId || !transferAmount) {
          throw new Error('Please fill in all transfer fields')
        }
        if (fromAccountId === toAccountId) {
          throw new Error('Cannot transfer to the same account')
        }
      } else {
        if (!accountId) {
          throw new Error('Please select an account')
        }
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
      }

      const payload = {
        kind,
        status,
        paidAt: new Date(paidAt),
        effectiveForMonth: new Date(`${effectiveFor}-01`),
        description: description || (kind === 'TRANSFER' ? 'Transfer' : 'Transaction'),
        notes: notes || null,
        accountId: kind !== 'TRANSFER' ? accountId : undefined,
        amount: kind !== 'TRANSFER' ? parseFloat(amount) : undefined,
        lines: kind !== 'TRANSFER' ? (isSplit ? lines.map(l => ({
          categoryId: l.categoryId,
          amount: parseFloat(l.amount)
        })) : [{
          categoryId: lines[0].categoryId,
          amount: parseFloat(amount)
        }]) : undefined,
        fromAccountId: kind === 'TRANSFER' ? fromAccountId : undefined,
        toAccountId: kind === 'TRANSFER' ? toAccountId : undefined,
        transferAmount: kind === 'TRANSFER' ? parseFloat(transferAmount) : undefined,
        // Recurrence
        isRecurring,
        frequency: isRecurring ? frequency : undefined,
        interval: isRecurring ? interval : undefined,
        repeatUntil: isRecurring && repeatUntil ? new Date(repeatUntil) : undefined,
        dayOfWeek: isRecurring && recurrencePattern === 'nth-weekday' ? dayOfWeek : undefined,
        weekOfMonth: isRecurring && recurrencePattern === 'nth-weekday' ? weekOfMonth : undefined,
      }

      const response = await fetch('/api/transactions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || 'Failed to create transaction')
      }

      router.push('/accounts')
      router.refresh()
      
      // Show success toast
      if (isRecurring) {
        toast.success(`Recurring ${kind.toLowerCase()} created!`, {
          description: `${recurringPreview.length} transactions scheduled`
        })
      } else {
        toast.success(`${kind === 'TRANSFER' ? 'Transfer' : kind.charAt(0) + kind.slice(1).toLowerCase()} added!`, {
          description: description || 'Transaction saved successfully'
        })
      }
    } catch (err: any) {
      setError(err.message || 'Failed to create transaction')
      toast.error('Failed to create transaction', {
        description: err.message
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-zen-stone">
      <div className="max-w-2xl mx-auto p-4 md:p-6">
        <div className="mb-4">
          <a href="/transactions" className="text-zen-sage-dark hover:text-zen-sage text-sm">
            ← Back
          </a>
        </div>

        <div className="bg-zen-stone-light rounded-xl shadow-md p-4 md:p-6">
          <h1 className="text-xl font-bold mb-4 text-zen-charcoal">Add Transaction</h1>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 text-sm rounded-lg mb-4 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Transaction Type & Status - Side by side */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-zen-charcoal mb-1.5">Type</label>
                <div className="flex gap-1">
                  {(['EXPENSE', 'INCOME', 'TRANSFER'] as const).map((type) => (
                    <button
                      key={type}
                      type="button"
                      onClick={() => setKind(type)}
                      className={`flex-1 py-2 px-2 text-xs rounded-lg border transition-colors ${
                        kind === type
                          ? 'border-zen-sage bg-zen-sage text-white'
                          : 'border-zen-stone-dark hover:border-zen-sand bg-white'
                      }`}
                    >
                      {type.charAt(0) + type.slice(1).toLowerCase()}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-zen-charcoal mb-1.5">Status</label>
                <div className="flex gap-1">
                  {(['PAID', 'PLANNED'] as const).map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setStatus(s)}
                      className={`flex-1 py-2 px-2 text-xs rounded-lg border transition-colors ${
                        status === s
                          ? 'border-zen-sage bg-zen-sage text-white'
                          : 'border-zen-stone-dark hover:border-zen-sand bg-white'
                      }`}
                    >
                      {s.charAt(0) + s.slice(1).toLowerCase()}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Dates - Side by side */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="paidAt" className="block text-xs font-medium text-zen-charcoal mb-1.5">
                  Paid At
                </label>
                <input
                  type="date"
                  id="paidAt"
                  value={paidAt}
                  onChange={(e) => setPaidAt(e.target.value)}
                  required
                  className="w-full px-3 py-2 text-sm text-sm border border-zen-stone-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                />
              </div>

              <div>
                <label htmlFor="effectiveFor" className="block text-xs font-medium text-zen-charcoal mb-1.5">
                  Effective For
                </label>
                <input
                  type="month"
                  id="effectiveFor"
                  value={effectiveFor}
                  onChange={(e) => setEffectiveFor(e.target.value)}
                  required
                  className="w-full px-3 py-2 text-sm border border-zen-stone-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                />
                <p className="text-xs text-zen-charcoal-light mt-1">Which budget month</p>
              </div>
            </div>

            {/* Description / Store / Source */}
            {kind !== 'TRANSFER' && (
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <label htmlFor="description" className="block text-xs font-medium text-zen-charcoal mb-1.5">
                    {kind === 'EXPENSE' && 'Store / Merchant'}
                    {kind === 'INCOME' && 'Source'}
                  </label>
                  <input
                    type="text"
                    id="description"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder={
                      kind === 'EXPENSE' ? 'e.g., Netto, Føtex' :
                      'e.g., Salary, Freelance'
                    }
                    className="w-full px-3 py-2 text-sm border border-zen-stone-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                  />
                </div>
                <div>
                  <label htmlFor="amount" className="block text-xs font-medium text-zen-charcoal mb-1.5">
                    Amount *
                  </label>
                  <input
                    type="number"
                    id="amount"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    step="0.01"
                    required
                    placeholder="0.00"
                    className="w-full px-3 py-2 text-sm border border-zen-stone-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                  />
                </div>
              </div>
            )}

            {kind === 'TRANSFER' && (
              <div>
                <label htmlFor="description" className="block text-xs font-medium text-zen-charcoal mb-1.5">
                  Description
                </label>
                <input
                  type="text"
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g., Moving to savings"
                  className="w-full px-3 py-2 text-sm border border-zen-stone-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                />
              </div>
            )}

            {/* Transfer Fields */}
            {kind === 'TRANSFER' && (
              <div className="space-y-4 p-4 bg-gray-50 rounded-lg">
                <div>
                  <label htmlFor="fromAccount" className="block text-xs font-medium text-zen-charcoal mb-1.5">
                    From Account *
                  </label>
                  <select
                    id="fromAccount"
                    value={fromAccountId}
                    onChange={(e) => setFromAccountId(e.target.value)}
                    required
                    className="w-full px-3 py-2 text-sm border border-zen-stone-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                  >
                    <option value="">Select account</option>
                    {accounts.map(acc => (
                      <option key={acc.id} value={acc.id}>{acc.name} ({acc.currency})</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label htmlFor="toAccount" className="block text-xs font-medium text-zen-charcoal mb-1.5">
                    To Account *
                  </label>
                  <select
                    id="toAccount"
                    value={toAccountId}
                    onChange={(e) => setToAccountId(e.target.value)}
                    required
                    className="w-full px-3 py-2 text-sm border border-zen-stone-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                  >
                    <option value="">Select account</option>
                    {accounts.map(acc => (
                      <option key={acc.id} value={acc.id}>{acc.name} ({acc.currency})</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label htmlFor="transferAmount" className="block text-xs font-medium text-zen-charcoal mb-1.5">
                    Amount *
                  </label>
                  <input
                    type="number"
                    id="transferAmount"
                    value={transferAmount}
                    onChange={(e) => setTransferAmount(e.target.value)}
                    step="0.01"
                    required
                    placeholder="0.00"
                    className="w-full px-3 py-2 text-sm border border-zen-stone-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                  />
                </div>
              </div>
            )}

            {/* Expense/Income Fields */}
            {kind !== 'TRANSFER' && (
              <div className="space-y-4">
                <div>
                  <label htmlFor="account" className="block text-xs font-medium text-zen-charcoal mb-1.5">
                    Account *
                  </label>
                  <select
                    id="account"
                    value={accountId}
                    onChange={(e) => setAccountId(e.target.value)}
                    required
                    className="w-full px-3 py-2 text-sm border border-zen-stone-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                  >
                    <option value="">Select account</option>
                    {accounts.map(acc => (
                      <option key={acc.id} value={acc.id}>{acc.name} ({acc.currency})</option>
                    ))}
                  </select>
                </div>

                {/* Split Toggle */}
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="split"
                    checked={isSplit}
                    onChange={(e) => setIsSplit(e.target.checked)}
                    className="rounded text-zen-sage focus:ring-zen-sage"
                  />
                  <label htmlFor="split" className="text-xs text-zen-charcoal">
                    Split across categories
                  </label>
                </div>

                {/* Category/Split Lines */}
                {isSplit ? (
                  <div className="space-y-2 p-3 bg-zen-stone rounded-lg">
                    <div className="flex justify-between items-center">
                      <p className="text-xs font-medium text-zen-charcoal">Split by category</p>
                      <p className={`text-xs font-semibold ${calculateRemaining() === 0 ? 'text-green-600' : 'text-red-600'}`}>
                        Remaining: {calculateRemaining().toFixed(2)}
                      </p>
                    </div>
                    
                    {lines.map((line, index) => (
                      <div key={index} className="flex gap-2">
                        <select
                          value={line.categoryId}
                          onChange={(e) => updateLine(index, 'categoryId', e.target.value)}
                          required
                          className="flex-1 px-2 py-1.5 text-sm border border-zen-stone-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                        >
                          <option value="">Category</option>
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
                          placeholder="0.00"
                          className="w-24 px-2 py-1.5 text-sm border border-zen-stone-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                        />
                        {lines.length > 1 && (
                          <button
                            type="button"
                            onClick={() => removeLine(index)}
                            className="px-2 py-1.5 text-xs text-red-600 hover:bg-red-50 rounded-lg"
                          >
                            ✕
                          </button>
                        )}
                      </div>
                    ))}
                    
                    <button
                      type="button"
                      onClick={addLine}
                      className="text-xs text-zen-sage-dark hover:text-zen-sage"
                    >
                      + Add line
                    </button>
                  </div>
                ) : (
                  <div>
                    <label htmlFor="category" className="block text-xs font-medium text-zen-charcoal mb-1.5">
                      Category *
                    </label>
                    {showCategoryForm ? (
                      <div className="space-y-2 p-3 bg-gray-50 rounded-lg border border-zen-stone-dark">
                        <input
                          type="text"
                          value={newCategoryName}
                          onChange={(e) => setNewCategoryName(e.target.value)}
                          placeholder="New category name"
                          className="w-full px-3 py-2 text-sm border border-zen-stone-dark rounded-lg"
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.preventDefault()
                              handleCreateCategory()
                            }
                          }}
                        />
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={handleCreateCategory}
                            disabled={creatingCategory || !newCategoryName.trim()}
                            className="flex-1 px-3 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm"
                          >
                            {creatingCategory ? 'Creating...' : 'Create'}
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setShowCategoryForm(false)
                              setNewCategoryName('')
                            }}
                            className="flex-1 px-3 py-2 text-sm bg-zen-stone-dark text-zen-charcoal rounded-lg hover:bg-zen-sand text-sm"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex gap-2">
                        <select
                          id="category"
                          value={lines[0].categoryId}
                          onChange={(e) => updateLine(0, 'categoryId', e.target.value)}
                          required
                          className="flex-1 px-3 py-2 text-sm border border-zen-stone-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                        >
                          <option value="">Select category</option>
                          {categories.map(cat => (
                            <option key={cat.id} value={cat.id}>{cat.name}</option>
                          ))}
                        </select>
                        <button
                          type="button"
                          onClick={() => setShowCategoryForm(true)}
                          className="px-4 py-2 bg-zen-sage text-white rounded-lg hover:bg-zen-sage-dark text-sm whitespace-nowrap"
                        >
                          + New
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Notes - Collapsible */}
            {!showNotes ? (
              <button
                type="button"
                onClick={() => setShowNotes(true)}
                className="text-xs text-zen-sage-dark hover:text-zen-sage flex items-center gap-1"
              >
                + Add note
              </button>
            ) : (
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label htmlFor="notes" className="block text-xs font-medium text-zen-charcoal">
                    Notes
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      setShowNotes(false)
                      setNotes('')
                    }}
                    className="text-xs text-zen-charcoal-light hover:text-zen-charcoal"
                  >
                    ✕
                  </button>
                </div>
                <textarea
                  id="notes"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={2}
                  placeholder="Additional notes..."
                  className="w-full px-3 py-2 text-sm border border-zen-stone-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                />
              </div>
            )}

            {/* Recurring Transaction */}
            <div className="border-t pt-4">
              {!isRecurring ? (
                <button
                  type="button"
                  onClick={() => setIsRecurring(true)}
                  className="text-xs text-zen-sage-dark hover:text-zen-sage flex items-center gap-1"
                >
                  🔄 Make this recurring
                </button>
              ) : (
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <label className="text-xs font-medium text-zen-charcoal">
                      🔄 Recurring Transaction
                    </label>
                    <button
                      type="button"
                      onClick={() => setIsRecurring(false)}
                      className="text-xs text-zen-charcoal-light hover:text-zen-charcoal"
                    >
                      ✕
                    </button>
                  </div>

              {isRecurring && (
                <div className="space-y-3">
                  {/* Pattern Type */}
                  <div>
                    <label className="block text-xs font-medium text-zen-charcoal mb-1.5">
                      Pattern
                    </label>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setRecurrencePattern('simple')}
                        className={`flex-1 py-1.5 px-3 text-xs rounded-lg border transition-colors ${
                          recurrencePattern === 'simple'
                            ? 'border-zen-sage bg-zen-sage text-white'
                            : 'border-zen-stone-dark hover:border-zen-sand bg-white'
                        }`}
                      >
                        Simple
                      </button>
                      <button
                        type="button"
                        onClick={() => setRecurrencePattern('nth-weekday')}
                        className={`flex-1 py-1.5 px-3 text-xs rounded-lg border transition-colors ${
                          recurrencePattern === 'nth-weekday'
                            ? 'border-zen-sage bg-zen-sage text-white'
                            : 'border-zen-stone-dark hover:border-zen-sand bg-white'
                        }`}
                      >
                        Nth Weekday
                      </button>
                    </div>
                  </div>

                  {recurrencePattern === 'simple' ? (
                    <>
                      {/* Simple Pattern: Frequency + Interval */}
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label htmlFor="interval" className="block text-xs font-medium text-zen-charcoal mb-1.5">
                            Every *
                          </label>
                          <input
                            type="number"
                            id="interval"
                            value={interval}
                            onChange={(e) => setInterval(Math.max(1, parseInt(e.target.value) || 1))}
                            min="1"
                            className="w-full px-3 py-2 text-sm border border-zen-stone-dark rounded-lg"
                          />
                        </div>
                        <div>
                          <label htmlFor="frequency" className="block text-xs font-medium text-zen-charcoal mb-1.5">
                            Period *
                          </label>
                          <select
                            id="frequency"
                            value={frequency}
                            onChange={(e) => setFrequency(e.target.value as any)}
                            className="w-full px-3 py-2 text-sm border border-zen-stone-dark rounded-lg"
                          >
                            <option value="DAILY">Day(s)</option>
                            <option value="WEEKLY">Week(s)</option>
                            <option value="MONTHLY">Month(s)</option>
                            <option value="YEARLY">Year(s)</option>
                          </select>
                        </div>
                      </div>
                      <p className="text-xs text-zen-charcoal-light">
                        {interval === 1 ? (
                          <>
                            {frequency === 'DAILY' && 'Every day'}
                            {frequency === 'WEEKLY' && 'Every week'}
                            {frequency === 'MONTHLY' && 'Every month'}
                            {frequency === 'YEARLY' && 'Every year'}
                          </>
                        ) : (
                          <>
                            {frequency === 'DAILY' && `Every ${interval} days`}
                            {frequency === 'WEEKLY' && `Every ${interval} weeks`}
                            {frequency === 'MONTHLY' && `Every ${interval} months`}
                            {frequency === 'YEARLY' && `Every ${interval} years`}
                          </>
                        )}
                      </p>
                    </>
                  ) : (
                    <>
                      {/* Nth Weekday Pattern */}
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label htmlFor="weekOfMonth" className="block text-xs font-medium text-zen-charcoal mb-1.5">
                            Week *
                          </label>
                          <select
                            id="weekOfMonth"
                            value={weekOfMonth ?? ''}
                            onChange={(e) => setWeekOfMonth(e.target.value ? parseInt(e.target.value) : null)}
                            required
                            className="w-full px-3 py-2 text-sm border border-zen-stone-dark rounded-lg"
                          >
                            <option value="">Select week</option>
                            <option value="1">First</option>
                            <option value="2">Second</option>
                            <option value="3">Third</option>
                            <option value="4">Fourth</option>
                            <option value="-1">Last</option>
                          </select>
                        </div>
                        <div>
                          <label htmlFor="dayOfWeek" className="block text-xs font-medium text-zen-charcoal mb-1.5">
                            Day *
                          </label>
                          <select
                            id="dayOfWeek"
                            value={dayOfWeek ?? ''}
                            onChange={(e) => setDayOfWeek(e.target.value ? parseInt(e.target.value) : null)}
                            required
                            className="w-full px-3 py-2 text-sm border border-zen-stone-dark rounded-lg"
                          >
                            <option value="">Select day</option>
                            <option value="0">Sunday</option>
                            <option value="1">Monday</option>
                            <option value="2">Tuesday</option>
                            <option value="3">Wednesday</option>
                            <option value="4">Thursday</option>
                            <option value="5">Friday</option>
                            <option value="6">Saturday</option>
                          </select>
                        </div>
                      </div>
                      <p className="text-xs text-zen-charcoal-light">
                        {weekOfMonth && dayOfWeek !== null && (
                          <>
                            {weekOfMonth === -1 ? 'Last' : ['First', 'Second', 'Third', 'Fourth'][weekOfMonth - 1]}{' '}
                            {['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][dayOfWeek]}{' '}
                            of every month
                          </>
                        )}
                      </p>
                    </>
                  )}

                  <div>
                    <label htmlFor="repeatUntil" className="block text-xs font-medium text-zen-charcoal mb-1.5">
                      Repeat Until (optional)
                    </label>
                    <input
                      type="date"
                      id="repeatUntil"
                      value={repeatUntil}
                      onChange={(e) => setRepeatUntil(e.target.value)}
                      min={paidAt}
                      className="w-full px-3 py-2 text-sm border border-zen-stone-dark rounded-lg"
                    />
                    <p className="text-xs text-zen-charcoal-light mt-1">
                      Leave blank to repeat indefinitely
                    </p>
                  </div>

                  <div className="bg-zen-sage-light border border-zen-sage rounded-lg p-3">
                    <p className="text-sm text-zen-charcoal">
                      <strong>💡 How it works:</strong> We'll create planned transactions for the next 24 months. 
                      {repeatUntil && ` Stops on ${new Date(repeatUntil).toLocaleDateString('en-GB')}.`}
                    </p>
                  </div>
                </div>
              )}
                </div>
              )}
            </div>

            {/* Submit */}
            <div className="flex gap-4 pt-4">
              <button
                type="submit"
                disabled={loading}
                className="flex-1 py-2 px-4 bg-zen-sage text-white rounded-lg hover:bg-zen-sage-dark focus:outline-none focus:ring-2 focus:ring-zen-sage disabled:opacity-50"
              >
                {loading ? 'Creating...' : (isRecurring && recurringPreview.length === 0 ? 'Preview Recurring' : 'Create Transaction')}
              </button>
              <button
                type="button"
                onClick={() => router.push('/accounts')}
                className="px-4 py-2 bg-zen-stone-dark text-zen-charcoal rounded-lg hover:bg-zen-sand"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Recurring Preview Modal */}
      {showRecurringPreview && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-xl font-bold text-gray-900">Confirm Recurring Transactions</h2>
              <p className="text-sm text-gray-600 mt-1">
                This will create {recurringPreview.length} transaction{recurringPreview.length !== 1 ? 's' : ''}
              </p>
            </div>
            
            <div className="flex-1 overflow-y-auto px-6 py-4">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-zen-charcoal-light uppercase">#</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-zen-charcoal-light uppercase">Paid At</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-zen-charcoal-light uppercase">Effective For</th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-zen-charcoal-light uppercase">Amount</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {recurringPreview.map((item, index) => (
                      <tr key={index} className={index === 0 ? 'bg-blue-50' : ''}>
                        <td className="px-4 py-2 text-sm text-gray-900">
                          {index + 1}
                          {index === 0 && <span className="ml-2 text-xs text-zen-sage-dark">(First)</span>}
                        </td>
                        <td className="px-4 py-2 text-sm text-gray-900">
                          {new Date(item.paidAt).toLocaleDateString('en-GB')}
                        </td>
                        <td className="px-4 py-2 text-sm text-gray-600">
                          {item.effectiveFor}
                        </td>
                        <td className="px-4 py-2 text-sm text-right font-medium text-gray-900">
                          {item.amount.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            
            <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 flex gap-3">
              <button
                onClick={() => {
                  setShowRecurringPreview(false)
                  setRecurringPreview([])
                }}
                className="flex-1 px-4 py-2 border border-zen-stone-dark rounded-lg text-zen-charcoal hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowRecurringPreview(false)
                  // The preview is already generated, so the next submit will proceed
                  const form = document.querySelector('form') as HTMLFormElement
                  if (form) form.requestSubmit()
                }}
                disabled={loading}
                className="flex-1 px-4 py-2 bg-zen-sage text-white rounded-lg hover:bg-zen-sage-dark disabled:opacity-50"
              >
                {loading ? 'Creating...' : `Confirm & Create ${recurringPreview.length} Transactions`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
