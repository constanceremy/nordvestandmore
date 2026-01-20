'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import LoadingSpinner from '@/components/LoadingSpinner'

type Category = {
  id: string
  name: string
  monthlyBudget: number | null
}

export default function CategoriesPage() {
  const router = useRouter()
  const [categories, setCategories] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchCategories()
  }, [])

  const fetchCategories = async () => {
    try {
      const res = await fetch('/api/categories')
      if (!res.ok) {
        if (res.status === 401) {
          router.push('/login')
          return
        }
        // If it's just an error (like no categories), set empty array
        setCategories([])
        setLoading(false)
        return
      }
      const data = await res.json()
      setCategories(data || [])
    } catch (error) {
      // Silent fail - just show empty state
      setCategories([])
    } finally {
      setLoading(false)
    }
  }

  const handleUpdateBudget = async (categoryId: string, monthlyBudget: string) => {
    try {
      const res = await fetch(`/api/categories/${categoryId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          monthlyBudget: monthlyBudget ? parseFloat(monthlyBudget) : null 
        })
      })

      if (!res.ok) throw new Error('Failed to update budget')

      toast.success('Budget updated!', {
        description: 'Category budget has been saved'
      })
      
      fetchCategories()
    } catch (error) {
      console.error('Error updating budget:', error)
      toast.error('Failed to update budget')
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-zen-stone flex items-center justify-center">
        <LoadingSpinner size="lg" text="Loading categories..." />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-zen-stone">
      <div className="max-w-6xl mx-auto p-6">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-zen-charcoal">Categories</h1>
          <a
            href="/categories/new"
            className="px-4 py-2 bg-zen-sage text-white rounded-lg hover:bg-zen-sage-dark transition-colors shadow-md"
          >
            + New Category
          </a>
        </div>

        {categories.length === 0 ? (
          <div className="bg-zen-stone-light rounded-xl shadow-md p-12 text-center">
            <div className="text-6xl mb-4">📁</div>
            <h3 className="text-xl font-semibold text-zen-charcoal mb-3">No Categories Yet</h3>
            <p className="text-zen-charcoal/60 mb-6 text-sm max-w-md mx-auto">
              Create categories to organize your spending and set monthly budget goals.
            </p>
            <a
              href="/categories/new"
              className="inline-block px-6 py-3 bg-zen-sage text-white rounded-lg hover:bg-zen-sage-dark transition-colors shadow-md"
            >
              + Create Your First Category
            </a>
          </div>
        ) : (
          <div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-6">
              {categories.map((category) => (
                <div
                  key={category.id}
                  className="bg-gradient-to-br from-zen-stone-light to-white rounded-xl shadow-md hover:shadow-xl transition-all duration-300 p-6 border border-zen-stone-dark"
                >
                  <h3 className="font-bold text-xl text-zen-charcoal mb-4">{category.name}</h3>
                  
                  <form
                    onSubmit={(e) => {
                      e.preventDefault()
                      const formData = new FormData(e.currentTarget)
                      const budget = formData.get('monthlyBudget') as string
                      handleUpdateBudget(category.id, budget)
                    }}
                    className="space-y-3"
                  >
                    <div>
                      <label className="block text-sm text-zen-charcoal-light mb-2">
                        Monthly Budget Target
                      </label>
                      <input
                        type="number"
                        name="monthlyBudget"
                        step="0.01"
                        placeholder="0.00"
                        defaultValue={category.monthlyBudget ? Number(category.monthlyBudget).toString() : ''}
                        className="w-full px-4 py-2 border border-zen-stone-dark rounded-lg focus:ring-2 focus:ring-zen-sage focus:border-zen-sage"
                      />
                    </div>
                    
                    {category.monthlyBudget && (
                      <div className="bg-zen-sage-light rounded-lg p-3">
                        <p className="text-sm text-zen-charcoal">
                          Current: <span className="font-semibold">{Number(category.monthlyBudget).toFixed(2)} DKK</span>
                        </p>
                      </div>
                    )}
                    
                    <button
                      type="submit"
                      className="w-full px-4 py-2 bg-zen-sage text-white rounded-lg hover:bg-zen-sage-dark transition-colors shadow-md"
                    >
                      Update Budget
                    </button>
                  </form>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
