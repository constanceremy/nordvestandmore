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

    // Get query params
    const { searchParams } = new URL(request.url)
    const month = searchParams.get('month') || new Date().toISOString().slice(0, 7)
    const dateField = searchParams.get('dateField') || 'effectiveFor'

    // Parse month to get just YYYY-MM format
    const monthStr = month // Already in YYYY-MM format

    // Build query based on dateField
    let whereClause: any = {
      profileId: profile.id,
    }

    if (dateField === 'effectiveFor') {
      // Match effectiveForMonth as string (YYYY-MM)
      whereClause.effectiveForMonth = {
        gte: new Date(`${monthStr}-01`),
        lte: new Date(`${monthStr}-31`)
      }
    } else {
      // Match paidAt as date range
      const [year, monthNum] = monthStr.split('-').map(Number)
      whereClause.paidAt = {
        gte: new Date(year, monthNum - 1, 1),
        lte: new Date(year, monthNum, 0, 23, 59, 59)
      }
    }

    // Fetch all categories with their budget targets
    const allCategories = await prisma.category.findMany({
      where: { profileId: profile.id }
    })

    // Fetch transactions
    const transactions = await prisma.transaction.findMany({
      where: whereClause,
      include: {
        lines: {
          include: {
            category: true
          }
        }
      }
    })

    // Group by category
    const categoryMap: Record<string, { 
      categoryId: string
      categoryName: string
      target: number
      planned: number
      paid: number
    }> = {}

    // Initialize all categories with their targets
    allCategories.forEach(cat => {
      categoryMap[cat.id] = {
        categoryId: cat.id,
        categoryName: cat.name,
        target: cat.monthlyBudget ? Number(cat.monthlyBudget) : 0,
        planned: 0,
        paid: 0
      }
    })

    // Sum up transactions
    transactions.forEach(tx => {
      tx.lines.forEach(line => {
        // Skip lines without categories (transfers)
        if (!line.categoryId || !categoryMap[line.categoryId]) return

        const amount = Math.abs(Number(line.amount))
        if (tx.status === 'PLANNED') {
          categoryMap[line.categoryId].planned += amount
        } else {
          categoryMap[line.categoryId].paid += amount
        }
      })
    })

    // Convert to array
    const categoryBreakdown = Object.values(categoryMap).sort((a, b) => 
      a.categoryName.localeCompare(b.categoryName)
    )

    // Calculate totals
    const totalTarget = categoryBreakdown.reduce((sum, cat) => sum + cat.target, 0)
    const totalPlanned = categoryBreakdown.reduce((sum, cat) => sum + cat.planned, 0)
    const totalPaid = categoryBreakdown.reduce((sum, cat) => sum + cat.paid, 0)

    return NextResponse.json({
      categoryBreakdown,
      totals: {
        totalTarget,
        totalPlanned,
        totalPaid
      }
    })
  } catch (error: any) {
    console.error('Error fetching budget data:', error)
    return NextResponse.json(
      { error: error.message || 'Failed to fetch budget data' },
      { status: 500 }
    )
  }
}
