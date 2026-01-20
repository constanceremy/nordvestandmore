'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import LoadingSpinner from '@/components/LoadingSpinner'

type Account = {
  id: string
  name: string
  type: string
  currency: string
  currentBalance: number
}

export default function AccountsPage() {
  const router = useRouter()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchAccounts()
  }, [])

  const fetchAccounts = async () => {
    try {
      const res = await fetch('/api/accounts')
      if (!res.ok) {
        if (res.status === 401) {
          router.push('/login')
          return
        }
        // If it's just an error (like no accounts), set empty array
        setAccounts([])
        setLoading(false)
        return
      }
      const data = await res.json()
      
      // If no accounts, just set empty array
      if (!data || data.length === 0) {
        setAccounts([])
        setLoading(false)
        return
      }
      
      // Calculate balances for each account
      const accountsWithBalances = await Promise.all(
        data.map(async (account: any) => {
          const detailRes = await fetch(`/api/accounts/${account.id}`)
          if (detailRes.ok) {
            const detail = await detailRes.json()
            return {
              ...account,
              currentBalance: detail.currentBalance || 0
            }
          }
          return { ...account, currentBalance: 0 }
        })
      )
      
      setAccounts(accountsWithBalances)
    } catch (error) {
      // Silent fail - just show empty state
      setAccounts([])
    } finally {
      setLoading(false)
    }
  }

  const formatCurrency = (amount: number, currency: string) => {
    return new Intl.NumberFormat('da-DK', {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 2
    }).format(amount)
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-zen-stone flex items-center justify-center">
        <LoadingSpinner size="lg" text="Loading accounts..." />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-zen-stone">
      <div className="max-w-6xl mx-auto p-6">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-zen-charcoal">Accounts</h1>
          <Link
            href="/accounts/new"
            className="px-4 py-2 bg-zen-sage text-white rounded-lg hover:bg-zen-sage-dark transition-colors shadow-md"
          >
            + New Account
          </Link>
        </div>

        {accounts.length === 0 ? (
          <div className="bg-zen-stone-light rounded-xl shadow-md p-12 text-center">
            <div className="text-6xl mb-4">🏦</div>
            <h3 className="text-xl font-semibold text-zen-charcoal mb-3">No Accounts Yet</h3>
            <p className="text-zen-charcoal/60 mb-6 text-sm max-w-md mx-auto">
              Create your first account to start tracking your finances. Add bank accounts, credit cards, or cash.
            </p>
            <Link
              href="/accounts/new"
              className="inline-block px-6 py-3 bg-zen-sage text-white rounded-lg hover:bg-zen-sage-dark transition-colors shadow-md"
            >
              + Create Your First Account
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {accounts.map((account) => (
              <div
                key={account.id}
                className="bg-zen-stone-light rounded-xl shadow-md hover:shadow-xl transition-all duration-300 p-6 border-l-4 border-zen-sage"
              >
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="font-bold text-xl text-zen-charcoal mb-1">
                      {account.name}
                    </h3>
                    <p className="text-sm text-zen-charcoal-light capitalize">
                      {account.type.toLowerCase().replace('_', ' ')}
                    </p>
                  </div>
                </div>

                <div className="mb-6">
                  <p className="text-3xl font-bold text-zen-sage-dark">
                    {formatCurrency(account.currentBalance, account.currency)}
                  </p>
                  <p className="text-xs text-zen-charcoal-light mt-1">Current Balance</p>
                </div>

                <div className="flex gap-2">
                  <Link
                    href={`/accounts/${account.id}`}
                    className="flex-1 px-3 py-2 bg-zen-sage text-white rounded-lg hover:bg-zen-sage-dark transition-colors text-center text-sm"
                  >
                    View
                  </Link>
                  <Link
                    href={`/accounts/${account.id}/edit`}
                    className="flex-1 px-3 py-2 bg-zen-stone-dark text-zen-charcoal rounded-lg hover:bg-zen-sand transition-colors text-center text-sm"
                  >
                    Edit
                  </Link>
                  <Link
                    href={`/accounts/${account.id}/reconcile`}
                    className="flex-1 px-3 py-2 bg-zen-stone-dark text-zen-charcoal rounded-lg hover:bg-zen-sand transition-colors text-center text-sm"
                  >
                    Reconcile
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
