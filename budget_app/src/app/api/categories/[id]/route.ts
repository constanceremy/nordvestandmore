import { NextResponse } from 'next/server';
import { createClient } from '@/lib/supabase/server';
import { prisma } from '@/lib/prisma';

export async function PATCH(
  request: Request,
  context: { params: Promise<{ id: string }> }
) {
  try {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const { id } = await context.params;
    const body = await request.json();
    const { monthlyBudget } = body;

    // Verify the category belongs to the user
    const category = await prisma.category.findUnique({
      where: { id },
      include: { profile: true },
    });

    if (!category || category.profile.userId !== user.id) {
      return NextResponse.json({ error: 'Category not found' }, { status: 404 });
    }

    // Update the budget
    const updated = await prisma.category.update({
      where: { id },
      data: {
        monthlyBudget: monthlyBudget !== null ? parseFloat(monthlyBudget) : null,
      },
    });

    return NextResponse.json(updated);
  } catch (error) {
    console.error('Error updating category budget:', error);
    return NextResponse.json({ error: 'Failed to update budget' }, { status: 500 });
  }
}
