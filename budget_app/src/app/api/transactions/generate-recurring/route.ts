import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { prisma } from '@/lib/prisma'

// Helper function to generate recurring transaction dates
function generateRecurringDates(
  startDate: Date,
  frequency: 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'YEARLY',
  interval: number = 1,
  repeatUntil: Date | null,
  dayOfWeek: number | null = null,
  weekOfMonth: number | null = null,
  horizonMonths: number = 24
): Date[] {
  const dates: Date[] = []
  const horizon = new Date()
  horizon.setMonth(horizon.getMonth() + horizonMonths)
  const endDate = repeatUntil && repeatUntil < horizon ? repeatUntil : horizon

  // Handle nth weekday of month pattern
  if (dayOfWeek !== null && weekOfMonth !== null) {
    let currentDate = new Date(startDate)
    currentDate.setDate(1) // Start at first of month
    
    while (currentDate <= endDate) {
      const nthWeekday = getNthWeekdayOfMonth(currentDate.getFullYear(), currentDate.getMonth(), dayOfWeek, weekOfMonth)
      if (nthWeekday && nthWeekday >= startDate && nthWeekday <= endDate) {
        dates.push(new Date(nthWeekday))
      }
      currentDate.setMonth(currentDate.getMonth() + 1)
    }
    
    return dates
  }

  // Handle simple interval pattern
  let currentDate = new Date(startDate)
  
  while (currentDate <= endDate) {
    dates.push(new Date(currentDate))
    
    switch (frequency) {
      case 'DAILY':
        currentDate.setDate(currentDate.getDate() + interval)
        break
      case 'WEEKLY':
        currentDate.setDate(currentDate.getDate() + (7 * interval))
        break
      case 'MONTHLY':
        currentDate.setMonth(currentDate.getMonth() + interval)
        break
      case 'YEARLY':
        currentDate.setFullYear(currentDate.getFullYear() + interval)
        break
    }
  }
  
  return dates
}

// Helper to get the nth occurrence of a weekday in a month
function getNthWeekdayOfMonth(year: number, month: number, dayOfWeek: number, weekOfMonth: number): Date | null {
  const firstDay = new Date(year, month, 1)
  
  if (weekOfMonth === -1) {
    // Last occurrence
    const lastDay = new Date(year, month + 1, 0)
    const lastDayOfWeek = lastDay.getDay()
    const daysBack = (lastDayOfWeek - dayOfWeek + 7) % 7
    return new Date(year, month, lastDay.getDate() - daysBack)
  } else {
    // Nth occurrence (1st, 2nd, 3rd, 4th)
    const firstDayOfWeek = firstDay.getDay()
    const daysUntilTarget = (dayOfWeek - firstDayOfWeek + 7) % 7
    const targetDate = 1 + daysUntilTarget + ((weekOfMonth - 1) * 7)
    
    // Check if this date exists in the month
    const result = new Date(year, month, targetDate)
    if (result.getMonth() !== month) {
      return null // This nth weekday doesn't exist in this month
    }
    return result
  }
}

export async function POST(request: Request) {
  try {
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const profile = await prisma.profile.findFirst({
      where: { userId: user.id }
    })

    if (!profile) {
      return NextResponse.json({ error: 'Profile not found' }, { status: 404 })
    }

    // Find all active recurrence rules for this profile
    const recurrenceRules = await prisma.recurrenceRule.findMany({
      where: {
        profileId: profile.id,
        OR: [
          { repeatUntil: null }, // No end date
          { repeatUntil: { gte: new Date() } } // Or end date in the future
        ]
      },
      include: {
        transactions: {
          orderBy: {
            paidAt: 'desc'
          },
          take: 1 // Get the most recent transaction for this rule
        }
      }
    })

    let totalCreated = 0

    // For each recurrence rule, generate missing transactions
    for (const rule of recurrenceRules) {
      if (rule.transactions.length === 0) continue

      const templateTransaction = rule.transactions[0]
      
      // Get the latest existing transaction date for this rule
      const allExistingTransactions = await prisma.transaction.findMany({
        where: {
          recurrenceRuleId: rule.id
        },
        orderBy: {
          paidAt: 'desc'
        }
      })

      const latestDate = allExistingTransactions.length > 0 
        ? new Date(allExistingTransactions[0].paidAt)
        : new Date()

      // Generate all dates that should exist
      const firstTransaction = await prisma.transaction.findFirst({
        where: {
          recurrenceRuleId: rule.id
        },
        orderBy: {
          paidAt: 'asc'
        }
      })

      if (!firstTransaction) continue

      const allDates = generateRecurringDates(
        new Date(firstTransaction.paidAt),
        rule.frequency,
        rule.interval || 1,
        rule.repeatUntil,
        rule.dayOfWeek,
        rule.weekOfMonth
      )

      // Find which dates are missing
      const existingDates = new Set(
        allExistingTransactions.map(tx => new Date(tx.paidAt).toISOString().split('T')[0])
      )

      const missingDates = allDates.filter(
        date => !existingDates.has(date.toISOString().split('T')[0])
      )

      // Calculate the offset between paidAt and effectiveForMonth from the first transaction
      const firstPaidAt = new Date(firstTransaction.paidAt)
      const firstEffectiveFor = firstTransaction.effectiveForMonth 
        ? new Date(firstTransaction.effectiveForMonth) 
        : new Date(firstPaidAt)
      firstEffectiveFor.setDate(1) // Normalize to first of month
      
      const monthOffset = (firstEffectiveFor.getFullYear() - firstPaidAt.getFullYear()) * 12 
                        + (firstEffectiveFor.getMonth() - firstPaidAt.getMonth())

      // Create missing transactions
      for (const date of missingDates) {
        // Apply the same month offset as the original transaction
        const effectiveMonth = new Date(date)
        effectiveMonth.setMonth(effectiveMonth.getMonth() + monthOffset)
        effectiveMonth.setDate(1) // Normalize to first of month

        // Get transaction lines from template
        const templateLines = await prisma.transactionLine.findMany({
          where: {
            transactionId: templateTransaction.id
          }
        })

        await prisma.transaction.create({
          data: {
            profileId: profile.id,
            kind: templateTransaction.kind,
            status: 'PLANNED',
            paidAt: date,
            effectiveForMonth: effectiveMonth, // Apply the month offset from original
            description: templateTransaction.description,
            notes: templateTransaction.notes,
            recurrenceRuleId: rule.id,
            lines: {
              create: templateLines.map(line => ({
                accountId: line.accountId,
                categoryId: line.categoryId,
                amount: line.amount,
                currency: line.currency,
              }))
            }
          }
        })

        totalCreated++
      }
    }

    return NextResponse.json({ 
      message: `Generated ${totalCreated} new recurring transactions`,
      created: totalCreated 
    })
  } catch (error: any) {
    console.error('Error generating recurring transactions:', error)
    return NextResponse.json(
      { error: error.message || 'Failed to generate recurring transactions' },
      { status: 500 }
    )
  }
}
