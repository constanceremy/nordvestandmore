'use client'

import { usePathname } from 'next/navigation'
import Link from 'next/link'

export default function Navigation() {
  const pathname = usePathname()
  
  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex space-x-8 items-center">
            <Link
              href="/home"
              className={`inline-flex items-center px-1 pt-1 text-sm font-medium ${
                pathname === '/home'
                  ? 'border-b-2 border-blue-500 text-gray-900'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Home
            </Link>
            <Link
              href="/transactions"
              className={`inline-flex items-center px-1 pt-1 text-sm font-medium ${
                pathname.startsWith('/transactions')
                  ? 'border-b-2 border-blue-500 text-gray-900'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Transactions
            </Link>
            <Link
              href="/accounts"
              className={`inline-flex items-center px-1 pt-1 text-sm font-medium ${
                pathname.startsWith('/accounts')
                  ? 'border-b-2 border-blue-500 text-gray-900'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Accounts
            </Link>
            <Link
              href="/categories"
              className={`inline-flex items-center px-1 pt-1 text-sm font-medium ${
                pathname.startsWith('/categories')
                  ? 'border-b-2 border-blue-500 text-gray-900'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Categories
            </Link>
            <Link
              href="/transactions/add"
              className="inline-flex items-center px-1 pt-1 text-sm font-medium text-blue-600 hover:text-blue-800"
            >
              + Add
            </Link>
          </div>
          <div className="flex items-center">
            <form action="/api/auth/signout" method="post">
              <button
                type="submit"
                className="text-sm text-gray-500 hover:text-gray-700"
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
