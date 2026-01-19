import { createClient } from '@/lib/supabase/server'
import { redirect } from 'next/navigation'
import { prisma } from '@/lib/prisma'

async function getProfile(userId: string) {
  return await prisma.profile.findFirst({
    where: { userId }
  })
}

async function updateCategoryBudget(formData: FormData) {
  'use server'
  
  const categoryId = formData.get('categoryId') as string
  const monthlyBudget = formData.get('monthlyBudget') as string
  
  await prisma.category.update({
    where: { id: categoryId },
    data: {
      monthlyBudget: monthlyBudget ? parseFloat(monthlyBudget) : null
    }
  })
  
  redirect('/categories')
}

export default async function CategoriesPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    redirect('/login')
  }

  const profile = await getProfile(user.id)
  if (!profile) {
    redirect('/login')
  }

  const categories = await prisma.category.findMany({
    where: { 
      profileId: profile.id,
      archived: false 
    },
    orderBy: { name: 'asc' }
  })

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto p-6">
        <h1 className="text-3xl font-bold mb-6">Categories</h1>

        {categories.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <p className="text-gray-600 mb-4">No categories yet. Create some categories for your expenses!</p>
            <a
              href="/categories/new"
              className="inline-block px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Create Category
            </a>
          </div>
        ) : (
          <div>
            <div className="bg-white rounded-lg shadow mb-4">
              <div className="grid grid-cols-1 divide-y">
                {categories.map((category) => (
                  <div key={category.id} className="p-4">
                    <div className="flex justify-between items-center">
                      <div className="flex-1">
                        <h3 className="font-semibold text-lg">{category.name}</h3>
                        {category.monthlyBudget && (
                          <p className="text-sm text-gray-600">
                            Monthly Budget: {Number(category.monthlyBudget).toFixed(2)} DKK
                          </p>
                        )}
                      </div>
                      <form action={updateCategoryBudget} className="flex gap-2 items-center">
                        <input type="hidden" name="categoryId" value={category.id} />
                        <input
                          type="number"
                          name="monthlyBudget"
                          step="0.01"
                          placeholder="Monthly budget"
                          defaultValue={category.monthlyBudget ? Number(category.monthlyBudget).toString() : ''}
                          className="w-32 px-3 py-1 border border-gray-300 rounded-md text-sm"
                        />
                        <button
                          type="submit"
                          className="px-3 py-1 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700"
                        >
                          Set
                        </button>
                      </form>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <a
              href="/categories/new"
              className="block w-full py-3 text-center border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-gray-400 hover:text-gray-700"
            >
              + Add Category
            </a>
          </div>
        )}
      </div>
    </div>
  )
}
