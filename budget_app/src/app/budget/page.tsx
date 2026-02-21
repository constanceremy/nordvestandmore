'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import { useEffect, useState } from 'react'

type CategoryTotal = {
  name: string
  planned: number
  paid: number
  budget: number | null
}

type BudgetData = {
  categories: CategoryTotal[]
  totalPlanned: number
  totalPaid: number
  totalDelta: number
}

export default function BudgetPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  
  const [budgetData, setBudgetData] = useState<BudgetData | null>(null)
  const [loading, setLoading] = useState(true)

  const month = searchParams.get('month') || new Date().toISOString().slice(0, 7)
  const groupBy = searchParams.get('groupBy') || 'effectiveFor'
  const status = searchParams.get('status') || 'both'

  useEffect(() => {
    fetchBudgetData()
  }, [month, groupBy, status])

  const fetchBudgetData = async () => {
    setLoading(true)
    try {
      const response = await fetch(`/api/overview?month=${month}&groupBy=${groupBy}&status=${status}`)
      const data = await response.json()
      setBudgetData(data)
    } catch (error) {
      console.error('Failed to fetch budget data', error)
    } finally {
      setLoading(false)
    }
  }

  const updateParam = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set(key, value)
    router.push(`?${params.toString()}`)
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">Loading budget data...</p>
      </div>
    )
  }

  if (!budgetData) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">Failed to load budget data</p>
      </div>
    )
  }

  const { categories, totalPlanned, totalPaid, totalDelta } = budgetData

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto p-6">
        <h1 className="text-3xl font-bold mb-6">Budget Analysis</h1>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Month Picker */}
            <div>
              <label htmlFor="month" className="block text-sm font-medium text-gray-700 mb-2">
                Month
              </label>
              <input
                type="month"
                id="month"
                value={month}
                onChange={(e) => updateParam('month', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>

            {/* Group By */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Group By
              </label>
              <div className="flex gap-2">
                <button
                  onClick={() => updateParam('groupBy', 'effectiveFor')}
                  className={`flex-1 py-2 px-3 text-center rounded-md border ${
                    groupBy === 'effectiveFor'
                      ? 'border-blue-600 bg-blue-50 text-blue-700'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  Effective For
                </button>
                <button
                  onClick={() => updateParam('groupBy', 'paidAt')}
                  className={`flex-1 py-2 px-3 text-center rounded-md border ${
                    groupBy === 'paidAt'
                      ? 'border-blue-600 bg-blue-50 text-blue-700'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                >
                  Paid At
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {groupBy === 'effectiveFor' ? 'Shows what month it belongs to' : 'Shows when money moved'}
              </p>
            </div>

            {/* Status Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Show
              </label>
              <div className="flex gap-2">
                {['both', 'paid', 'planned'].map((s) => (
                  <button
                    key={s}
                    onClick={() => updateParam('status', s)}
                    className={`flex-1 py-2 px-3 text-center text-sm rounded-md border ${
                      status === s
                        ? 'border-blue-600 bg-blue-50 text-blue-700'
                        : 'border-gray-300 hover:border-gray-400'
                    }`}
                  >
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Summary */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <p className="text-sm text-gray-600">Total Planned</p>
              <p className="text-2xl font-bold text-blue-600">
                {totalPlanned.toFixed(2)} DKK
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Total Paid</p>
              <p className="text-2xl font-bold text-green-600">
                {totalPaid.toFixed(2)} DKK
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Difference</p>
              <p className={`text-2xl font-bold ${
                totalDelta > 0 ? 'text-red-600' : totalDelta < 0 ? 'text-green-600' : 'text-gray-900'
              }`}>
                {totalDelta > 0 ? '+' : ''}{totalDelta.toFixed(2)} DKK
              </p>
              {totalDelta !== 0 && (
                <p className="text-xs text-gray-500">
                  {totalDelta > 0 ? 'Over budget' : 'Under budget'}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Category Breakdown */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-xl font-semibold">Category Breakdown</h2>
          </div>

          {categories.length === 0 ? (
            <div className="p-8 text-center text-gray-600">
              No transactions for this period.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Budget</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Planned</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Paid</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">vs Budget</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {categories.map((cat) => {
                    const vsBudget = cat.budget ? cat.paid - cat.budget : null
                    return (
                      <tr key={cat.name} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {cat.name}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-600">
                          {cat.budget !== null ? cat.budget.toFixed(2) : (
                            <a href="/categories" className="text-blue-600 hover:text-blue-700 text-xs">
                              Set budget
                            </a>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-blue-600">
                          {cat.planned.toFixed(2)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-green-600">
                          {cat.paid.toFixed(2)}
                        </td>
                        <td className={`px-6 py-4 whitespace-nowrap text-sm text-right font-medium ${
                          vsBudget === null ? 'text-gray-400' :
                          vsBudget > 0 ? 'text-red-600' : vsBudget < 0 ? 'text-green-600' : 'text-gray-900'
                        }`}>
                          {vsBudget !== null ? (
                            <>{vsBudget > 0 ? '+' : ''}{vsBudget.toFixed(2)}</>
                          ) : '—'}
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
