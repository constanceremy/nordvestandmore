import { createClient } from '@/lib/supabase/server'
import { redirect } from 'next/navigation'
import { prisma } from '@/lib/prisma'

export default async function RootPage() {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    redirect('/login')
  }

  // Check if user has completed onboarding
  const profile = await prisma.profile.findUnique({
    where: { userId: user.id },
  })

  if (profile && !profile.onboardingCompleted) {
    redirect('/onboarding')
  }

  redirect('/home')
}
