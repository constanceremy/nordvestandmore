import { prisma } from "@/lib/prisma";

export default async function HealthPage() {
  const accountCount = await prisma.account.count();
  const categoryCount = await prisma.category.count();
  const txCount = await prisma.transaction.count();

  return (
    <main className="p-6 space-y-2">
      <h1 className="text-xl font-semibold">Database Health Check</h1>
      <p>Accounts: {accountCount}</p>
      <p>Categories: {categoryCount}</p>
      <p>Transactions: {txCount}</p>
      <p className="text-sm text-muted-foreground mt-4">
        ✅ If you can see counts, the database connection works!
      </p>
    </main>
  );
}
