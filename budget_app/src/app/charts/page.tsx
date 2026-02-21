'use client'

import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import Link from 'next/link'

type ChartData = {
  monthlyTrend: any[]
  groupBy: string
}

const COLORS = [
  '#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', 
  '#06b6d4', '#f97316', '#6366f1', '#84cc16', '#ef4444',
  '#0891b2', '#c026d3', '#dc2626', '#059669', '#7c3aed'
]

export default function ChartsPage() {
  const [data, setData] = useState<ChartData | null>(null)
  const [loading, setLoading] = useState(true)
  const [timeRange, setTimeRange] = useState('6') // months
  const [groupBy, setGroupBy] = useState('total') // total, account, category
  const [showData, setShowData] = useState('both') // income, expenses, both

  useEffect(() => {
    fetchChartData()
  }, [timeRange, groupBy])

  const fetchChartData = async () => {
    setLoading(true)
    try {
      const response = await fetch(`/api/charts?timeRange=${timeRange}&groupBy=${groupBy}`)
      const chartData = await response.json()
      setData(chartData)
    } catch (error) {
      console.error('Failed to fetch chart data', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">Loading charts...</p>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-600">Failed to load chart data</p>
      </div>
    )
  }

  // Get all the keys (series) from the data, excluding 'month'
  let dataKeys = (data.monthlyTrend?.length ?? 0) > 0 
    ? Object.keys(data.monthlyTrend[0]).filter(key => key !== 'month')
    : []

  // Filter based on showData selection (only for 'total' groupBy)
  if (groupBy === 'total') {
    if (showData === 'income') {
      dataKeys = dataKeys.filter(key => key === 'income')
    } else if (showData === 'expenses') {
      dataKeys = dataKeys.filter(key => key === 'paid' || key === 'planned')
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto p-6">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900">Spending Trend</h1>
          <p className="text-gray-600 mt-1">Track your income and expenses over time</p>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Time Range */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Time Range
              </label>
              <select
                value={timeRange}
                onChange={(e) => setTimeRange(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
              >
                <option value="3">Last 3 months</option>
                <option value="6">Last 6 months</option>
                <option value="12">Last 12 months</option>
                <option value="24">Last 2 years</option>
              </select>
            </div>

            {/* Group By */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Group By
              </label>
              <select
                value={groupBy}
                onChange={(e) => setGroupBy(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
              >
                <option value="total">Total (Income & Expenses)</option>
                <option value="account">By Account</option>
                <option value="category">By Category</option>
              </select>
              <p className="text-xs text-gray-500 mt-1">
                {groupBy === 'total' && 'Shows overall income and expenses'}
                {groupBy === 'account' && 'Break down expenses by account'}
                {groupBy === 'category' && 'Break down expenses by spending category'}
              </p>
            </div>

            {/* Show Data */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Show Data
              </label>
              <select
                value={showData}
                onChange={(e) => setShowData(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500"
              >
                <option value="both">Income & Expenses</option>
                <option value="income">Income Only</option>
                <option value="expenses">Expenses Only</option>
              </select>
              <p className="text-xs text-gray-500 mt-1">
                {showData === 'both' && 'Shows all financial data'}
                {showData === 'income' && 'Shows only income'}
                {showData === 'expenses' && 'Shows only expenses (paid & planned)'}
              </p>
            </div>
          </div>
        </div>

        {/* Spending Trend Chart */}
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">
            {groupBy === 'total' && `Income vs Expenses (Last ${timeRange} months)`}
            {groupBy === 'account' && `Expenses by Account (Last ${timeRange} months)`}
            {groupBy === 'category' && `Expenses by Category (Last ${timeRange} months)`}
          </h2>
          {(data.monthlyTrend?.length ?? 0) > 0 ? (
            <ResponsiveContainer width="100%" height={400}>
              <LineChart data={data.monthlyTrend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip formatter={(value: number) => `${value.toFixed(0)} DKK`} />
                <Legend />
                {dataKeys.map((key, index) => (
                  <Line 
                    key={key}
                    type="monotone" 
                    dataKey={key} 
                    stroke={COLORS[index % COLORS.length]}
                    strokeWidth={3}
                    name={key.charAt(0).toUpperCase() + key.slice(1)}
                    dot={{ r: 4 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="text-center py-12">
              <p className="text-gray-500 text-lg mb-4">No data available yet</p>
              <Link 
                href="/transactions/add"
                className="inline-block px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
              >
                Add Your First Transaction
              </Link>
            </div>
          )}

          {/* Summary Stats */}
          {(data.monthlyTrend?.length ?? 0) > 0 && groupBy === 'total' && (
            <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-purple-50 rounded-lg p-4 text-center">
                <p className="text-xs text-purple-600 font-medium mb-1">Avg Monthly Income</p>
                <p className="text-xl font-bold text-purple-700">
                  {(data.monthlyTrend.reduce((sum: number, m: any) => sum + (m.income || 0), 0) / data.monthlyTrend.length).toFixed(0)} DKK
                </p>
              </div>
              <div className="bg-red-50 rounded-lg p-4 text-center">
                <p className="text-xs text-red-600 font-medium mb-1">Avg Monthly Expenses</p>
                <p className="text-xl font-bold text-red-700">
                  {(data.monthlyTrend.reduce((sum: number, m: any) => sum + Math.abs(m.paid || 0), 0) / data.monthlyTrend.length).toFixed(0)} DKK
                </p>
              </div>
              <div className="bg-blue-50 rounded-lg p-4 text-center">
                <p className="text-xs text-blue-600 font-medium mb-1">Avg Planned</p>
                <p className="text-xl font-bold text-blue-700">
                  {(data.monthlyTrend.reduce((sum: number, m: any) => sum + Math.abs(m.planned || 0), 0) / data.monthlyTrend.length).toFixed(0)} DKK
                </p>
              </div>
              <div className="bg-green-50 rounded-lg p-4 text-center">
                <p className="text-xs text-green-600 font-medium mb-1">Avg Net</p>
                <p className="text-xl font-bold text-green-700">
                  {(data.monthlyTrend.reduce((sum: number, m: any) => sum + (m.income || 0) + (m.paid || 0), 0) / data.monthlyTrend.length).toFixed(0)} DKK
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Back to Home */}
        <div className="mt-6 text-center">
          <Link 
            href="/home"
            className="inline-block px-6 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition"
          >
            ← Back to Home
          </Link>
        </div>
      </div>
    </div>
  )
}
