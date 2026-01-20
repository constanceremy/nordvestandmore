import { NextResponse } from 'next/server';
import { prisma } from '@/lib/prisma';
import { createClient } from '@/lib/supabase/server';

/**
 * This endpoint can be called to skip onboarding for existing users
 * who already have accounts and categories set up
 */
export async function POST() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    console.log('[SKIP] Starting skip onboarding for user:', user.id);
    
    // Check if profile exists
    let profile = await prisma.profile.findUnique({
      where: { userId: user.id },
    });

    console.log('[SKIP] Existing profile:', profile ? 'found' : 'not found');

    // Create profile if it doesn't exist
    if (!profile) {
      console.log('[SKIP] Creating new profile...');
      profile = await prisma.profile.create({
        data: {
          userId: user.id,
          onboardingCompleted: true,
        },
      });
      console.log('[SKIP] Profile created successfully');
    } else {
      // Update existing profile
      console.log('[SKIP] Updating existing profile...');
      profile = await prisma.profile.update({
        where: { userId: user.id },
        data: { onboardingCompleted: true },
      });
      console.log('[SKIP] Profile updated successfully');
    }

    return NextResponse.json({
      success: true,
      message: 'Onboarding skipped successfully',
      onboardingCompleted: profile.onboardingCompleted,
    });
  } catch (error) {
    console.error('Error skipping onboarding:', error);
    return NextResponse.json({ 
      error: 'Internal server error',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
}
