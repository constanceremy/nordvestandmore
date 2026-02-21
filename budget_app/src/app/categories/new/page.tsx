'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'

export default function NewCategoryPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    const formData = new FormData(e.currentTarget)
    const data = {
      name: formData.get('name') as string,
    }

    try {
      const response = await fetch('/api/categories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || 'Failed to create category')
      }

      router.push('/categories')
      router.refresh()
      
      toast.success('Category created!', {
        description: `${name} has been added`
      })
    } catch (err: any) {
      setError(err.message || 'Failed to create category')
      toast.error('Failed to create category', {
        description: err.message
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-zen-stone">
      <div className="max-w-2xl mx-auto p-6">
        <div className="mb-6">
          <a href="/categories" className="text-zen-sage-dark hover:text-zen-sage">
            ← Back to Categories
          </a>
        </div>

        <div className="bg-zen-stone-light rounded-xl shadow-md p-8">
          <h1 className="text-2xl font-bold mb-6 text-zen-charcoal">Create Category</h1>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-zen-charcoal mb-2">
                Category Name *
              </label>
              <input
                type="text"
                id="name"
                name="name"
                required
                placeholder="e.g., Groceries, Dining, Travel"
                className="w-full px-4 py-3 border border-zen-stone-dark rounded-lg focus:ring-2 focus:ring-zen-sage focus:border-zen-sage"
              />
              <p className="text-sm text-zen-charcoal-light mt-2">
                Common categories: Groceries, Dining, Transport, Entertainment, Utilities, Rent, Salary
              </p>
            </div>

            <div className="flex gap-4 pt-4">
              <button
                type="submit"
                disabled={loading}
                className="flex-1 py-3 px-6 bg-zen-sage text-white rounded-lg hover:bg-zen-sage-dark transition-colors shadow-md disabled:opacity-50"
              >
                {loading ? 'Creating...' : 'Create Category'}
              </button>
              <button
                type="button"
                onClick={() => router.push('/categories')}
                className="px-6 py-3 bg-zen-stone-dark text-zen-charcoal rounded-lg hover:bg-zen-sand transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
