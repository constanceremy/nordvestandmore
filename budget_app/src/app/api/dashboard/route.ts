import { NextRequest, NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'
import { createClient } from '@/lib/supabase/server'

export async function GET(request: NextRequest) {
  try {
    const supabase = await createClient()
    const {
      data: { user },
    } = await supabase.auth.getUser()

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    // Get the profile
    const profile = await prisma.profile.findUnique({
      where: { userId: user.id },
    })

    if (!profile) {
      return NextResponse.json({ error: 'Profile not found' }, { status: 404 })
    }

    const now = new Date()
    const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1)
    const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59, 999)
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const endOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999)

    // Get all accounts with their current balances
    const accounts = await prisma.account.findMany({
      where: { profileId: profile.id },
      include: {
        transactionLines: {
          where: {
            transaction: { status: 'PAID' },
          },
          include: {
            transaction: true,
          },
        },
      },
    })

    const accountsWithBalances = accounts.map((account) => {
      const currentBalance = account.openingBalance + 
        account.transactionLines.reduce((sum, line) => sum + line.amount, 0)
      return {
        id: account.id,
        name: account.name,
        currentBalance,
        currency: account.currency,
      }
    })

    const totalNetWorth = accountsWithBalances.reduce((sum, acc) => sum + acc.currentBalance, 0)

    // Get this month's transactions
    const thisMonthTransactions = await prisma.transaction.findMany({
      where: {
        profileId: profile.id,
        OR: [
          { effectiveFor: { gte: startOfMonth, lte: endOfMonth } },
          { 
            AND: [
              { effectiveFor: null },
              { paidAt: { gte: startOfMonth, lte: endOfMonth } }
            ]
          }
        ],
      },
      include: {
        lines: {
          include: {
            category: true,
          },
        },
      },
    })

    // Calculate month spending vs budget
    const categorySpending: { [key: string]: { paid: number; planned: number; budget: number | null; name: string } } = {}
    
    for (const tx of thisMonthTransactions) {
      if (tx.kind !== 'EXPENSE') continue
      
      for (const line of tx.lines) {
        if (!line.category) continue
        
        if (!categorySpending[line.category.id]) {
          categorySpending[line.category.id] = {
            paid: 0,
            planned: 0,
            budget: line.category.monthlyBudgetTarget,
            name: line.category.name,
          }
        }
        
        if (tx.status === 'PAID') {
          categorySpending[line.category.id].paid += Math.abs(line.amount)
        } else {
          categorySpending[line.category.id].planned += Math.abs(line.amount)
        }
      }
    }

    const topSpendingCategories = Object.values(categorySpending)
      .sort((a, b) => b.paid - a.paid)
      .slice(0, 3)

    const totalSpentThisMonth = Object.values(categorySpending).reduce((sum, cat) => sum + cat.paid, 0)
    const totalBudgetThisMonth = Object.values(categorySpending)
      .filter(cat => cat.budget !== null)
      .reduce((sum, cat) => sum + (cat.budget || 0), 0)

    // Get today's planned transactions
    const todayPlanned = await prisma.transaction.findMany({
      where: {
        profileId: profile.id,
        status: 'PLANNED',
        OR: [
          { effectiveFor: { gte: startOfToday, lte: endOfToday } },
          { 
            AND: [
              { effectiveFor: null },
              { paidAt: { gte: startOfToday, lte: endOfToday } }
            ]
          }
        ],
      },
      include: {
        lines: true,
      },
    })

    const totalPlannedToday = todayPlanned.reduce((sum, tx) => {
      if (tx.kind === 'TRANSFER') return sum
      return sum + Math.abs(tx.lines.reduce((s, line) => s + line.amount, 0))
    }, 0)

    // Get upcoming planned expenses (next 7 days)
    const next7Days = new Date(now)
    next7Days.setDate(next7Days.getDate() + 7)
    
    const upcomingPlanned = await prisma.transaction.findMany({
      where: {
        profileId: profile.id,
        status: 'PLANNED',
        OR: [
          { effectiveFor: { gte: now, lte: next7Days } },
          { 
            AND: [
              { effectiveFor: null },
              { paidAt: { gte: now, lte: next7Days } }
            ]
          }
        ],
      },
      include: {
        lines: true,
      },
      orderBy: [
        { effectiveFor: 'asc' },
        { paidAt: 'asc' },
      ],
      take: 5,
    })

    const upcomingExpenses = upcomingPlanned.map(tx => ({
      id: tx.id,
      description: tx.description,
      amount: Math.abs(tx.lines.reduce((s, line) => s + line.amount, 0)),
      date: (tx.effectiveFor || tx.paidAt)?.toISOString().split('T')[0] || '',
      kind: tx.kind,
    }))

    // Calculate days remaining in month
    const daysInMonth = endOfMonth.getDate()
    const daysRemaining = daysInMonth - now.getDate() + 1

    // Calculate forecast for end of month directly
    const forecastTransactions = await prisma.transaction.findMany({
      where: {
        profileId: profile.id,
        kind: { in: ['INCOME', 'EXPENSE'] },
        OR: [
          { effectiveFor: { lte: endOfMonth } },
          { 
            AND: [
              { effectiveFor: null },
              { paidAt: { lte: endOfMonth } }
            ]
          }
        ],
      },
      include: {
        lines: true,
      },
    })

    const forecastIncome = forecastTransactions
      .filter((tx) => tx.kind === 'INCOME')
      .reduce((sum, tx) => {
        const lineTotal = tx.lines.reduce((s, line) => s + line.amount, 0)
        return sum + lineTotal
      }, 0)

    const forecastExpenses = forecastTransactions
      .filter((tx) => tx.kind === 'EXPENSE')
      .reduce((sum, tx) => {
        const lineTotal = tx.lines.reduce((s, line) => s + line.amount, 0)
        return sum + lineTotal
      }, 0)

    const monthEndForecast = {
      totalIncome: forecastIncome,
      totalExpenses: forecastExpenses,
      netResult: forecastIncome + forecastExpenses, // expenses are negative
    }

    return NextResponse.json({
      netWorth: totalNetWorth,
      accounts: accountsWithBalances,
      thisMonth: {
        spent: totalSpentThisMonth,
        budget: totalBudgetThisMonth,
        daysRemaining,
        daysInMonth,
      },
      todayPlanned: totalPlannedToday,
      topSpending: topSpendingCategories,
      upcomingExpenses,
      monthEndForecast,
    })
  } catch (error) {
    console.error('Error fetching dashboard data:', error)
    return NextResponse.json(
      { error: 'Failed to fetch dashboard data' },
      { status: 500 }
    )
  }
}
