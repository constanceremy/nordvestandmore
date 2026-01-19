import { createClient } from '@/lib/supabase/server'
import { redirect } from 'next/navigation'
import { prisma } from '@/lib/prisma'

async function ensureProfile(userId: string, email: string) {
  // Check if profile exists
  let profile = await prisma.profile.findFirst({
    where: { userId }
  })

  // If not, create user and profile
  if (!profile) {
    // First ensure user exists
    let user = await prisma.user.findUnique({
      where: { id: userId }
    })

    if (!user) {
      user = await prisma.user.create({
        data: {
          id: userId,
          email,
        }
      })
    }

    // Then create profile
    profile = await prisma.profile.create({
      data: {
        userId,
        primaryCurrency: 'DKK',
        timezone: 'Europe/Copenhagen',
      }
    })
  }

  return profile
}

export default async function AccountsPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    redirect('/login')
  }

  // Ensure user has a profile
  const profile = await ensureProfile(user.id, user.email!)

  const accounts = await prisma.account.findMany({
    where: { 
      profileId: profile.id,
      archived: false 
    },
    include: {
      lines: {
        where: {
          transaction: {
            status: 'PAID'
          }
        }
      }
    },
    orderBy: { createdAt: 'asc' }
  })

  // Calculate current balances
  const accountsWithBalances = accounts.map(account => {
    const transactionTotal = account.lines.reduce((sum, line) => 
      sum + Number(line.amount), 0
    )
    const currentBalance = Number(account.openingBalance) + transactionTotal
    return {
      ...account,
      currentBalance
    }
  })

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto p-6">
        <h1 className="text-3xl font-bold mb-6">Accounts</h1>

        {accounts.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <p className="text-gray-600 mb-4">No accounts yet. Create your first account!</p>
            <a
              href="/accounts/new"
              className="inline-block px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Create Account
            </a>
          </div>
        ) : (
          <div className="space-y-4">
            {accountsWithBalances.map((account) => (
              <a
                key={account.id}
                href={`/accounts/${account.id}`}
                className="block bg-white rounded-lg shadow p-6 hover:shadow-lg transition-shadow"
              >
                <h3 className="text-xl font-semibold">{account.name}</h3>
                <p className="text-sm text-gray-500">{account.type} • {account.currency}</p>
                <p className="text-2xl font-bold mt-2">
                  {account.currentBalance.toFixed(2)} {account.currency}
                </p>
              </a>
            ))}

            <a
              href="/accounts/new"
              className="block w-full py-3 text-center border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-gray-400 hover:text-gray-700"
            >
              + Add Account
            </a>
          </div>
        )}
      </div>
    </div>
  )
}
