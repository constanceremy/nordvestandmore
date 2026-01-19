# Budget App - Build Plan

## ✅ Phase 0: Setup (COMPLETED)
**Time: ~2 hours** | **Status: DONE**

- [x] Next.js + TypeScript project
- [x] Supabase database connection
- [x] Prisma ORM setup
- [x] Database schema with all tables:
  - User, Profile, Account, Category
  - Transaction, TransactionLine (for splits)
  - RecurrenceRule (for recurring transactions)
- [x] Health check page working

---

## ✅ Phase 1: MVP Core (COMPLETED)

### 1. Authentication ✅
- [x] Supabase Auth setup
- [x] Login/signup page (email + password)
- [x] Auto-create Profile on first login (with primary currency: DKK)
- [x] Protected routes (redirect if not logged in)
- [x] Simple logout button

---

### 2. Accounts ✅
- [x] "Create Account" form
  - Name, type (checking/savings/credit/cash), currency, opening balance, opening balance date
- [x] Accounts list page
  - Shows: name, current balance (calculated from transactions)
- [x] Account detail page with ledger
  - Opening balance + date visible
  - Current balance (paid only)
  - Expected balance (paid + planned)
  - Full transaction list with running balance

---

### 3. Categories ✅
- [x] "Create Category" form
- [x] Categories list
- [x] Set monthly budget targets per category
- [x] Category picker component (used in transactions)

---

### 4. Add Transaction ✅
- [x] Unified "Add Transaction" page
- [x] Transaction type picker: Expense / Income / Transfer
- [x] Core fields:
  - **paid_at** (date - always filled, even for planned)
  - **effective_for** (which month it belongs to)
  - **status** (planned / paid)
  - description (dynamically labeled: Store/Merchant for expenses, Source for income)
  - notes
- [x] **For Expense/Income:**
  - Account picker
  - Amount
  - Category picker OR "Split" mode
  - Split mode: add multiple category lines with amounts, show "remaining to allocate"
- [x] **For Transfer:**
  - From account, To account, Amount
  - Auto-creates 2 transaction lines (negative + positive)
- [x] Save to database (Transaction + TransactionLine records)
- [x] Transactions list page with filters (account, category, status)

---

### 5. Overview/Budget View ✅
- [x] Monthly overview page (renamed from "Budget")
- [x] Period selector (month picker)
- [x] Toggle: Group by **paid_at** vs **effective_for**
- [x] Category breakdown table: Budget | Planned | Paid | vs Budget
- [x] Compares monthly budget targets with actual spending

---

### 6. Edit/Update Transactions ✅
- [x] Edit transaction page (pre-filled form)
- [x] Update transaction details (status, dates, amount, categories, notes)
- [x] Quick "Mark as Paid" button for planned transactions (on transactions list & account ledger)
- [x] Delete transaction functionality
- [x] Edit buttons on transactions list and account ledger
- [x] API routes for GET/PUT/DELETE individual transactions
- [x] Full transfer editing (accounts, amounts, dates, status)
- [x] Sticky navigation bar (stays at top when scrolling)

---

### 7. Recurring Transactions ✅
- [x] "Repeat" toggle on transaction form
- [x] Frequency picker (Daily, Weekly, Monthly, Yearly)
- [x] Custom intervals (every 2 weeks, every 3 months, etc.)
- [x] Nth weekday patterns (3rd Monday, last Friday, etc.)
- [x] "Repeat until" date (optional - blank = forever)
- [x] Auto-generate future planned transactions (24 months ahead)
- [x] RecurrenceRule created and linked to transactions
- [x] Visual indicator (🔄) on transactions list showing which are recurring
- [x] Background auto-generation: Missing recurring transactions automatically created when viewing transactions
- [x] Manual refresh button to generate missing recurring transactions
- [x] Smart date detection: Only creates missing dates, doesn't duplicate existing ones

---

### 8. Quick Category Creation ✅
- [x] "+ New" button on transaction form category selector
- [x] Inline form to create category without leaving transaction page
- [x] Auto-selects newly created category

---

### 9. Search ✅
- [x] Dedicated search page with prominent search box
- [x] Text search across transaction descriptions and notes
- [x] Advanced filters:
  - Status (Paid/Planned)
  - Amount range (min/max)
  - Date range
  - Category filter
  - Account filter
- [x] Real-time results with full transaction details
- [x] Search link in main navigation (🔍 Search)
- [x] Results show recurring indicator, edit button
- [x] Case-insensitive search
- [x] Fast search with 500 result limit

---

## 🚀 Phase 2: Next Features (Priority Order)

### 📊 Home Dashboard & Visualizations (COMPLETED)
- [x] **Financial Forecast**
  - Date picker for forecast date (defaults to end of month)
  - Expected net result (total income - total expenses by forecast date)
  - Expected account balances with change indicators
  - Visual styling with gradient background
  - Real-time updates when forecast date changes
- [x] **Enhanced Dashboard Home Page**
  - "At a glance" summary cards (Net Worth, Monthly Spending, Today's Planned)
  - Current month spending vs budget progress with visual bars
  - **HERO: Prominent month-end forecast showing "Will you finish positive?"**
  - Large, eye-catching display with income, expenses, and net result
  - Clear YES/AT RISK indicator for end of month position
  - Top 3 spending categories this month with budget progress
  - Accounts overview with current balances
  - Upcoming planned expenses (next 7 days)
  - Quick action buttons (Add Transaction, View Budget, Charts, Manage Accounts, Search)
- [x] **Budget Analysis Page**
  - Separated detailed category breakdown into dedicated /budget page
  - Month picker, Group By (Effective For / Paid At), Status filter
  - Category table with Budget | Planned | Paid | vs Budget columns
  - Total summary cards
- [x] **Navigation Update**
  - Added "Budget" link to main navigation
  - Renamed "Overview" to "Home"
  - Added "📊 Charts" link to main navigation
  - Order: Home | Budget | Charts | Transactions | Accounts | Categories | Search | + Add
  
- [x] **Interactive Charts & Graphs**
  - **Flexible spending trend** (line chart with dynamic time ranges)
  - Time range selector (3/6/12/24 months) - FULLY FUNCTIONAL
  - Group by dropdown - FULLY FUNCTIONAL:
    - Total: Shows income vs paid vs planned expenses
    - By Account: Shows expenses broken down by account
    - By Category: Shows expenses broken down by category
  - Dynamic chart rendering with multiple colored lines
  - Average monthly stats for total view (income, expenses, planned, net)
  - Hover tooltips with formatted currency
  - Dedicated /charts page
  - Quick access from Home page
  
- [ ] **Insight Cards**
  - "Biggest expense this month"
  - "Most under-budget category" 🎉
  - "Trending up/down" with percentages
  - Quick stats (total transactions, avg per day, savings rate)
  - Spending velocity: "On track to spend X by end of month"

---

### 🎮 Gamification & Behavioral Psychology (AFTER CHARTS)
**Goal:** Create dopamine hits when users spend less than planned, building positive money habits

#### Core Gamification Features:
- [ ] **Daily Win/Loss Summary**
  - Show "You saved 150 DKK today! 🎉" when spending less than planned
  - Visual celebration (confetti, animations) for beating budget
  - Streak tracker: "5 days under budget!"
  
- [ ] **Achievement System**
  - Badges: "Budget Ninja" (week under budget), "Savings Superstar" (month 10% under), "Frugal February"
  - Progressive unlocks: Bronze → Silver → Gold → Platinum
  - Display badge collection on profile
  
- [ ] **Progress Bars & Visual Feedback**
  - Daily budget spent: Progress bar that turns green when under, red when over
  - Category-level visual feedback (traffic light system: 🟢 🟡 🔴)
  - Monthly scorecard: "You're 12% under budget this month!"
  
- [ ] **Positive Reinforcement Notifications**
  - Morning: "You have 350 DKK budgeted for today. You've got this! 💪"
  - Evening: "Amazing! You spent 280 DKK vs 350 planned. That's 70 DKK saved!"
  - Celebratory messages with emojis and encouraging language
  
- [ ] **Savings Visualization**
  - "Money saved this month" card on dashboard
  - Visual of money pile growing
  - Goal tracker: "1,234 DKK saved toward [vacation/emergency fund]"
  
- [ ] **Social Proof & Milestones**
  - "You're in the top 20% of budget keepers!"
  - Milestone celebrations: "You've tracked 100 transactions!"
  - "You've saved 5,000 DKK in 3 months!"
  
- [ ] **Behavioral Nudges**
  - Before adding expense: "This will put you 50 DKK over budget. Still add?"
  - Smart suggestions: "You usually spend less on groceries. Budget 400 instead of 500?"
  - Gentle reminders without shame or guilt

#### Advanced Gamification:
- [ ] Leaderboards (optional, opt-in, anonymous)
- [ ] Challenges: "No-spend weekend", "Cook-at-home week"
- [ ] Point system that converts to visual rewards
- [ ] "Budget coach" AI assistant with encouraging personality

**Why this matters:** Your friend's dopamine rush insight is GOLD. Most budget apps focus on guilt/scarcity. This focuses on winning/achievement. Game-changing differentiation.

---

### Edit Recurring Transactions
- [ ] Edit one occurrence vs edit entire series
- [ ] Update recurrence rule (frequency, end date)
- [ ] Bulk delete future occurrences

### Account Balance Reconciliation
- [ ] "Edit Balance" button on account detail page
- [ ] Adjust balance to match bank statement
- [ ] Creates a reconciliation adjustment transaction
- [ ] Shows difference between expected vs actual

### Search
- [ ] Search across: accounts, categories, transactions (description), merchants
- [ ] Filters: date range, amount range, status

### Budget Insights
- [ ] Charts (category breakdown pie chart, spending over time line chart)
- [ ] "+/- vs plan" indicator on main dashboard
- [ ] "Today" card: planned vs actual

### Multi-Currency
- [ ] Currency conversion API
- [ ] Show original + converted amounts
- [ ] Budget totals in primary currency

### Bank Integration
- [ ] Connect to aggregator (Tink/TrueLayer/Salt Edge)
- [ ] Import transactions
- [ ] Match imported → planned transactions
- [ ] Reconciliation workflow

### Notifications
- [ ] Morning: "You've planned 650 DKK today"
- [ ] Evening: "Today: planned 650, spent 720, +70"

### Account Sharing
- [ ] Invite another user to an account
- [ ] Role-based permissions (owner/editor/viewer)

### Mobile App
- [ ] React Native / Expo wrapper
- [ ] OR: Progressive Web App (PWA) for mobile browser

---

## 🧠 Key Design Principles (What Makes This Special)

### 1. Two-Date System
Every transaction has:
- **paid_at**: when the transaction happens in real life (ALWAYS filled, even for planned)
- **effective_for**: which budget month it belongs to

Example: Plane tickets paid in October for December trip
- `paid_at` = 2026-10-18
- `effective_for` = 2026-12-01
- Result: October cashflow shows it, December budget shows it

### 2. Planned-First
- Transactions can be **planned** or **paid**
- You can plan dinner for Friday (status=planned), then mark it paid when it happens
- Expected balance = opening balance + all planned + paid transactions up to date
- Budget views can show: planned only / paid only / both

### 3. Split Transactions
- One transaction can have multiple **TransactionLine** records
- Each line: account + category + amount (signed)
- Example: 600 DKK groceries split into:
  - Groceries: 450
  - Household: 100
  - Baby: 50

### 4. Transfers Are Just Two Lines
- Transfer = one transaction with 2 lines, no category
- Line 1: -5000 from Checking
- Line 2: +5000 to Savings
- They don't pollute budget reports (category = null)

### 5. Accounts Are First-Class
- Each "account" = like a tab in your Google Sheet
- Current balance: opening + paid transactions up to today
- Expected balance: opening + (paid + planned) up to date
- Every transaction line must belong to an account

---

## 📁 File Structure (Planned)

```
/src
  /app
    /auth
      /login/page.tsx
      /signup/page.tsx
    /accounts
      /page.tsx                    # List all accounts
      /[id]/page.tsx               # Account ledger
      /new/page.tsx                # Create account
    /categories
      /page.tsx                    # List + create
    /transactions
      /page.tsx                    # All transactions
      /add/page.tsx                # Add transaction (expense/income/transfer)
    /budget
      /page.tsx                    # Budget view with toggles
    /health/page.tsx               # Database health check
    /page.tsx                      # Home/dashboard
    layout.tsx
    globals.css

  /lib
    prisma.ts                      # Prisma client singleton
    supabase.ts                    # Supabase client (for auth)
    /actions                       # Server actions for mutations
      accounts.ts
      categories.ts
      transactions.ts
    /queries                       # Database queries
      accounts.ts
      transactions.ts
      budget.ts
    /utils
      balances.ts                  # Calculate running balance
      recurrence.ts                # Generate recurring transactions (later)

  /components
    /ui                            # shadcn/ui components
    /forms
      AccountForm.tsx
      CategoryForm.tsx
      TransactionForm.tsx
    /displays
      TransactionList.tsx
      AccountCard.tsx
      CategoryPicker.tsx

/prisma
  schema.prisma
  /migrations
