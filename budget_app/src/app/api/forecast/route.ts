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

    // Get forecast date from query params
    const { searchParams } = new URL(request.url)
    const forecastDateStr = searchParams.get('date')
    
    if (!forecastDateStr) {
      return NextResponse.json({ error: 'Date parameter required' }, { status: 400 })
    }

    const forecastDate = new Date(forecastDateStr)
    forecastDate.setHours(23, 59, 59, 999) // End of day

    // Get all accounts
    const accounts = await prisma.account.findMany({
      where: { profileId: profile.id },
      include: {
        transactionLines: {
          include: {
            transaction: true,
          },
        },
      },
    })

    // Calculate current and expected balances for each account
    const accountForecasts = accounts.map((account) => {
      // Current balance = opening balance + all PAID transactions
      const paidTransactions = account.transactionLines.filter(
        (line) => line.transaction.status === 'PAID'
      )
      const currentBalance = account.openingBalance + 
        paidTransactions.reduce((sum, line) => sum + line.amount, 0)

      // Expected balance = opening balance + all PAID + PLANNED up to forecast date
      const relevantTransactions = account.transactionLines.filter((line) => {
        const txDate = line.transaction.effectiveFor || line.transaction.paidAt
        return txDate && new Date(txDate) <= forecastDate
      })
      const expectedBalance = account.openingBalance +
        relevantTransactions.reduce((sum, line) => sum + line.amount, 0)

      return {
        id: account.id,
        name: account.name,
        currentBalance,
        expectedBalance,
        change: expectedBalance - currentBalance,
      }
    })

    // Calculate total income and expenses (planned + paid) up to forecast date
    const allTransactions = await prisma.transaction.findMany({
      where: {
        profileId: profile.id,
        kind: { in: ['INCOME', 'EXPENSE'] },
        OR: [
          { effectiveFor: { lte: forecastDate } },
          { 
            AND: [
              { effectiveFor: null },
              { paidAt: { lte: forecastDate } }
            ]
          }
        ],
      },
      include: {
        lines: true,
      },
    })

    const totalIncome = allTransactions
      .filter((tx) => tx.kind === 'INCOME')
      .reduce((sum, tx) => {
        const lineTotal = tx.lines.reduce((s, line) => s + line.amount, 0)
        return sum + lineTotal
      }, 0)

    const totalExpenses = allTransactions
      .filter((tx) => tx.kind === 'EXPENSE')
      .reduce((sum, tx) => {
        const lineTotal = tx.lines.reduce((s, line) => s + line.amount, 0)
        return sum + lineTotal
      }, 0)

    const netResult = totalIncome + totalExpenses // expenses are negative

    return NextResponse.json({
      accounts: accountForecasts,
      totalIncome,
      totalExpenses,
      netResult,
    })
  } catch (error) {
    console.error('Error fetching forecast:', error)
    return NextResponse.json(
      { error: 'Failed to fetch forecast data' },
      { status: 500 }
    )
  }
}
