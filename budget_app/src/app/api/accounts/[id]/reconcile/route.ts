import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { prisma } from '@/lib/prisma'

export async function POST(
  request: Request,
  context: { params: Promise<{ id: string }> }
) {
  try {
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const { id: accountId } = await context.params
    const body = await request.json()
    const { newBalance, reconcileDate, notes } = body

    const profile = await prisma.profile.findFirst({
      where: { userId: user.id }
    })

    if (!profile) {
      return NextResponse.json({ error: 'Profile not found' }, { status: 404 })
    }

    // Verify account belongs to user
    const account = await prisma.account.findUnique({
      where: { id: accountId },
      include: {
        lines: {
          where: {
            transaction: {
              status: 'PAID'
            }
          }
        }
      }
    })

    if (!account || account.profileId !== profile.id) {
      return NextResponse.json({ error: 'Account not found' }, { status: 404 })
    }

    // Calculate current balance
    const transactionTotal = account.lines.reduce((sum, line) => 
      sum + Number(line.amount), 0
    )
    const currentBalance = Number(account.openingBalance) + transactionTotal
    const difference = Number(newBalance) - currentBalance

    // If no difference, nothing to do
    if (difference === 0) {
      return NextResponse.json({ message: 'Balance already matches' })
    }

    // Create a reconciliation transaction
    // This is a special transaction that adjusts the balance
    const reconcileMonth = new Date(reconcileDate)
    // Set effectiveForMonth to the first day of the month
    const effectiveForMonth = new Date(reconcileMonth.getFullYear(), reconcileMonth.getMonth(), 1)

    // Determine transaction kind based on difference
    // Positive difference = money added to account (INCOME)
    // Negative difference = money removed from account (EXPENSE)
    const transactionKind = difference > 0 ? 'INCOME' : 'EXPENSE'

    const transaction = await prisma.transaction.create({
      data: {
        profileId: profile.id,
        kind: transactionKind,
        paidAt: new Date(reconcileDate),
        effectiveForMonth,
        description: 'Balance Reconciliation',
        notes: notes || `Reconciliation adjustment: ${difference > 0 ? '+' : ''}${difference.toFixed(2)} ${account.currency}`,
        status: 'PAID',
        lines: {
          create: {
            accountId: accountId,
            categoryId: null, // No category for reconciliation
            amount: difference,
            currency: account.currency,
          }
        }
      }
    })

    return NextResponse.json({ 
      success: true, 
      transaction,
      adjustment: difference 
    })
  } catch (error) {
    console.error('Error reconciling account:', error)
    return NextResponse.json({ error: 'Failed to reconcile account' }, { status: 500 })
  }
}
