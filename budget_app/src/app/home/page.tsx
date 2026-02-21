'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import LoadingSpinner from '@/components/LoadingSpinner'

type BudgetData = {
  categoryBreakdown: Array<{
    categoryId: string
    categoryName: string
    budget: number
    planned: number
    paid: number
  }>
  totals: {
    totalBudget: number
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
  const router = useRouter()
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
    checkOnboardingStatus()
  }, [])

  useEffect(() => {
    fetchBudgetData()
    fetchChartData()
  }, [selectedMonth, dateField])

  const checkOnboardingStatus = async () => {
    try {
      const res = await fetch('/api/onboarding/status')
      if (res.ok) {
        const data = await res.json()
        if (!data.onboardingCompleted) {
          router.push('/onboarding')
          return
        }
      }
    } catch (error) {
      console.error('Error checking onboarding status:', error)
    }
  }

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

  const formatCurrency = (amount: number | undefined | null) => {
    if (amount === undefined || amount === null) return '0.00'
    return amount.toFixed(2)
  }

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
      <div className="min-h-screen bg-zen-stone flex items-center justify-center">
        <LoadingSpinner size="lg" text="Loading your dashboard..." />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-zen-stone">
      <div className="max-w-7xl mx-auto px-4 py-6">
        <h1 className="text-2xl md:text-3xl font-bold mb-4 md:mb-6 text-zen-charcoal">Home</h1>

        {/* Controls - Compact */}
        <div className="bg-zen-stone-light rounded-lg p-3 md:p-4 mb-4 md:mb-6 shadow-md">
          <div className="flex flex-wrap gap-3 md:gap-4 items-center">
            {/* Month Picker */}
            <div className="flex items-center gap-2">
              <label className="text-xs md:text-sm font-medium text-zen-charcoal whitespace-nowrap">Month:</label>
              <input
                type="month"
                value={selectedMonth}
                onChange={(e) => setSelectedMonth(e.target.value)}
                className="px-2 md:px-3 py-1 md:py-2 text-sm border border-zen-stone-dark rounded-md focus:ring-2 focus:ring-zen-sage focus:border-zen-sage"
              />
            </div>

            {/* View By Toggle */}
            <div className="flex items-center gap-2">
              <label className="text-xs md:text-sm font-medium text-zen-charcoal whitespace-nowrap">View:</label>
              <div className="flex gap-1 bg-zen-stone-dark rounded-md p-0.5">
                <button
                  onClick={() => setDateField('effectiveFor')}
                  className={`px-2 md:px-3 py-1 rounded text-xs md:text-sm font-medium transition-colors ${
                    dateField === 'effectiveFor'
                      ? 'bg-zen-sage text-white'
                      : 'text-zen-charcoal hover:bg-zen-sand-light'
                  }`}
                >
                  Effective
                </button>
                <button
                  onClick={() => setDateField('paidAt')}
                  className={`px-2 md:px-3 py-1 rounded text-xs md:text-sm font-medium transition-colors ${
                    dateField === 'paidAt'
                      ? 'bg-zen-sage text-white'
                      : 'text-zen-charcoal hover:bg-zen-sand-light'
                  }`}
                >
                  Paid
                </button>
              </div>
            </div>

            {/* Show Checkboxes */}
            <div className="flex items-center gap-2 md:gap-3">
              <span className="text-xs md:text-sm font-medium text-zen-charcoal whitespace-nowrap">Show:</span>
              <label className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={showPaid}
                  onChange={(e) => setShowPaid(e.target.checked)}
                  className="rounded text-zen-sage focus:ring-zen-sage w-4 h-4"
                />
                <span className="text-xs md:text-sm">Paid</span>
              </label>
              <label className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={showPlanned}
                  onChange={(e) => setShowPlanned(e.target.checked)}
                  className="rounded text-zen-sage focus:ring-zen-sage w-4 h-4"
                />
                <span className="text-xs md:text-sm">Planned</span>
              </label>
            </div>
          </div>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 mb-6">
          {/* Mobile: Row 1, Col 1 | Desktop: Col 1 */}
          <div className="bg-zen-stone-light rounded-lg p-4 md:p-6 shadow-md">
            <h3 className="text-xs md:text-sm font-medium text-zen-charcoal-light uppercase mb-1 md:mb-2">Total Spent</h3>
            <p className="text-xl md:text-3xl font-bold text-zen-charcoal">{formatCurrency(budgetData?.totals?.totalPaid ?? 0)}</p>
            <p className="text-xs md:text-sm text-zen-charcoal-light mt-1">{formatMonth(selectedMonth)}</p>
          </div>

          {/* Mobile: Row 1, Col 2 (order-1) | Desktop: Col 4 */}
          <div className="bg-gradient-to-br from-zen-sage-light to-zen-sage rounded-lg p-4 md:p-6 shadow-md order-1 lg:order-4">
            <h3 className="text-xs md:text-sm font-medium text-white uppercase mb-1 md:mb-2">Remaining</h3>
            <p className={`text-xl md:text-3xl font-bold ${
              ((budgetData?.totals?.totalBudget ?? 0) - (budgetData?.totals?.totalPaid ?? 0) - (budgetData?.totals?.totalPlanned ?? 0)) >= 0 
                ? 'text-white' 
                : 'text-red-200'
            }`}>
              {formatCurrency((budgetData?.totals?.totalBudget ?? 0) - (budgetData?.totals?.totalPaid ?? 0) - (budgetData?.totals?.totalPlanned ?? 0))}
            </p>
            <p className="text-xs md:text-sm text-zen-stone-light mt-1">
              Budget - Spent - Planned
            </p>
          </div>

          {/* Mobile: Row 2, Col 1 (order-2) | Desktop: Col 2 */}
          <div className="bg-zen-stone-light rounded-lg p-4 md:p-6 shadow-md order-2">
            <h3 className="text-xs md:text-sm font-medium text-zen-charcoal-light uppercase mb-1 md:mb-2">Total Planned</h3>
            <p className="text-xl md:text-3xl font-bold text-zen-charcoal">{formatCurrency(budgetData?.totals?.totalPlanned ?? 0)}</p>
            <p className="text-xs md:text-sm text-zen-charcoal-light mt-1">{formatMonth(selectedMonth)}</p>
          </div>

          {/* Mobile: Row 2, Col 2 (order-3) | Desktop: Col 3 */}
          <div className="bg-zen-stone-light rounded-lg p-4 md:p-6 shadow-md order-3">
            <h3 className="text-xs md:text-sm font-medium text-zen-charcoal-light uppercase mb-1 md:mb-2">Total Budgeted</h3>
            <p className="text-xl md:text-3xl font-bold text-zen-charcoal">{formatCurrency(budgetData?.totals?.totalBudget ?? 0)}</p>
            <p className="text-xs md:text-sm text-zen-charcoal-light mt-1">{formatMonth(selectedMonth)}</p>
          </div>
        </div>

        {/* Budget Table */}
        <div className="bg-zen-stone-light rounded-lg shadow-md mb-6 overflow-hidden">
          <div className="px-6 py-4 border-b border-zen-stone-dark">
            <h2 className="text-xl font-bold text-zen-charcoal">Budget Breakdown</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-zen-stone">
                <tr>
                  <th className="sticky left-0 z-10 bg-zen-stone px-6 py-3 text-left text-xs font-medium text-zen-charcoal uppercase">Category</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-zen-charcoal uppercase">Budget</th>
                  {showPlanned && <th className="px-6 py-3 text-right text-xs font-medium text-zen-charcoal uppercase">Planned</th>}
                  {showPaid && <th className="px-6 py-3 text-right text-xs font-medium text-zen-charcoal uppercase">Paid</th>}
                  <th className="px-6 py-3 text-right text-xs font-medium text-zen-charcoal uppercase">Total</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-zen-charcoal uppercase">vs Budget</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zen-stone-dark">
                {filteredCategories.map((cat) => {
                  const total = cat.planned + cat.paid
                  const vsBudget = total - cat.budget
                  return (
                    <tr key={cat.categoryId} className="hover:bg-zen-stone transition-colors">
                      <td className="sticky left-0 z-10 bg-zen-stone-light px-6 py-4 text-sm font-medium text-zen-charcoal">
                        {cat.categoryName}
                      </td>
                      <td className="px-6 py-4 text-sm text-right text-zen-charcoal-light">{formatCurrency(cat.budget)}</td>
                      {showPlanned && <td className="px-6 py-4 text-sm text-right text-zen-sand-dark font-medium">{formatCurrency(cat.planned)}</td>}
                      {showPaid && <td className="px-6 py-4 text-sm text-right text-zen-sage-dark font-medium">{formatCurrency(cat.paid)}</td>}
                      <td className="px-6 py-4 text-sm text-right font-semibold text-zen-charcoal">{formatCurrency(total)}</td>
                      <td className={`px-6 py-4 text-sm text-right font-bold ${vsBudget > 0 ? 'text-red-600' : 'text-green-600'}`}>
                        {vsBudget > 0 ? '+' : ''}{formatCurrency(vsBudget)}
                      </td>
                    </tr>
                  )
                })}
                <tr className="bg-zen-stone-dark font-bold">
                  <td className="sticky left-0 z-10 bg-zen-stone-dark px-6 py-4 text-sm text-zen-charcoal">TOTAL</td>
                  <td className="px-6 py-4 text-sm text-right text-zen-charcoal">{formatCurrency(budgetData?.totals?.totalBudget ?? 0)}</td>
                  {showPlanned && <td className="px-6 py-4 text-sm text-right text-zen-charcoal">{formatCurrency(budgetData?.totals?.totalPlanned ?? 0)}</td>}
                  {showPaid && <td className="px-6 py-4 text-sm text-right text-zen-charcoal">{formatCurrency(budgetData?.totals?.totalPaid ?? 0)}</td>}
                  <td className="px-6 py-4 text-sm text-right text-zen-charcoal">{formatCurrency((budgetData?.totals?.totalPlanned ?? 0) + (budgetData?.totals?.totalPaid ?? 0))}</td>
                  <td className={`px-6 py-4 text-sm text-right ${
                    ((budgetData?.totals?.totalPlanned ?? 0) + (budgetData?.totals?.totalPaid ?? 0) - (budgetData?.totals?.totalBudget ?? 0)) > 0 ? 'text-red-600' : 'text-green-600'
                  }`}>
                    {((budgetData?.totals?.totalPlanned ?? 0) + (budgetData?.totals?.totalPaid ?? 0) - (budgetData?.totals?.totalBudget ?? 0)) > 0 ? '+' : ''}
                    {formatCurrency((budgetData?.totals?.totalPlanned ?? 0) + (budgetData?.totals?.totalPaid ?? 0) - (budgetData?.totals?.totalBudget ?? 0))}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Chart */}
        {chartData && chartData.monthlyTrend && chartData.monthlyTrend.length > 0 && (
          <div className="bg-zen-stone-light rounded-lg shadow-md p-6">
            <h2 className="text-xl font-bold mb-4 text-zen-charcoal">Spending Trend</h2>
            <p className="text-sm text-zen-charcoal-light mb-4">Last 6 Months</p>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData.monthlyTrend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E8E8E3" />
                <XAxis dataKey="month" stroke="#5A5A5A" style={{ fontSize: '12px' }} />
                <YAxis stroke="#5A5A5A" style={{ fontSize: '12px' }} />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#FEFEFE', 
                    border: '1px solid #E8E8E3',
                    borderRadius: '0.5rem',
                    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'
                  }}
                />
                <Legend wrapperStyle={{ paddingTop: '20px' }} />
                <Line type="monotone" dataKey="paid" stroke="#6B8E6B" name="Paid" strokeWidth={2} />
                <Line type="monotone" dataKey="planned" stroke="#D4C5B0" name="Planned" strokeWidth={2} strokeDasharray="5 5" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}
