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

    const accounts = await prisma.account.findMany({
      where: { 
        profileId: profile.id,
        archived: false 
      },
      orderBy: { createdAt: 'asc' }
    })

    return NextResponse.json(accounts)
  } catch (error: any) {
    console.error('Error fetching accounts:', error)
    return NextResponse.json(
      { error: error.message || 'Failed to fetch accounts' },
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
    const { name, type, currency, openingBalance } = body

    const account = await prisma.account.create({
      data: {
        profileId: profile.id,
        name,
        type,
        currency,
        openingBalance: openingBalance || 0,
        openingBalanceDate: new Date(),
      }
    })

    return NextResponse.json(account)
  } catch (error: any) {
    console.error('Error creating account:', error)
    return NextResponse.json(
      { error: error.message || 'Failed to create account' },
      { status: 500 }
    )
  }
}
