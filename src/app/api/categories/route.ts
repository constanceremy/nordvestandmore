import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'
import { prisma } from '@/lib/prisma'

export async function GET() {
  try {
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const profile = await prisma.profile.findFirst({
      where: { userId: user.id }
    })

    if (!profile) {
      return NextResponse.json({ error: 'Profile not found' }, { status: 404 })
    }

    const categories = await prisma.category.findMany({
      where: { 
        profileId: profile.id,
        archived: false 
      },
      orderBy: { name: 'asc' }
    })

    return NextResponse.json(categories)
  } catch (error: any) {
    console.error('Error fetching categories:', error)
    return NextResponse.json(
      { error: error.message || 'Failed to fetch categories' },
      { status: 500 }
    )
  }
}

export async function POST(request: Request) {
  try {
    const supabase = await createClient()
    const { data: { user } } = await supabase.auth.getUser()

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    const profile = await prisma.profile.findFirst({
      where: { userId: user.id }
    })

    if (!profile) {
      return NextResponse.json({ error: 'Profile not found' }, { status: 404 })
    }

    const body = await request.json()
    const { name } = body

    if (!name || name.trim().length === 0) {
      return NextResponse.json({ error: 'Category name is required' }, { status: 400 })
    }

    const existing = await prisma.category.findFirst({
      where: {
        profileId: profile.id,
        name: name.trim(),
      }
    })

    if (existing) {
      return NextResponse.json({ error: 'Category already exists' }, { status: 400 })
    }

    const category = await prisma.category.create({
      data: {
        profileId: profile.id,
        name: name.trim(),
      }
    })

    return NextResponse.json(category)
  } catch (error: any) {
    console.error('Error creating category:', error)
    return NextResponse.json(
      { error: error.message || 'Failed to create category' },
      { status: 500 }
    )
  }
}
