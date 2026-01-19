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

    // Get query parameters
    const { searchParams } = new URL(request.url)
    const timeRange = parseInt(searchParams.get('timeRange') || '6') // months
    const groupBy = searchParams.get('groupBy') || 'total' // total, account, category

    const now = new Date()
    const startDate = new Date(now.getFullYear(), now.getMonth() - (timeRange - 1), 1)
    
    // Get all transactions from the time range
    const transactions = await prisma.transaction.findMany({
      where: {
        profileId: profile.id,
        OR: [
          { effectiveFor: { gte: startDate } },
          { 
            AND: [
              { effectiveFor: null },
              { paidAt: { gte: startDate } }
            ]
          }
        ],
      },
      include: {
        lines: {
          include: {
            category: true,
            account: true,
          },
        },
      },
    })

    let monthlyTrend: any[] = []

    if (groupBy === 'total') {
      // Total: Show income, paid expenses, planned expenses
      for (let i = timeRange - 1; i >= 0; i--) {
        const monthDate = new Date(now.getFullYear(), now.getMonth() - i, 1)
        const monthStart = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1)
        const monthEnd = new Date(monthDate.getFullYear(), monthDate.getMonth() + 1, 0, 23, 59, 59, 999)
        
        const monthName = monthDate.toLocaleString('default', { month: 'short', year: 'numeric' })
        
        let planned = 0
        let paid = 0
        let income = 0
        
        transactions
          .filter(tx => {
            const date = tx.effectiveFor || tx.paidAt
            return date && date >= monthStart && date <= monthEnd
          })
          .forEach(tx => {
            const total = Math.abs(tx.lines.reduce((sum, line) => sum + line.amount, 0))
            
            if (tx.kind === 'INCOME') {
              income += total
            } else if (tx.kind === 'EXPENSE') {
              if (tx.status === 'PLANNED') {
                planned += total
              } else {
                paid += total
              }
            }
          })
        
        monthlyTrend.push({
          month: monthName,
          planned,
          paid,
          income,
        })
      }
    } else if (groupBy === 'account') {
      // By Account: Show paid expenses per account
      const accounts = await prisma.account.findMany({
        where: { profileId: profile.id },
      })

      for (let i = timeRange - 1; i >= 0; i--) {
        const monthDate = new Date(now.getFullYear(), now.getMonth() - i, 1)
        const monthStart = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1)
        const monthEnd = new Date(monthDate.getFullYear(), monthDate.getMonth() + 1, 0, 23, 59, 59, 999)
        
        const monthName = monthDate.toLocaleString('default', { month: 'short', year: 'numeric' })
        
        const monthData: any = { month: monthName }
        
        accounts.forEach(account => {
          const accountExpenses = transactions
            .filter(tx => {
              const date = tx.effectiveFor || tx.paidAt
              return tx.kind === 'EXPENSE' && 
                     tx.status === 'PAID' &&
                     date && date >= monthStart && date <= monthEnd &&
                     tx.lines.some(line => line.accountId === account.id)
            })
            .reduce((sum, tx) => {
              const accountLines = tx.lines.filter(line => line.accountId === account.id)
              return sum + Math.abs(accountLines.reduce((s, line) => s + line.amount, 0))
            }, 0)
          
          monthData[account.name] = accountExpenses
        })
        
        monthlyTrend.push(monthData)
      }
    } else if (groupBy === 'category') {
      // By Category: Show paid expenses per category
      const categories = await prisma.category.findMany({
        where: { profileId: profile.id },
      })

      for (let i = timeRange - 1; i >= 0; i--) {
        const monthDate = new Date(now.getFullYear(), now.getMonth() - i, 1)
        const monthStart = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1)
        const monthEnd = new Date(monthDate.getFullYear(), monthDate.getMonth() + 1, 0, 23, 59, 59, 999)
        
        const monthName = monthDate.toLocaleString('default', { month: 'short', year: 'numeric' })
        
        const monthData: any = { month: monthName }
        
        categories.forEach(category => {
          const categoryExpenses = transactions
            .filter(tx => {
              const date = tx.effectiveFor || tx.paidAt
              return tx.kind === 'EXPENSE' && 
                     tx.status === 'PAID' &&
                     date && date >= monthStart && date <= monthEnd
            })
            .reduce((sum, tx) => {
              const categoryLines = tx.lines.filter(line => line.categoryId === category.id)
              return sum + Math.abs(categoryLines.reduce((s, line) => s + line.amount, 0))
            }, 0)
          
          monthData[category.name] = categoryExpenses
        })
        
        monthlyTrend.push(monthData)
      }
    }

    return NextResponse.json({
      monthlyTrend,
      groupBy,
    })
  } catch (error) {
    console.error('Error fetching chart data:', error)
    return NextResponse.json(
      { error: 'Failed to fetch chart data' },
      { status: 500 }
    )
  }
}
