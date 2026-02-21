import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { prisma } from '@/lib/prisma'

export async function GET(
  request: Request,
  context: { params: Promise<{ id: string }> }
) {
  try {
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const { id } = await context.params

    const profile = await prisma.profile.findFirst({
      where: { userId: user.id }
    })

    if (!profile) {
      return NextResponse.json({ error: 'Profile not found' }, { status: 404 })
    }

    // Get account
    const account = await prisma.account.findUnique({
      where: { id }
    })

    if (!account || account.profileId !== profile.id) {
      return NextResponse.json({ error: 'Account not found' }, { status: 404 })
    }

    // Get all transaction lines for this account
    const lines = await prisma.transactionLine.findMany({
      where: { accountId: id },
      include: {
        transaction: true,
        category: true,
      },
      orderBy: {
        transaction: {
          paidAt: 'desc'
        }
      }
    })

    // Sort lines by date (newest first for display)
    const sortedLines = [...lines].sort((a, b) => 
      new Date(b.transaction.paidAt).getTime() - new Date(a.transaction.paidAt).getTime()
    )

    // Calculate running balances (from oldest to newest for accurate balance)
    const linesForBalance = [...sortedLines].reverse()
    let runningBalance = Number(account.openingBalance)
    const linesWithBalance = linesForBalance.map(line => {
      runningBalance = runningBalance + Number(line.amount)
      return {
        id: line.id,
        amount: line.amount.toString(),
        runningBalance,
        transaction: {
          id: line.transaction.id,
          paidAt: line.transaction.paidAt.toISOString(),
          description: line.transaction.description,
          notes: line.transaction.notes,
          status: line.transaction.status,
        },
        category: line.category ? { name: line.category.name } : null,
      }
    }).reverse() // Reverse back to newest first

    // Calculate current balance (paid only)
    const currentBalance = lines
      .filter(line => line.transaction.status === 'PAID')
      .reduce((sum, line) => sum + Number(line.amount), Number(account.openingBalance))

    // Calculate expected balance (paid + planned)
    const expectedBalance = lines
      .reduce((sum, line) => sum + Number(line.amount), Number(account.openingBalance))

    return NextResponse.json({
      account: {
        id: account.id,
        name: account.name,
        type: account.type,
        currency: account.currency,
        openingBalance: account.openingBalance.toString(),
        openingBalanceDate: account.openingBalanceDate.toISOString(),
      },
      linesWithBalance,
      currentBalance,
      expectedBalance,
    })
  } catch (error) {
    console.error('Error fetching account details:', error)
    return NextResponse.json({ error: 'Failed to fetch account details' }, { status: 500 })
  }
}

export async function PUT(
  request: Request,
  context: { params: Promise<{ id: string }> }
) {
  try {
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const { id } = await context.params
    const body = await request.json()
    const { name, currency } = body

    const profile = await prisma.profile.findFirst({
      where: { userId: user.id }
    })

    if (!profile) {
      return NextResponse.json({ error: 'Profile not found' }, { status: 404 })
    }

    // Verify account belongs to user
    const account = await prisma.account.findUnique({
      where: { id }
    })

    if (!account || account.profileId !== profile.id) {
      return NextResponse.json({ error: 'Account not found' }, { status: 404 })
    }

    // Update account
    const updatedAccount = await prisma.account.update({
      where: { id },
      data: {
        name,
        currency,
      }
    })

    return NextResponse.json(updatedAccount)
  } catch (error) {
    console.error('Error updating account:', error)
    return NextResponse.json({ error: 'Failed to update account' }, { status: 500 })
  }
}
