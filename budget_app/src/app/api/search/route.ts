import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { prisma } from '@/lib/prisma'

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

    const { searchParams } = new URL(request.url)
    const query = searchParams.get('q') || ''
    const category = searchParams.get('category')
    const account = searchParams.get('account')
    const status = searchParams.get('status')
    const minAmount = searchParams.get('minAmount')
    const maxAmount = searchParams.get('maxAmount')
    const startDate = searchParams.get('startDate')
    const endDate = searchParams.get('endDate')
    const dateField = searchParams.get('dateField') || 'paidAt' // 'paidAt' or 'effectiveFor'

    // Build where clause
    const where: any = {
      profileId: profile.id,
    }

    // Text search on description and notes
    if (query) {
      where.OR = [
        {
          description: {
            contains: query,
            mode: 'insensitive'
          }
        },
        {
          notes: {
            contains: query,
            mode: 'insensitive'
          }
        }
      ]
    }

    // Status filter
    if (status) {
      where.status = status
    }

    // Date range filter
    if (startDate || endDate) {
      console.log('Date filtering:', { startDate, endDate, dateField })
      if (dateField === 'effectiveFor') {
        // effectiveForMonth is a string field (YYYY-MM), so we need to filter differently
        if (startDate && endDate) {
          const startMonth = startDate.substring(0, 7) // "2026-02-01" -> "2026-02"
          const endMonth = endDate.substring(0, 7)     // "2026-02-28" -> "2026-02"
          
          console.log('Filtering by effectiveForMonth:', { startMonth, endMonth })
          if (startMonth === endMonth) {
            // Same month - exact match
            where.effectiveForMonth = startMonth
          } else {
            // Date range spans multiple months
            where.effectiveForMonth = {
              gte: startMonth,
              lte: endMonth
            }
          }
        } else if (startDate) {
          where.effectiveForMonth = {
            gte: startDate.substring(0, 7)
          }
        } else if (endDate) {
          where.effectiveForMonth = {
            lte: endDate.substring(0, 7)
          }
        }
      } else {
        // paidAt is a DateTime field
        where.paidAt = {}
        if (startDate) {
          where.paidAt.gte = new Date(startDate)
        }
        if (endDate) {
          const end = new Date(endDate)
          end.setHours(23, 59, 59, 999)
          where.paidAt.lte = end
        }
      }
    }
    
    console.log('Final where clause:', JSON.stringify(where, null, 2))

    // Category or account filter (via lines)
    if (account || category) {
      where.lines = {
        some: {
          ...(account ? { accountId: account } : {}),
          ...(category ? { categoryId: category } : {})
        }
      }
    }

    // Fetch transactions
    let transactions = await prisma.transaction.findMany({
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
      },
      take: 500 // Limit results
    })

    // Filter by amount range (post-query since amount is calculated)
    if (minAmount || maxAmount) {
      transactions = transactions.filter(tx => {
        const totalAmount = tx.lines.reduce((sum, line) => sum + Math.abs(Number(line.amount)), 0)
        if (minAmount && totalAmount < parseFloat(minAmount)) return false
        if (maxAmount && totalAmount > parseFloat(maxAmount)) return false
        return true
      })
    }

    return NextResponse.json(transactions)
  } catch (error: any) {
    console.error('Error searching transactions:', error)
    return NextResponse.json(
      { error: error.message || 'Failed to search transactions' },
      { status: 500 }
    )
  }
}
