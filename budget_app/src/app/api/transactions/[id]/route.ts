import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { prisma } from '@/lib/prisma'

// GET single transaction
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

    const transaction = await prisma.transaction.findUnique({
      where: { id },
      include: {
        lines: {
          include: {
            account: true,
            category: true,
          },
        },
      },
    })

    if (!transaction) {
      return NextResponse.json({ error: 'Transaction not found' }, { status: 404 })
    }

    // Check ownership via account
    const accountIds = transaction.lines.map(l => l.accountId)
    const accounts = await prisma.account.findMany({
      where: {
        id: { in: accountIds },
        profile: { userId: user.id },
      },
    })

    if (accounts.length === 0) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 403 })
    }

    return NextResponse.json(transaction)
  } catch (error) {
    console.error('Error fetching transaction:', error)
    return NextResponse.json({ error: 'Failed to fetch transaction' }, { status: 500 })
  }
}

// PUT (update) transaction
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
    const { status, paidAt, effectiveForMonth, description, notes, accountId, amount, lines, fromAccountId, toAccountId, transferAmount } = body

    // Verify ownership
    const existingTransaction = await prisma.transaction.findUnique({
      where: { id },
      include: { lines: { include: { account: { include: { profile: true } } } } },
    })

    if (!existingTransaction) {
      return NextResponse.json({ error: 'Transaction not found' }, { status: 404 })
    }

    if (existingTransaction.lines.some(l => l.account.profile.userId !== user.id)) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 403 })
    }

    // Simple status/date update only (for "Mark as Paid" button)
    if (status && paidAt && !accountId && !lines && !fromAccountId && !toAccountId) {
      const updated = await prisma.transaction.update({
        where: { id },
        data: {
          status,
          paidAt: new Date(paidAt),
        },
        include: { lines: true },
      })
      return NextResponse.json(updated)
    }

    // For TRANSFER, allow full editing
    if (existingTransaction.kind === 'TRANSFER') {
      // Get currencies from accounts
      const fromAccount = await prisma.account.findUnique({
        where: { id: fromAccountId },
        select: { currency: true }
      })
      const toAccount = await prisma.account.findUnique({
        where: { id: toAccountId },
        select: { currency: true }
      })

      if (!fromAccount || !toAccount) {
        return NextResponse.json({ error: 'Invalid accounts' }, { status: 400 })
      }

      // Delete old lines
      await prisma.transactionLine.deleteMany({
        where: { transactionId: id },
      })

      // Create new transfer lines
      const updated = await prisma.transaction.update({
        where: { id },
        data: {
          status,
          paidAt: new Date(paidAt),
          effectiveForMonth: effectiveForMonth ? new Date(effectiveForMonth) : null,
          description: description || existingTransaction.description,
          notes: notes || null,
          lines: {
            create: [
              {
                accountId: fromAccountId,
                categoryId: null,
                amount: -Math.abs(transferAmount),
                currency: fromAccount.currency,
              },
              {
                accountId: toAccountId,
                categoryId: null,
                amount: Math.abs(transferAmount),
                currency: toAccount.currency,
              },
            ],
          },
        },
        include: { lines: true },
      })
      return NextResponse.json(updated)
    }

    // For EXPENSE/INCOME, allow full update
    const isExpense = existingTransaction.kind === 'EXPENSE'
    const signMultiplier = isExpense ? -1 : 1

    // Get account currency
    const account = await prisma.account.findUnique({
      where: { id: accountId },
      select: { currency: true }
    })

    if (!account) {
      return NextResponse.json({ error: 'Invalid account' }, { status: 400 })
    }

    // Delete old lines
    await prisma.transactionLine.deleteMany({
      where: { transactionId: id },
    })

    // Create new lines
    const newLines = lines.map((line: { categoryId: string; amount: number }) => ({
      accountId,
      categoryId: line.categoryId,
      amount: line.amount * signMultiplier,
      currency: account.currency,
    }))

    const updated = await prisma.transaction.update({
      where: { id },
      data: {
        status,
        paidAt: new Date(paidAt),
        effectiveForMonth: effectiveForMonth ? new Date(effectiveForMonth) : null,
        description: description || existingTransaction.description,
        notes: notes || null,
        lines: {
          create: newLines,
        },
      },
      include: {
        lines: {
          include: {
            account: true,
            category: true,
          },
        },
      },
    })

    return NextResponse.json(updated)
  } catch (error) {
    console.error('Error updating transaction:', error)
    return NextResponse.json({ error: 'Failed to update transaction' }, { status: 500 })
  }
}

// DELETE transaction
export async function DELETE(
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

    // Verify ownership
    const existingTransaction = await prisma.transaction.findUnique({
      where: { id },
      include: { lines: { include: { account: { include: { profile: true } } } } },
    })

    if (!existingTransaction) {
      return NextResponse.json({ error: 'Transaction not found' }, { status: 404 })
    }

    if (existingTransaction.lines.some(l => l.account.profile.userId !== user.id)) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 403 })
    }

    // Delete transaction (lines will cascade)
    await prisma.transaction.delete({
      where: { id },
    })

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error('Error deleting transaction:', error)
    return NextResponse.json({ error: 'Failed to delete transaction' }, { status: 500 })
  }
}
