'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

type OnboardingStep = 'welcome' | 'accounts' | 'categories' | 'first-transaction' | 'complete';

interface Account {
  name: string;
  type: string;
  currency: string;
  openingBalance: string;
}

interface Category {
  name: string;
  monthlyBudget: string;
}

export default function OnboardingPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState<OnboardingStep>('welcome');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Account step state
  const [accounts, setAccounts] = useState<Account[]>([
    { name: '', type: 'CHECKING', currency: 'DKK', openingBalance: '0' },
  ]);

  // Category step state
  const [categories, setCategories] = useState<Category[]>([
    { name: '', monthlyBudget: '' },
    { name: '', monthlyBudget: '' },
    { name: '', monthlyBudget: '' },
  ]);

  // First transaction state
  const [skipTransaction, setSkipTransaction] = useState(false);
  const [transaction, setTransaction] = useState({
    kind: 'EXPENSE' as 'EXPENSE' | 'INCOME',
    description: '',
    amount: '',
    accountId: '',
    categoryId: '',
    paidAt: new Date().toISOString().split('T')[0],
  });

  const [createdAccounts, setCreatedAccounts] = useState<any[]>([]);
  const [createdCategories, setCreatedCategories] = useState<any[]>([]);

  const stepProgress = {
    welcome: 0,
    accounts: 25,
    categories: 50,
    'first-transaction': 75,
    complete: 100,
  };

  const handleAccountSubmit = async () => {
    setIsSubmitting(true);
    try {
      // Filter out empty accounts
      const validAccounts = accounts.filter((acc) => acc.name.trim() !== '');

      // Allow skipping if no accounts provided
      if (validAccounts.length === 0) {
        setCurrentStep('categories');
        setIsSubmitting(false);
        return;
      }

      const created = [];
      for (const acc of validAccounts) {
        const res = await fetch('/api/accounts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: acc.name,
            type: acc.type,
            currency: acc.currency,
            openingBalance: parseFloat(acc.openingBalance) || 0,
          }),
        });

        if (!res.ok) throw new Error('Failed to create account');
        const data = await res.json();
        created.push(data);
      }

      setCreatedAccounts(created);
      setCurrentStep('categories');
    } catch (error) {
      console.error('Error creating accounts:', error);
      alert('Failed to create accounts. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCategorySubmit = async () => {
    setIsSubmitting(true);
    try {
      // Filter out empty categories
      const validCategories = categories.filter((cat) => cat.name.trim() !== '');

      // Allow skipping if no categories provided
      if (validCategories.length === 0) {
        setCurrentStep('first-transaction');
        setIsSubmitting(false);
        return;
      }

      const created = [];
      for (const cat of validCategories) {
        const res = await fetch('/api/categories', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: cat.name,
            monthlyBudget: cat.monthlyBudget ? parseFloat(cat.monthlyBudget) : null,
          }),
        });

        if (!res.ok) throw new Error('Failed to create category');
        const data = await res.json();
        created.push(data);
      }

      setCreatedCategories(created);
      setCurrentStep('first-transaction');
    } catch (error) {
      console.error('Error creating categories:', error);
      alert('Failed to create categories. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleTransactionSubmit = async () => {
    if (skipTransaction) {
      await completeOnboarding();
      return;
    }

    if (!transaction.description || !transaction.amount || !transaction.accountId) {
      alert('Please fill in all required fields');
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await fetch('/api/transactions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          kind: transaction.kind,
          status: 'PAID',
          description: transaction.description,
          paidAt: new Date(transaction.paidAt).toISOString(),
          effectiveForMonth: new Date(transaction.paidAt).toISOString(),
          lines: [
            {
              accountId: transaction.accountId,
              categoryId: transaction.categoryId || null,
              amount: parseFloat(transaction.amount) * (transaction.kind === 'EXPENSE' ? -1 : 1),
              currency: createdAccounts.find((a) => a.id === transaction.accountId)?.currency || 'DKK',
            },
          ],
        }),
      });

      if (!res.ok) throw new Error('Failed to create transaction');

      await completeOnboarding();
    } catch (error) {
      console.error('Error creating transaction:', error);
      alert('Failed to create transaction. Please try again.');
      setIsSubmitting(false);
    }
  };

  const completeOnboarding = async () => {
    try {
      await fetch('/api/onboarding/complete', {
        method: 'POST',
      });
      setCurrentStep('complete');
      setTimeout(() => {
        router.push('/home');
      }, 2000);
    } catch (error) {
      console.error('Error completing onboarding:', error);
      // Even if API fails, just redirect to home
      router.push('/home');
    }
  };

  const skipOnboarding = async () => {
    // Just mark as complete and redirect to home
    setIsSubmitting(true);
    try {
      await fetch('/api/onboarding/complete', {
        method: 'POST',
      });
      router.push('/home');
    } catch (error) {
      console.error('Error skipping onboarding:', error);
      // Even if API fails, just redirect to home
      router.push('/home');
    }
  };

  const addAccount = () => {
    setAccounts([...accounts, { name: '', type: 'CHECKING', currency: 'DKK', openingBalance: '0' }]);
  };

  const updateAccount = (index: number, field: keyof Account, value: string) => {
    const updated = [...accounts];
    updated[index][field] = value;
    setAccounts(updated);
  };

  const removeAccount = (index: number) => {
    if (accounts.length > 1) {
      setAccounts(accounts.filter((_, i) => i !== index));
    }
  };

  const addCategory = () => {
    setCategories([...categories, { name: '', monthlyBudget: '' }]);
  };

  const updateCategory = (index: number, field: keyof Category, value: string) => {
    const updated = [...categories];
    updated[index][field] = value;
    setCategories(updated);
  };

  const removeCategory = (index: number) => {
    if (categories.length > 1) {
      setCategories(categories.filter((_, i) => i !== index));
    }
  };

  return (
    <div className="min-h-screen bg-zen-stone flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        {/* Skip button - only show before complete step */}
        {currentStep !== 'complete' && (
          <div className="text-right mb-4">
            <button
              onClick={skipOnboarding}
              disabled={isSubmitting}
              className="text-sm text-zen-charcoal/60 hover:text-zen-charcoal underline disabled:opacity-50"
            >
              Skip setup for now
            </button>
          </div>
        )}

        {/* Progress Bar */}
        <div className="mb-8">
          <div className="h-2 bg-zen-stone-light rounded-full overflow-hidden">
            <div
              className="h-full bg-zen-sage transition-all duration-500"
              style={{ width: `${stepProgress[currentStep]}%` }}
            />
          </div>
          <p className="text-sm text-zen-charcoal/60 mt-2 text-center">
            Step {Object.keys(stepProgress).indexOf(currentStep) + 1} of {Object.keys(stepProgress).length}
          </p>
        </div>

        {/* Welcome Step */}
        {currentStep === 'welcome' && (
          <div className="bg-white rounded-2xl shadow-lg p-8 md:p-12">
            <h1 className="text-4xl font-bold text-zen-charcoal mb-4">Welcome to Balance! 🌿</h1>
            <p className="text-lg text-zen-charcoal/70 mb-6">
              Your peaceful path to financial clarity. Let's get you set up in just a few steps.
            </p>

            <div className="space-y-4 mb-8">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-zen-sage/20 flex items-center justify-center flex-shrink-0 mt-1">
                  <span className="text-zen-sage-dark font-bold">1</span>
                </div>
                <div>
                  <h3 className="font-semibold text-zen-charcoal">Create Your Accounts</h3>
                  <p className="text-sm text-zen-charcoal/60">
                    Add your bank accounts, credit cards, or cash accounts
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-zen-sage/20 flex items-center justify-center flex-shrink-0 mt-1">
                  <span className="text-zen-sage-dark font-bold">2</span>
                </div>
                <div>
                  <h3 className="font-semibold text-zen-charcoal">Set Up Categories & Budgets</h3>
                  <p className="text-sm text-zen-charcoal/60">
                    Organize your spending and set monthly budget goals
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-zen-sage/20 flex items-center justify-center flex-shrink-0 mt-1">
                  <span className="text-zen-sage-dark font-bold">3</span>
                </div>
                <div>
                  <h3 className="font-semibold text-zen-charcoal">Add Your First Transaction</h3>
                  <p className="text-sm text-zen-charcoal/60">Learn how to track your expenses (optional)</p>
                </div>
              </div>
            </div>

            <button
              onClick={() => setCurrentStep('accounts')}
              className="w-full py-3 px-6 bg-zen-sage text-white rounded-xl font-medium hover:bg-zen-sage-dark transition-colors"
            >
              Let's Get Started →
            </button>
          </div>
        )}

        {/* Accounts Step */}
        {currentStep === 'accounts' && (
          <div className="bg-white rounded-2xl shadow-lg p-8">
            <h2 className="text-3xl font-bold text-zen-charcoal mb-2">Create Your Accounts</h2>
            <p className="text-zen-charcoal/60 mb-6">
              Add at least one account to track your finances. You can always add more later!
            </p>

            <div className="space-y-4 mb-6">
              {accounts.map((account, index) => (
                <div key={index} className="border border-zen-stone-light rounded-xl p-4">
                  <div className="flex justify-between items-center mb-3">
                    <span className="text-sm font-medium text-zen-charcoal">Account {index + 1}</span>
                    {accounts.length > 1 && (
                      <button
                        onClick={() => removeAccount(index)}
                        className="text-red-500 text-sm hover:text-red-600"
                      >
                        Remove
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <input
                      type="text"
                      placeholder="Account name (e.g., Checking)"
                      value={account.name}
                      onChange={(e) => updateAccount(index, 'name', e.target.value)}
                      className="px-3 py-2 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                    />

                    <select
                      value={account.type}
                      onChange={(e) => updateAccount(index, 'type', e.target.value)}
                      className="px-3 py-2 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                    >
                      <option value="CHECKING">Checking</option>
                      <option value="SAVINGS">Savings</option>
                      <option value="CREDIT_CARD">Credit Card</option>
                      <option value="CASH">Cash</option>
                    </select>

                    <select
                      value={account.currency}
                      onChange={(e) => updateAccount(index, 'currency', e.target.value)}
                      className="px-3 py-2 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                    >
                      <option value="DKK">DKK (kr)</option>
                      <option value="USD">USD ($)</option>
                      <option value="EUR">EUR (€)</option>
                      <option value="GBP">GBP (£)</option>
                    </select>

                    <input
                      type="number"
                      step="0.01"
                      placeholder="Opening balance"
                      value={account.openingBalance}
                      onChange={(e) => updateAccount(index, 'openingBalance', e.target.value)}
                      className="px-3 py-2 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                    />
                  </div>
                </div>
              ))}
            </div>

            <button
              onClick={addAccount}
              className="w-full py-2 border-2 border-dashed border-zen-sage text-zen-sage-dark rounded-xl font-medium hover:bg-zen-sage/5 transition-colors mb-6"
            >
              + Add Another Account
            </button>

            <div className="flex gap-3">
              <button
                onClick={() => setCurrentStep('welcome')}
                className="flex-1 py-3 px-6 border border-zen-stone-light text-zen-charcoal rounded-xl font-medium hover:bg-zen-stone-light transition-colors"
                disabled={isSubmitting}
              >
                ← Back
              </button>
              <button
                onClick={() => setCurrentStep('categories')}
                className="px-6 py-3 text-zen-charcoal/60 hover:text-zen-charcoal transition-colors"
                disabled={isSubmitting}
              >
                Skip →
              </button>
              <button
                onClick={handleAccountSubmit}
                disabled={isSubmitting}
                className="flex-1 py-3 px-6 bg-zen-sage text-white rounded-xl font-medium hover:bg-zen-sage-dark transition-colors disabled:opacity-50"
              >
                {isSubmitting ? 'Creating...' : 'Continue →'}
              </button>
            </div>
          </div>
        )}

        {/* Categories Step */}
        {currentStep === 'categories' && (
          <div className="bg-white rounded-2xl shadow-lg p-8">
            <h2 className="text-3xl font-bold text-zen-charcoal mb-2">Set Up Categories</h2>
            <p className="text-zen-charcoal/60 mb-6">
              Create categories to organize your spending. Set monthly budgets to track your goals!
            </p>

            <div className="space-y-4 mb-6">
              {categories.map((category, index) => (
                <div key={index} className="border border-zen-stone-light rounded-xl p-4">
                  <div className="flex justify-between items-center mb-3">
                    <span className="text-sm font-medium text-zen-charcoal">Category {index + 1}</span>
                    {categories.length > 1 && (
                      <button
                        onClick={() => removeCategory(index)}
                        className="text-red-500 text-sm hover:text-red-600"
                      >
                        Remove
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <input
                      type="text"
                      placeholder="Category name (e.g., Groceries)"
                      value={category.name}
                      onChange={(e) => updateCategory(index, 'name', e.target.value)}
                      className="px-3 py-2 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                    />

                    <input
                      type="number"
                      step="0.01"
                      placeholder="Monthly budget (optional)"
                      value={category.monthlyBudget}
                      onChange={(e) => updateCategory(index, 'monthlyBudget', e.target.value)}
                      className="px-3 py-2 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                    />
                  </div>
                </div>
              ))}
            </div>

            <button
              onClick={addCategory}
              className="w-full py-2 border-2 border-dashed border-zen-sage text-zen-sage-dark rounded-xl font-medium hover:bg-zen-sage/5 transition-colors mb-6"
            >
              + Add Another Category
            </button>

            <div className="bg-zen-stone-light rounded-lg p-4 mb-6">
              <p className="text-sm text-zen-charcoal/70">
                💡 <strong>Tip:</strong> Common categories include Groceries, Rent, Utilities, Entertainment,
                Transportation, and Dining Out.
              </p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setCurrentStep('accounts')}
                className="flex-1 py-3 px-6 border border-zen-stone-light text-zen-charcoal rounded-xl font-medium hover:bg-zen-stone-light transition-colors"
                disabled={isSubmitting}
              >
                ← Back
              </button>
              <button
                onClick={() => setCurrentStep('first-transaction')}
                className="px-6 py-3 text-zen-charcoal/60 hover:text-zen-charcoal transition-colors"
                disabled={isSubmitting}
              >
                Skip →
              </button>
              <button
                onClick={handleCategorySubmit}
                disabled={isSubmitting}
                className="flex-1 py-3 px-6 bg-zen-sage text-white rounded-xl font-medium hover:bg-zen-sage-dark transition-colors disabled:opacity-50"
              >
                {isSubmitting ? 'Creating...' : 'Continue →'}
              </button>
            </div>
          </div>
        )}

        {/* First Transaction Step */}
        {currentStep === 'first-transaction' && (
          <div className="bg-white rounded-2xl shadow-lg p-8">
            <h2 className="text-3xl font-bold text-zen-charcoal mb-2">Add Your First Transaction</h2>
            <p className="text-zen-charcoal/60 mb-6">
              Let's add a transaction to see how it all works! You can skip this if you prefer.
            </p>

            {!skipTransaction ? (
              <>
                <div className="space-y-4 mb-6">
                  {/* Transaction Type */}
                  <div>
                    <label className="block text-sm font-medium text-zen-charcoal mb-2">Type</label>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setTransaction({ ...transaction, kind: 'EXPENSE' })}
                        className={`flex-1 py-2 rounded-lg font-medium transition-colors ${
                          transaction.kind === 'EXPENSE'
                            ? 'bg-zen-sage text-white'
                            : 'bg-zen-stone-light text-zen-charcoal hover:bg-zen-stone'
                        }`}
                      >
                        Expense
                      </button>
                      <button
                        onClick={() => setTransaction({ ...transaction, kind: 'INCOME' })}
                        className={`flex-1 py-2 rounded-lg font-medium transition-colors ${
                          transaction.kind === 'INCOME'
                            ? 'bg-zen-sage text-white'
                            : 'bg-zen-stone-light text-zen-charcoal hover:bg-zen-stone'
                        }`}
                      >
                        Income
                      </button>
                    </div>
                  </div>

                  {/* Description / Store / Source */}
                  <div>
                    <label className="block text-sm font-medium text-zen-charcoal mb-2">
                      {transaction.kind === 'EXPENSE' && 'Store / Merchant'}
                      {transaction.kind === 'INCOME' && 'Source'}
                      {' '}<span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      placeholder={
                        transaction.kind === 'EXPENSE' 
                          ? 'e.g., Netto, Føtex' 
                          : 'e.g., Salary, Freelance'
                      }
                      value={transaction.description}
                      onChange={(e) => setTransaction({ ...transaction, description: e.target.value })}
                      className="w-full px-3 py-2 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                    />
                  </div>

                  {/* Account & Amount */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-zen-charcoal mb-2">
                        Account <span className="text-red-500">*</span>
                      </label>
                      <select
                        value={transaction.accountId}
                        onChange={(e) => setTransaction({ ...transaction, accountId: e.target.value })}
                        className="w-full px-3 py-2 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                      >
                        <option value="">Select account</option>
                        {createdAccounts.map((acc) => (
                          <option key={acc.id} value={acc.id}>
                            {acc.name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-zen-charcoal mb-2">
                        Amount <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        placeholder="0.00"
                        value={transaction.amount}
                        onChange={(e) => setTransaction({ ...transaction, amount: e.target.value })}
                        className="w-full px-3 py-2 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                      />
                    </div>
                  </div>

                  {/* Category */}
                  <div>
                    <label className="block text-sm font-medium text-zen-charcoal mb-2">
                      Category {transaction.kind === 'EXPENSE' && '(optional)'}
                    </label>
                    <select
                      value={transaction.categoryId}
                      onChange={(e) => setTransaction({ ...transaction, categoryId: e.target.value })}
                      className="w-full px-3 py-2 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                    >
                      <option value="">Uncategorized</option>
                      {createdCategories.map((cat) => (
                        <option key={cat.id} value={cat.id}>
                          {cat.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Date */}
                  <div>
                    <label className="block text-sm font-medium text-zen-charcoal mb-2">Date</label>
                    <input
                      type="date"
                      value={transaction.paidAt}
                      onChange={(e) => setTransaction({ ...transaction, paidAt: e.target.value })}
                      className="w-full px-3 py-2 border border-zen-stone-light rounded-lg focus:outline-none focus:ring-2 focus:ring-zen-sage"
                    />
                  </div>
                </div>
              </>
            ) : (
              <div className="bg-zen-stone-light rounded-lg p-6 mb-6 text-center">
                <p className="text-zen-charcoal/70">
                  No problem! You can add transactions later from the main app.
                </p>
              </div>
            )}

            <button
              onClick={() => setSkipTransaction(!skipTransaction)}
              className="w-full py-2 text-zen-charcoal/60 hover:text-zen-charcoal text-sm mb-6"
            >
              {skipTransaction ? '← Go back to add a transaction' : 'Skip this step →'}
            </button>

            <div className="flex gap-3">
              <button
                onClick={() => setCurrentStep('categories')}
                className="flex-1 py-3 px-6 border border-zen-stone-light text-zen-charcoal rounded-xl font-medium hover:bg-zen-stone-light transition-colors"
                disabled={isSubmitting}
              >
                ← Back
              </button>
              <button
                onClick={handleTransactionSubmit}
                disabled={isSubmitting}
                className="flex-1 py-3 px-6 bg-zen-sage text-white rounded-xl font-medium hover:bg-zen-sage-dark transition-colors disabled:opacity-50"
              >
                {isSubmitting ? 'Finishing...' : 'Complete Setup →'}
              </button>
            </div>
          </div>
        )}

        {/* Complete Step */}
        {currentStep === 'complete' && (
          <div className="bg-white rounded-2xl shadow-lg p-8 md:p-12 text-center">
            <div className="w-20 h-20 bg-zen-sage/20 rounded-full flex items-center justify-center mx-auto mb-6">
              <span className="text-4xl">✨</span>
            </div>
            <h2 className="text-3xl font-bold text-zen-charcoal mb-4">You're All Set!</h2>
            <p className="text-lg text-zen-charcoal/70 mb-6">
              Welcome to your financial zen garden. Let's explore your dashboard!
            </p>
            <div className="animate-pulse text-zen-sage-dark">Redirecting to home...</div>
          </div>
        )}
      </div>
    </div>
  );
}
