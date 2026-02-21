import { NextResponse } from 'next/server';
import { createClient } from '@/lib/supabase/server';
import { prisma } from '@/lib/prisma';

// GET profile
export async function GET() {
  try {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const profile = await prisma.profile.findUnique({
      where: { userId: user.id },
      select: {
        id: true,
        primaryCurrency: true,
        timezone: true,
        onboardingCompleted: true,
      },
    });

    if (!profile) {
      return NextResponse.json({ error: 'Profile not found' }, { status: 404 });
    }

    return NextResponse.json(profile);
  } catch (error) {
    console.error('Error fetching profile:', error);
    return NextResponse.json({ error: 'Failed to fetch profile' }, { status: 500 });
  }
}

// PUT (update) profile
export async function PUT(request: Request) {
  try {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const body = await request.json();
    const { primaryCurrency, timezone } = body;

    const profile = await prisma.profile.update({
      where: { userId: user.id },
      data: {
        primaryCurrency,
        timezone,
      },
    });

    return NextResponse.json(profile);
  } catch (error) {
    console.error('Error updating profile:', error);
    return NextResponse.json({ error: 'Failed to update profile' }, { status: 500 });
  }
}

// DELETE account (nuclear option)
export async function DELETE() {
  try {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const profile = await prisma.profile.findUnique({
      where: { userId: user.id },
    });

    if (!profile) {
      return NextResponse.json({ error: 'Profile not found' }, { status: 404 });
    }

    // Delete in correct order to avoid foreign key constraints
    // 1. Delete transaction lines (has FK to transactions, accounts, categories)
    await prisma.transactionLine.deleteMany({
      where: {
        transaction: {
          profileId: profile.id,
        },
      },
    });

    // 2. Delete transactions
    await prisma.transaction.deleteMany({
      where: { profileId: profile.id },
    });

    // 3. Delete recurrence rules
    await prisma.recurrenceRule.deleteMany({
      where: { profileId: profile.id },
    });

    // 4. Delete categories
    await prisma.category.deleteMany({
      where: { profileId: profile.id },
    });

    // 5. Delete accounts
    await prisma.account.deleteMany({
      where: { profileId: profile.id },
    });

    // 6. Finally delete the profile
    await prisma.profile.delete({
      where: { id: profile.id },
    });

    // Note: We don't delete from Supabase Auth here
    // That would require service_role key
    // The user can still exist in auth but won't be able to login
    // since the profile check will fail

    return NextResponse.json({ success: true, message: 'Account deleted successfully' });
  } catch (error: any) {
    console.error('Error deleting account:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to delete account' },
      { status: 500 }
    );
  }
}
