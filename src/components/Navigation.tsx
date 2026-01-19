'use client'

import { usePathname } from 'next/navigation'
import Link from 'next/link'

export default function Navigation() {
  const pathname = usePathname()
  
  return (
    <nav className="bg-zen-stone-light border-b border-zen-stone-dark sticky top-0 z-50 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex space-x-8 items-center">
            <Link
              href="/home"
              className={`inline-flex items-center px-1 pt-1 text-sm font-medium ${
                pathname === '/home'
                  ? 'border-b-2 border-zen-sage text-zen-charcoal'
                  : 'text-zen-charcoal-light hover:text-zen-charcoal'
              }`}
            >
              Home
            </Link>
            <Link
              href="/transactions"
              className={`inline-flex items-center px-1 pt-1 text-sm font-medium ${
                pathname.startsWith('/transactions')
                  ? 'border-b-2 border-zen-sage text-zen-charcoal'
                  : 'text-zen-charcoal-light hover:text-zen-charcoal'
              }`}
            >
              Transactions
            </Link>
            <Link
              href="/accounts"
              className={`inline-flex items-center px-1 pt-1 text-sm font-medium ${
                pathname.startsWith('/accounts')
                  ? 'border-b-2 border-zen-sage text-zen-charcoal'
                  : 'text-zen-charcoal-light hover:text-zen-charcoal'
              }`}
            >
              Accounts
            </Link>
            <Link
              href="/categories"
              className={`inline-flex items-center px-1 pt-1 text-sm font-medium ${
                pathname.startsWith('/categories')
                  ? 'border-b-2 border-zen-sage text-zen-charcoal'
                  : 'text-zen-charcoal-light hover:text-zen-charcoal'
              }`}
            >
              Categories
            </Link>
            <Link
              href="/transactions/add"
              className="inline-flex items-center px-1 pt-1 text-sm font-medium text-zen-sage-dark hover:text-zen-sage"
            >
              + Add
            </Link>
          </div>
          <div className="flex items-center">
            <form action="/api/auth/signout" method="post">
              <button
                type="submit"
                className="text-sm text-zen-charcoal-light hover:text-zen-charcoal"
              >
                Sign Out
              </button>
            </form>
          </div>
        </div>
      </div>
    </nav>
  )
}
