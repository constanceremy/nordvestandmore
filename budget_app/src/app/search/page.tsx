'use client'

import { useState, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

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

export default function SearchPage() {
  return (
    <Suspense fallback={<div className="p-8">Loading...</div>}>
      <SearchPageContent />
    </Suspense>
  )
}

function SearchPageContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [searchQuery, setSearchQuery] = useState('')
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)

  // Filters
  const [categoryFilter, setCategoryFilter] = useState('')
  const [accountFilter, setAccountFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [minAmount, setMinAmount] = useState('')
  const [maxAmount, setMaxAmount] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [dateField, setDateField] = useState<'paidAt' | 'effectiveFor'>('paidAt')

  // Parse smart query when URL params change (wait for accounts to load)
  useEffect(() => {
    const q = searchParams.get('q')
    console.log('useEffect triggered, query:', q, 'accounts loaded:', accounts.length)
    if (q) {
      setSearchQuery(q)
      // Reset filters before parsing
      setCategoryFilter('')
      setAccountFilter('')
      setStatusFilter('')
      setMinAmount('')
      setMaxAmount('')
      setStartDate('')
      setEndDate('')
      setDateField('paidAt')
      // Parse immediately, accounts check happens inside
      parseSmartQuery(q)
    }
  }, [searchParams])

  // Parse smart queries: accounts, weeks (W34), dates, months
  const parseSmartQuery = (query: string) => {
    const trimmed = query.trim().toLowerCase()
    console.log('Parsing query:', query, 'trimmed:', trimmed)
    
    // Check if it's a week number: W34, Week 34, week34
    const weekMatch = trimmed.match(/^(?:w|week)\s*(\d{1,2})$/i)
    if (weekMatch) {
      const weekNum = parseInt(weekMatch[1])
      const year = new Date().getFullYear()
      const weekStart = getDateOfWeek(weekNum, year)
      const weekEnd = new Date(weekStart)
      weekEnd.setDate(weekStart.getDate() + 6)
      
      const formatDate = (d: Date) => {
        const yyyy = d.getFullYear()
        const mm = String(d.getMonth() + 1).padStart(2, '0')
        const dd = String(d.getDate()).padStart(2, '0')
        return `${yyyy}-${mm}-${dd}`
      }
      
      setStartDate(formatDate(weekStart))
      setEndDate(formatDate(weekEnd))
      setDateField('paidAt')
      setSearchQuery('') // Clear text search
      setTimeout(() => handleSearch(''), 100) // Pass empty string
      return
    }

    // Check if it's a month: Jan, January, Jan 2026, 2026-01
    const monthMatch = trimmed.match(/^(?:(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)\s*(\d{4})?$/i) ||
                       trimmed.match(/^(\d{4})-(\d{1,2})$/)
    console.log('Month match:', monthMatch)
    if (monthMatch) {
      let month, year
      if (monthMatch[0].includes('-')) {
        year = parseInt(monthMatch[1])
        month = parseInt(monthMatch[2]) - 1
      } else {
        const monthNames = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        const capturedMonth = monthMatch[1].toLowerCase()
        month = monthNames.findIndex(m => capturedMonth.startsWith(m))
        year = monthMatch[2] ? parseInt(monthMatch[2]) : new Date().getFullYear()
      }
      
      console.log('Parsed month:', month, 'year:', year)
      const monthStart = new Date(year, month, 1)
      const monthEnd = new Date(year, month + 1, 0)
      console.log('Date range:', monthStart, 'to', monthEnd)
      
      // Format dates safely without timezone issues
      const formatDate = (d: Date) => {
        const yyyy = d.getFullYear()
        const mm = String(d.getMonth() + 1).padStart(2, '0')
        const dd = String(d.getDate()).padStart(2, '0')
        return `${yyyy}-${mm}-${dd}`
      }
      
      setStartDate(formatDate(monthStart))
      setEndDate(formatDate(monthEnd))
      setDateField('effectiveFor')
      setSearchQuery('') // Clear text search
      setTimeout(() => handleSearch(''), 100) // Pass empty string
      return
    }

    // Check if it's a date: 2026-01-15, 01/15/2026, 15-01-2026
    const dateMatch = trimmed.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/) ||
                     trimmed.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/) ||
                     trimmed.match(/^(\d{1,2})-(\d{1,2})-(\d{4})$/)
    if (dateMatch) {
      let dateStr
      if (dateMatch[0].startsWith('2')) {
        // YYYY-MM-DD
        dateStr = `${dateMatch[1]}-${dateMatch[2].padStart(2, '0')}-${dateMatch[3].padStart(2, '0')}`
      } else {
        // DD/MM/YYYY or DD-MM-YYYY
        dateStr = `${dateMatch[3]}-${dateMatch[2].padStart(2, '0')}-${dateMatch[1].padStart(2, '0')}`
      }
      
      setStartDate(dateStr)
      setEndDate(dateStr)
      setDateField('paidAt')
      setSearchQuery('') // Clear text search
      setTimeout(() => handleSearch(''), 100) // Pass empty string
      return
    }

    // Check if it matches an account name
    const matchingAccount = accounts.find(acc => 
      acc.name.toLowerCase().includes(trimmed) || trimmed.includes(acc.name.toLowerCase())
    )
    if (matchingAccount) {
      setAccountFilter(matchingAccount.id)
      setSearchQuery('') // Clear text search
      setTimeout(() => handleSearch(''), 100) // Pass empty string
      return
    }

    // Otherwise, treat as text search
    setTimeout(() => handleSearch(), 100)
  }

  // Get date of ISO week number
  const getDateOfWeek = (week: number, year: number): Date => {
    const date = new Date(year, 0, 1 + (week - 1) * 7)
    const dayOfWeek = date.getDay()
    const ISOweekStart = date
    if (dayOfWeek <= 4) {
      ISOweekStart.setDate(date.getDate() - date.getDay() + 1)
    } else {
      ISOweekStart.setDate(date.getDate() + 8 - date.getDay())
    }
    return ISOweekStart
  }

  // Fetch accounts and categories on load
  useEffect(() => {
    const fetchFilters = async () => {
      try {
        const [accountsRes, categoriesRes] = await Promise.all([
          fetch('/api/accounts'),
          fetch('/api/categories')
        ])
        
        if (accountsRes.ok) setAccounts(await accountsRes.json())
        if (categoriesRes.ok) setCategories(await categoriesRes.json())
      } catch (error) {
        console.error('Failed to fetch filters', error)
      }
    }
    fetchFilters()
  }, [])

  const handleSearch = async (overrideQuery?: string) => {
    setLoading(true)
    setHasSearched(true)
    
    try {
      const params = new URLSearchParams()
      const queryToUse = overrideQuery !== undefined ? overrideQuery : searchQuery
      if (queryToUse) params.set('q', queryToUse)
      if (categoryFilter) params.set('category', categoryFilter)
      if (accountFilter) params.set('account', accountFilter)
      if (statusFilter) params.set('status', statusFilter)
      if (minAmount) params.set('minAmount', minAmount)
      if (maxAmount) params.set('maxAmount', maxAmount)
      if (startDate) params.set('startDate', startDate)
      if (endDate) params.set('endDate', endDate)
      if (startDate || endDate) params.set('dateField', dateField)

      const response = await fetch(`/api/search?${params.toString()}`)
      
      if (response.ok) {
        const data = await response.json()
        setTransactions(data)
      }
    } catch (error) {
      console.error('Search failed:', error)
    } finally {
      setLoading(false)
    }
  }

  const clearSearch = () => {
    setSearchQuery('')
    setCategoryFilter('')
    setAccountFilter('')
    setStatusFilter('')
    setMinAmount('')
    setMaxAmount('')
    setStartDate('')
    setEndDate('')
    setDateField('paidAt')
    setTransactions([])
    setHasSearched(false)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto p-6">
        <h1 className="text-3xl font-bold mb-6">Search Transactions</h1>

        {/* Search Box */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex gap-4 mb-4">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSearch()
              }}
              placeholder="Search by description, merchant, notes..."
              className="flex-1 px-4 py-3 border border-gray-300 rounded-md text-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleSearch}
              disabled={loading}
              className="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 font-medium"
            >
              {loading ? 'Searching...' : '🔍 Search'}
            </button>
          </div>

          {/* Advanced Filters */}
          <details className="mt-4">
            <summary className="cursor-pointer text-sm text-gray-600 hover:text-gray-900 font-medium">
              Advanced Filters
            </summary>
            <div className="mt-4 space-y-4">
              {/* First Row */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Account
                  </label>
                  <select
                    value={accountFilter}
                    onChange={(e) => setAccountFilter(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  >
                    <option value="">All Accounts</option>
                    {accounts.map(acc => (
                      <option key={acc.id} value={acc.id}>{acc.name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Category
                  </label>
                  <select
                    value={categoryFilter}
                    onChange={(e) => setCategoryFilter(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  >
                    <option value="">All Categories</option>
                    {categories.map(cat => (
                      <option key={cat.id} value={cat.id}>{cat.name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Status
                  </label>
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  >
                    <option value="">All</option>
                    <option value="PAID">Paid</option>
                    <option value="PLANNED">Planned</option>
                  </select>
                </div>
              </div>

              {/* Second Row */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Amount Range
                </label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    value={minAmount}
                    onChange={(e) => setMinAmount(e.target.value)}
                    placeholder="Min"
                    className="w-1/2 px-3 py-2 border border-gray-300 rounded-md"
                  />
                  <input
                    type="number"
                    value={maxAmount}
                    onChange={(e) => setMaxAmount(e.target.value)}
                    placeholder="Max"
                    className="w-1/2 px-3 py-2 border border-gray-300 rounded-md"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Date Range
                </label>
                <div className="flex gap-2 mb-2">
                  <button
                    type="button"
                    onClick={() => setDateField('paidAt')}
                    className={`flex-1 py-1 px-2 rounded text-xs ${
                      dateField === 'paidAt'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    Paid At
                  </button>
                  <button
                    type="button"
                    onClick={() => setDateField('effectiveFor')}
                    className={`flex-1 py-1 px-2 rounded text-xs ${
                      dateField === 'effectiveFor'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    Effective For
                  </button>
                </div>
                <div className="flex gap-2">
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="w-1/2 px-3 py-2 border border-gray-300 rounded-md"
                  />
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="w-1/2 px-3 py-2 border border-gray-300 rounded-md"
                  />
                </div>
              </div>
            </div>
            </div>

            <button
              onClick={clearSearch}
              className="mt-4 text-sm text-blue-600 hover:text-blue-700"
            >
              Clear all filters
            </button>
          </details>
        </div>

        {/* Results */}
        {hasSearched && (
          <div className="bg-white rounded-lg shadow">
            {loading ? (
              <div className="p-8 text-center text-gray-600">
                Searching...
              </div>
            ) : transactions.length === 0 ? (
              <div className="p-8 text-center text-gray-600">
                No transactions found. Try different search terms or filters.
              </div>
            ) : (
              <>
                <div className="px-6 py-4 border-b border-gray-200">
                  <p className="text-sm text-gray-600">
                    Found <strong>{transactions.length}</strong> transaction{transactions.length !== 1 ? 's' : ''}
                  </p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-50 border-b border-gray-200">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Account</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                        <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Amount</th>
                        <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {transactions.map((tx) => {
                        const totalAmount = tx.lines.reduce((sum, line) => sum + Math.abs(Number(line.amount)), 0)
                        const isExpense = tx.kind === 'EXPENSE'
                        const categories = tx.lines.map(l => l.category?.name).filter(Boolean).join(', ')
                        const accounts = [...new Set(tx.lines.map(l => l.account.name))].join(' → ')

                        return (
                          <tr key={tx.id} className="hover:bg-gray-50">
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              {new Date(tx.paidAt).toLocaleDateString('en-GB')}
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
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-right">
                              <button
                                onClick={() => router.push(`/transactions/${tx.id}/edit`)}
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
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
