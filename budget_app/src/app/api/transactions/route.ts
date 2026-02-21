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

export async function GET(request: Request) {
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

    // Get query params
    const { searchParams } = new URL(request.url)
    const accountId = searchParams.get('account')
    const categoryId = searchParams.get('category')
    const status = searchParams.get('status')

    // Build where clause
    const where: any = {
      profileId: profile.id,
    }

    if (status) {
      where.status = status
    }

    if (accountId || categoryId) {
      where.lines = {
        some: {
          ...(accountId ? { accountId } : {}),
          ...(categoryId ? { categoryId } : {})
        }
      }
    }

    const transactions = await prisma.transaction.findMany({
      where,
      include: {
        lines: {
          include: {
            account: true,
            category: true
          }
        },
        recurrenceRule: true
      },
      orderBy: {
        paidAt: 'desc'
      }
    })

    return NextResponse.json(transactions)
  } catch (error: any) {
    console.error('Error fetching transactions:', error)
    return NextResponse.json(
      { error: error.message || 'Failed to fetch transactions' },
      { status: 500 }
    )
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

    const body = await request.json()
    const {
      kind,
      status,
      paidAt,
      effectiveForMonth,
      description,
      notes,
      accountId,
      amount,
      lines,
      fromAccountId,
      toAccountId,
      transferAmount,
      isRecurring,
      frequency,
      interval,
      repeatUntil,
      dayOfWeek,
      weekOfMonth
    } = body

    // Handle Transfer
    if (kind === 'TRANSFER') {
      const fromAccount = await prisma.account.findUnique({ where: { id: fromAccountId } })
      const toAccount = await prisma.account.findUnique({ where: { id: toAccountId } })

      if (!fromAccount || !toAccount) {
        return NextResponse.json({ error: 'Account not found' }, { status: 404 })
      }

      // Create recurrence rule if recurring
      let recurrenceRuleId = null
      if (isRecurring) {
        const rule = await prisma.recurrenceRule.create({
          data: {
            profileId: profile.id,
            title: description || 'Recurring Transfer',
            kind,
            statusDefault: status,
            startDate: new Date(paidAt),
            frequency,
            interval: interval || 1,
            repeatUntil: repeatUntil ? new Date(repeatUntil) : null,
            dayOfWeek: dayOfWeek !== undefined ? dayOfWeek : null,
            weekOfMonth: weekOfMonth !== undefined ? weekOfMonth : null,
          }
        })
        recurrenceRuleId = rule.id
      }

      // Generate dates (first occurrence + future ones if recurring)
      const dates = isRecurring 
        ? generateRecurringDates(
            new Date(paidAt), 
            frequency, 
            interval || 1,
            repeatUntil ? new Date(repeatUntil) : null,
            dayOfWeek !== undefined ? dayOfWeek : null,
            weekOfMonth !== undefined ? weekOfMonth : null
          )
        : [new Date(paidAt)]

      // Create transactions for all dates
      const transactions = await Promise.all(dates.map(async (date, index) => {
        const effectiveMonth = new Date(date)
        effectiveMonth.setDate(1)
        
        return prisma.transaction.create({
          data: {
            profileId: profile.id,
            kind,
            status: index === 0 ? status : 'PLANNED', // First one uses provided status, rest are planned
            paidAt: date,
            effectiveForMonth: effectiveForMonth ? new Date(effectiveForMonth) : effectiveMonth,
            description: description || 'Transfer',
            notes,
            recurrenceRuleId,
            lines: {
              create: [
                {
                  accountId: fromAccountId,
                  amount: -Math.abs(transferAmount),
                  currency: fromAccount.currency,
                },
                {
                  accountId: toAccountId,
                  amount: Math.abs(transferAmount),
                  currency: toAccount.currency,
                }
              ]
            }
          },
          include: {
            lines: true
          }
        })
      }))

      return NextResponse.json({ 
        message: isRecurring ? `Created ${transactions.length} transactions` : 'Transaction created',
        count: transactions.length,
        transaction: transactions[0] 
      })
    }

    // Handle Expense/Income
    const account = await prisma.account.findUnique({ where: { id: accountId } })
    if (!account) {
      return NextResponse.json({ error: 'Account not found' }, { status: 404 })
    }

    // Determine sign based on kind
    const sign = kind === 'EXPENSE' ? -1 : 1

    // Create recurrence rule if recurring
    let recurrenceRuleId = null
    if (isRecurring) {
      const rule = await prisma.recurrenceRule.create({
        data: {
          profileId: profile.id,
          title: description || 'Recurring Transaction',
          kind,
          statusDefault: status,
          startDate: new Date(paidAt),
          frequency,
          interval: interval || 1,
          repeatUntil: repeatUntil ? new Date(repeatUntil) : null,
          dayOfWeek: dayOfWeek !== undefined ? dayOfWeek : null,
          weekOfMonth: weekOfMonth !== undefined ? weekOfMonth : null,
        }
      })
      recurrenceRuleId = rule.id
    }

    // Generate dates (first occurrence + future ones if recurring)
    const dates = isRecurring 
      ? generateRecurringDates(
          new Date(paidAt), 
          frequency, 
          interval || 1,
          repeatUntil ? new Date(repeatUntil) : null,
          dayOfWeek !== undefined ? dayOfWeek : null,
          weekOfMonth !== undefined ? weekOfMonth : null
        )
      : [new Date(paidAt)]

    // Calculate the offset between paidAt and effectiveForMonth (in months)
    const originalPaidAt = new Date(paidAt)
    const originalEffectiveFor = effectiveForMonth ? new Date(effectiveForMonth) : new Date(paidAt)
    originalEffectiveFor.setDate(1) // Normalize to first of month
    
    const monthOffset = (originalEffectiveFor.getFullYear() - originalPaidAt.getFullYear()) * 12 
                      + (originalEffectiveFor.getMonth() - originalPaidAt.getMonth())

    // Create transactions for all dates
    const transactions = await Promise.all(dates.map(async (date, index) => {
      // Apply the same month offset to each recurring instance
      const effectiveMonth = new Date(date)
      effectiveMonth.setMonth(effectiveMonth.getMonth() + monthOffset)
      effectiveMonth.setDate(1) // Normalize to first of month
      
      return prisma.transaction.create({
        data: {
          profileId: profile.id,
          kind,
          status: index === 0 ? status : 'PLANNED', // First one uses provided status, rest are planned
          paidAt: date,
          effectiveForMonth: effectiveMonth, // Apply the month offset from original
          description: description || 'Transaction',
          notes,
          recurrenceRuleId,
          lines: {
            create: lines.map((line: any) => ({
              accountId,
              categoryId: line.categoryId,
              amount: sign * Math.abs(line.amount),
              currency: account.currency,
            }))
          }
        },
        include: {
          lines: {
            include: {
              category: true
            }
          }
        }
      })
    }))

    return NextResponse.json({ 
      message: isRecurring ? `Created ${transactions.length} transactions` : 'Transaction created',
      count: transactions.length,
      transaction: transactions[0] 
    })
  } catch (error: any) {
    console.error('Error creating transaction:', error)
    return NextResponse.json(
      { error: error.message || 'Failed to create transaction' },
      { status: 500 }
    )
  }
}
