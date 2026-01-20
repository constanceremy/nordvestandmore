import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { createClient } from '@/lib/supabase/server';

export async function POST() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    // Check if profile exists
    let profile = await prisma.profile.findUnique({
      where: { userId: user.id },
    });

    // Create profile if it doesn't exist
    if (!profile) {
      profile = await prisma.profile.create({
        data: {
          userId: user.id,
          onboardingCompleted: true,
        },
      });
    } else {
      // Update existing profile
      profile = await prisma.profile.update({
        where: { userId: user.id },
        data: { onboardingCompleted: true },
      });
    }

    return NextResponse.json({
      success: true,
      onboardingCompleted: profile.onboardingCompleted,
    });
  } catch (error) {
    console.error('Error completing onboarding:', error);
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 });
  }
}
