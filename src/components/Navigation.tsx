'use client'

import { usePathname } from 'next/navigation'
import Link from 'next/link'
import { useState } from 'react'

export default function Navigation() {
  const pathname = usePathname()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  
  // Hide navigation on login, signup, and auth pages
  const hideNav = pathname === '/login' || 
                  pathname === '/signup' || 
                  pathname.startsWith('/auth/') ||
                  pathname === '/onboarding'
  
  if (hideNav) {
    return null
  }
  
  return (
    <nav className="bg-zen-stone-light border-b border-zen-stone-dark sticky top-0 z-50 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          {/* Logo/Brand - visible on mobile */}
          <div className="flex items-center">
            <Link href="/home" className="text-lg font-semibold text-zen-sage-dark">
              Balance 🌿
            </Link>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:flex space-x-8 items-center">
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
              className={`inline-flex items-centers px-1 pt-1 text-sm font-medium ${
                pathname.startsWith('/categories')
                  ? 'border-b-2 border-zen-sage text-zen-charcoal'
                  : 'text-zen-charcoal-light hover:text-zen-charcoal'
              }`}
            >
              Categories
            </Link>
            <Link
              href="/transactions/add"
              className="inline-flex items-center px-4 py-2 bg-zen-sage text-white rounded-lg hover:bg-zen-sage-dark transition-colors text-sm font-medium"
            >
              + Add
            </Link>
          </div>

          {/* Desktop Right Side */}
          <div className="hidden md:flex space-x-8 items-center">
            <Link
              href="/profile"
              className={`inline-flex items-center px-1 pt-1 text-sm font-medium ${
                pathname === '/profile'
                  ? 'border-b-2 border-zen-sage text-zen-charcoal'
                  : 'text-zen-charcoal-light hover:text-zen-charcoal'
              }`}
            >
              Profile
            </Link>
            <form action="/api/auth/signout" method="post">
              <button
                type="submit"
                className="inline-flex items-center px-1 pt-1 text-sm font-medium text-zen-charcoal-light hover:text-zen-charcoal"
              >
                Sign Out
              </button>
            </form>
          </div>

          {/* Mobile menu button */}
          <div className="flex items-center md:hidden">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="inline-flex items-center justify-center p-2 rounded-md text-zen-charcoal hover:text-zen-sage hover:bg-zen-stone transition-colors"
              aria-expanded="false"
            >
              <span className="sr-only">Open main menu</span>
              {mobileMenuOpen ? (
                <svg className="block h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="block h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-zen-stone-dark">
          <div className="px-2 pt-2 pb-3 space-y-1">
            <Link
              href="/home"
              className={`block px-3 py-2 rounded-md text-base font-medium ${
                pathname === '/home'
                  ? 'bg-zen-sage text-white'
                  : 'text-zen-charcoal hover:bg-zen-stone'
              }`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Home
            </Link>
            <Link
              href="/transactions"
              className={`block px-3 py-2 rounded-md text-base font-medium ${
                pathname.startsWith('/transactions')
                  ? 'bg-zen-sage text-white'
                  : 'text-zen-charcoal hover:bg-zen-stone'
              }`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Transactions
            </Link>
            <Link
              href="/accounts"
              className={`block px-3 py-2 rounded-md text-base font-medium ${
                pathname.startsWith('/accounts')
                  ? 'bg-zen-sage text-white'
                  : 'text-zen-charcoal hover:bg-zen-stone'
              }`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Accounts
            </Link>
            <Link
              href="/categories"
              className={`block px-3 py-2 rounded-md text-base font-medium ${
                pathname.startsWith('/categories')
                  ? 'bg-zen-sage text-white'
                  : 'text-zen-charcoal hover:bg-zen-stone'
              }`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Categories
            </Link>
            <Link
              href="/profile"
              className={`block px-3 py-2 rounded-md text-base font-medium ${
                pathname === '/profile'
                  ? 'bg-zen-sage text-white'
                  : 'text-zen-charcoal hover:bg-zen-stone'
              }`}
              onClick={() => setMobileMenuOpen(false)}
            >
              Profile
            </Link>
            <div className="border-t border-zen-stone-dark my-2"></div>
            <Link
              href="/transactions/add"
              className="block px-3 py-2 rounded-md text-base font-medium bg-zen-sage text-white hover:bg-zen-sage-dark text-center"
              onClick={() => setMobileMenuOpen(false)}
            >
              + Add Transaction
            </Link>
            <form action="/api/auth/signout" method="post">
              <button
                type="submit"
                className="w-full text-left block px-3 py-2 rounded-md text-base font-medium text-zen-charcoal hover:bg-zen-stone"
              >
                Sign Out
              </button>
            </form>
          </div>
        </div>
      )}
    </nav>
  )
}
