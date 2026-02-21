import { createClient } from '@/lib/supabase/server';
import { NextResponse } from 'next/server';
import { NextRequest } from 'next/server';
import { prisma } from '@/lib/prisma';

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url);
  const code = requestUrl.searchParams.get('code');

  if (code) {
    const supabase = await createClient();
    await supabase.auth.exchangeCodeForSession(code);
    
    // Check if user has completed onboarding
    const { data: { user } } = await supabase.auth.getUser();
    
    if (user) {
      try {
        // Check if profile exists and if onboarding is completed
        const profile = await prisma.profile.findUnique({
          where: { userId: user.id },
        });

        // If no profile or onboarding not completed, redirect to onboarding
        if (!profile || !profile.onboardingCompleted) {
          return NextResponse.redirect(new URL('/onboarding', request.url));
        }
      } catch (error) {
        console.error('Error checking onboarding status:', error);
        // On error, redirect to onboarding to be safe
        return NextResponse.redirect(new URL('/onboarding', request.url));
      }
    }
  }

  // Redirect to home page after email verification
  return NextResponse.redirect(new URL('/home', request.url));
}
