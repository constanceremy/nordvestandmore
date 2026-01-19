'use client'

import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

type BudgetData = {
  categoryBreakdown: Array<{
    categoryId: string
    categoryName: string
    target: number
    planned: number
    paid: number
  }>
  totals: {
    totalTarget: number
    totalPlanned: number
    totalPaid: number
  }
}

type ChartData = {
  monthlyTrend: Array<{
    month: string
    [key: string]: string | number
  }>
}

export default function HomePage() {
  const [budgetData, setBudgetData] = useState<BudgetData | null>(null)
  const [chartData, setChartData] = useState<ChartData | null>(null)
  const [loading, setLoading] = useState(true)

  // Filters
  const [selectedMonth, setSelectedMonth] = useState(() => {
    const now = new Date()
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  })
  const [dateField, setDateField] = useState<'paidAt' | 'effectiveFor'>('effectiveFor')
  const [showPaid, setShowPaid] = useState(true)
  const [showPlanned, setShowPlanned] = useState(true)

  // Derived metrics
  const [todayMetrics, setTodayMetrics] = useState({
    plannedUntilToday: 0,
    actualUntilToday: 0
  })
  const [forecastEndOfMonth, setForecastEndOfMonth] = useState(0)

  useEffect(() => {
    fetchBudgetData()
    fetchChartData()
  }, [selectedMonth, dateField])

  const fetchBudgetData = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({
        month: selectedMonth,
        dateField
      })
      const response = await fetch(`/api/overview?${params}`)
      if (response.ok) {
        const data = await response.json()
        setBudgetData(data)
        calculateTodayMetrics(data)
        calculateForecast(data)
      }
    } catch (error) {
      console.error('Failed to fetch budget data', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchChartData = async () => {
    try {
      const params = new URLSearchParams({
        timeRange: '6',
        groupBy: 'total'
      })
      const response = await fetch(`/api/charts?${params}`)
      if (response.ok) {
        setChartData(await response.json())
      }
    } catch (error) {
      console.error('Failed to fetch chart data', error)
    }
  }

  const calculateTodayMetrics = (data: BudgetData) => {
    if (!data || !data.totals) {
      setTodayMetrics({ plannedUntilToday: 0, actualUntilToday: 0 })
      return
    }

    const today = new Date()
    const [year, month] = selectedMonth.split('-').map(Number)
    const selectedDate = new Date(year, month - 1, 1)
    
    // Only calculate if we're looking at the current month
    if (selectedDate.getMonth() === today.getMonth() && selectedDate.getFullYear() === today.getFullYear()) {
      const dayOfMonth = today.getDate()
      const daysInMonth = new Date(year, month, 0).getDate()
      const progressRatio = dayOfMonth / daysInMonth

      const plannedUntilToday = (data.totals.totalPlanned ?? 0) * progressRatio
      const actualUntilToday = data.totals.totalPaid ?? 0

      setTodayMetrics({ plannedUntilToday, actualUntilToday })
    } else {
      setTodayMetrics({ plannedUntilToday: 0, actualUntilToday: 0 })
    }
  }

  const calculateForecast = (data: BudgetData) => {
    if (!data || !data.totals) {
      setForecastEndOfMonth(0)
      return
    }
    // Simple forecast: planned + paid
    const forecast = (data.totals.totalPlanned ?? 0) + (data.totals.totalPaid ?? 0)
    setForecastEndOfMonth(forecast)
  }

  const filteredCategories = budgetData?.categoryBreakdown?.filter(cat => {
    if (!showPaid && !showPlanned) return false
    if (showPaid && showPlanned) return true
    if (showPaid) return cat.paid > 0
    if (showPlanned) return cat.planned > 0
    return true
  }) ?? []

  const formatCurrency = (amount: number) => amount.toFixed(2)

  const formatMonth = (monthStr: string) => {
    const [year, month] = monthStr.split('-')
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    return `${months[parseInt(month) - 1]} ${year}`
  }

  const isCurrentMonth = () => {
    const now = new Date()
    const current = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
    return selectedMonth === current
  }

  if (loading && !budgetData) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">Loading...</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-6">
        <h1 className="text-3xl font-bold mb-6 text-gray-900">Overview</h1>

        {/* Controls */}
        <div className="bg-white rounded-lg p-6 mb-6 shadow">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Month</label>
              <input
                type="month"
                value={selectedMonth}
                onChange={(e) => setSelectedMonth(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">View By</label>
              <div className="flex gap-2">
                <button
                  onClick={() => setDateField('effectiveFor')}
                  className={`flex-1 px-3 py-2 rounded-md text-sm font-medium ${
                    dateField === 'effectiveFor'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  Effective For
                </button>
                <button
                  onClick={() => setDateField('paidAt')}
                  className={`flex-1 px-3 py-2 rounded-md text-sm font-medium ${
                    dateField === 'paidAt'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  Paid At
                </button>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Show</label>
              <div className="flex gap-4 items-center">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={showPaid}
                    onChange={(e) => setShowPaid(e.target.checked)}
                    className="rounded"
                  />
                  <span className="text-sm">Paid</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={showPlanned}
                    onChange={(e) => setShowPlanned(e.target.checked)}
                    className="rounded"
                  />
                  <span className="text-sm">Planned</span>
                </label>
              </div>
            </div>
          </div>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg p-6 shadow">
            <h3 className="text-sm font-medium text-gray-500 uppercase mb-2">Total Spent</h3>
            <p className="text-3xl font-bold text-gray-900">{formatCurrency(budgetData?.totals?.totalPaid ?? 0)}</p>
            <p className="text-sm text-gray-500 mt-1">{formatMonth(selectedMonth)}</p>
          </div>

          <div className="bg-white rounded-lg p-6 shadow">
            <h3 className="text-sm font-medium text-gray-500 uppercase mb-2">Total Planned</h3>
            <p className="text-3xl font-bold text-gray-900">{formatCurrency(budgetData?.totals?.totalPlanned ?? 0)}</p>
            <p className="text-sm text-gray-500 mt-1">{formatMonth(selectedMonth)}</p>
          </div>

          {isCurrentMonth() && (
            <div className="bg-white rounded-lg p-6 shadow border-2 border-orange-200">
              <h3 className="text-sm font-medium text-orange-600 uppercase mb-2">As of Today</h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">Planned</span>
                  <span className="text-sm font-semibold">{formatCurrency(todayMetrics.plannedUntilToday)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">Actual</span>
                  <span className={`text-sm font-semibold ${
                    todayMetrics.actualUntilToday > todayMetrics.plannedUntilToday ? 'text-red-600' : 'text-green-600'
                  }`}>
                    {formatCurrency(todayMetrics.actualUntilToday)}
                  </span>
                </div>
                <div className="pt-2 border-t border-gray-200 flex justify-between">
                  <span className="text-sm font-medium">Difference</span>
                  <span className={`text-lg font-bold ${
                    todayMetrics.actualUntilToday > todayMetrics.plannedUntilToday ? 'text-red-600' : 'text-green-600'
                  }`}>
                    {todayMetrics.actualUntilToday > todayMetrics.plannedUntilToday ? '+' : ''}
                    {formatCurrency(todayMetrics.actualUntilToday - todayMetrics.plannedUntilToday)}
                  </span>
                </div>
              </div>
            </div>
          )}

          <div className="bg-purple-100 rounded-lg p-6 shadow">
            <h3 className="text-sm font-medium text-purple-700 uppercase mb-2">Month-End Forecast</h3>
            <p className="text-3xl font-bold text-purple-900">{formatCurrency(forecastEndOfMonth)}</p>
            <p className="text-sm text-purple-700 mt-1">Expected total</p>
          </div>
        </div>

        {/* Budget Table */}
        <div className="bg-white rounded-lg shadow mb-6 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-xl font-bold">Budget Breakdown</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Target</th>
                  {showPlanned && <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Planned</th>}
                  {showPaid && <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Paid</th>}
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Total</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">vs Target</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredCategories.map((cat) => {
                  const total = cat.planned + cat.paid
                  const vsTarget = total - cat.target
                  return (
                    <tr key={cat.categoryId} className="hover:bg-gray-50">
                      <td className="px-6 py-4 text-sm font-medium text-gray-900">{cat.categoryName}</td>
                      <td className="px-6 py-4 text-sm text-right text-gray-600">{formatCurrency(cat.target)}</td>
                      {showPlanned && <td className="px-6 py-4 text-sm text-right text-orange-600 font-medium">{formatCurrency(cat.planned)}</td>}
                      {showPaid && <td className="px-6 py-4 text-sm text-right text-blue-600 font-medium">{formatCurrency(cat.paid)}</td>}
                      <td className="px-6 py-4 text-sm text-right font-semibold">{formatCurrency(total)}</td>
                      <td className={`px-6 py-4 text-sm text-right font-bold ${vsTarget > 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {vsTarget > 0 ? '+' : ''}{formatCurrency(vsTarget)}
                      </td>
                    </tr>
                  )
                })}
                <tr className="bg-gray-100 font-bold">
                  <td className="px-6 py-4 text-sm">TOTAL</td>
                  <td className="px-6 py-4 text-sm text-right">{formatCurrency(budgetData?.totals?.totalTarget ?? 0)}</td>
                  {showPlanned && <td className="px-6 py-4 text-sm text-right">{formatCurrency(budgetData?.totals?.totalPlanned ?? 0)}</td>}
                  {showPaid && <td className="px-6 py-4 text-sm text-right">{formatCurrency(budgetData?.totals?.totalPaid ?? 0)}</td>}
                  <td className="px-6 py-4 text-sm text-right">{formatCurrency((budgetData?.totals?.totalPlanned ?? 0) + (budgetData?.totals?.totalPaid ?? 0))}</td>
                  <td className={`px-6 py-4 text-sm text-right ${
                    ((budgetData?.totals?.totalPlanned ?? 0) + (budgetData?.totals?.totalPaid ?? 0) - (budgetData?.totals?.totalTarget ?? 0)) > 0 ? 'text-red-600' : 'text-green-600'
                  }`}>
                    {((budgetData?.totals?.totalPlanned ?? 0) + (budgetData?.totals?.totalPaid ?? 0) - (budgetData?.totals?.totalTarget ?? 0)) > 0 ? '+' : ''}
                    {formatCurrency((budgetData?.totals?.totalPlanned ?? 0) + (budgetData?.totals?.totalPaid ?? 0) - (budgetData?.totals?.totalTarget ?? 0))}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Chart */}
        {chartData && chartData.monthlyTrend && chartData.monthlyTrend.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-bold mb-4">Spending Trend</h2>
            <p className="text-sm text-gray-500 mb-4">Last 6 Months</p>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData.monthlyTrend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="month" stroke="#6b7280" style={{ fontSize: '12px' }} />
                <YAxis stroke="#6b7280" style={{ fontSize: '12px' }} />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#ffffff', 
                    border: '1px solid #e5e7eb',
                    borderRadius: '0.5rem',
                    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'
                  }}
                />
                <Legend wrapperStyle={{ paddingTop: '20px' }} />
                <Line type="monotone" dataKey="paid" stroke="#2563eb" name="Paid" strokeWidth={2} />
                <Line type="monotone" dataKey="planned" stroke="#f97316" name="Planned" strokeWidth={2} strokeDasharray="5 5" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}
