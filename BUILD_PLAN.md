# Budget App - Build Plan

---

## ✅ COMPLETED FEATURES

### ✅ Phase 0: Setup
**Time: ~2 hours** | **Status: DONE**

- ✅ Next.js + TypeScript project
- ✅ Supabase database connection
- ✅ Prisma ORM setup
- ✅ Database schema with all tables:
  - User, Profile, Account, Category
  - Transaction, TransactionLine (for splits)
  - RecurrenceRule (for recurring transactions)
- ✅ Health check page working

---

### ✅ Authentication & Security 🔐
- ✅ Supabase Auth setup
- ✅ Login/signup page (email + password) with Nordic Zen styling
- ✅ Auto-create Profile on first login (with primary currency: DKK)
- ✅ Protected routes (redirect if not logged in)
- ✅ Simple logout button
- ✅ **Password Security**
  - Password strength indicator (weak/medium/strong)
  - Client-side validation (8+ chars, uppercase, lowercase, numbers, symbols)
  - Visual feedback with progress bar
  - Clear requirements shown to users
  - Supabase bcrypt hashing on server
- ✅ **Password Reset Flow**
  - "Forgot Password" page with email submission
  - Reset link sent via email (expires in 1 hour)
  - "Reset Password" page with strength validation
  - Success confirmation and auto-redirect to login
- ✅ **Email Verification**
  - Verification email sent on signup
  - User cannot login until email verified
  - Auth callback route for confirmation
  - Clear messaging to users
- ✅ **Security Audit Complete**
  - All API routes check authentication ✓
  - Data isolation by profileId ✓
  - Ownership verification before mutations ✓
  - No SQL injection vulnerabilities ✓
  - No XSS vulnerabilities ✓
  - Proper error handling ✓
  - See `SECURITY_AUDIT.md` for full report
- ✅ **Onboarding Flow** 🎓
  - Multi-step wizard for new users
  - Step 1: Welcome screen with overview
  - Step 2: Create accounts (checking, savings, credit card, cash)
  - Step 3: Set up categories with monthly budgets
  - Step 4: Add first transaction (optional, can skip)
  - Progress bar showing completion status
  - Skip button for users who want to explore first
  - Database field to track onboarding completion
  - Automatic redirect to onboarding for new users
  - Existing users automatically marked as completed

---

### ✅ Accounts
- ✅ "Create Account" form (name, type, currency, opening balance, opening balance date)
- ✅ Accounts list page showing name and current balance (calculated from transactions)
- ✅ Account detail page with ledger showing:
  - Opening balance + date visible
  - Current balance (paid only)
  - Expected balance (paid + planned)
  - Full transaction list with running balance
- ✅ Edit account (name, currency)
- ✅ Beautiful card-based layout with Nordic Zen styling
- ✅ Edit and Reconcile buttons on each account card
- ✅ Account Balance Reconciliation
  - "Reconcile" button on account cards and detail page
  - Form to enter actual balance from bank statement
  - Calculates difference automatically
  - Creates adjustment transaction (preserves history)
  - Visual feedback (green/red for positive/negative adjustments)
  - Shows current calculated balance vs new balance

---

### ✅ Categories
- ✅ "Create Category" form
- ✅ Categories list
- ✅ Set monthly budget targets per category
- ✅ Category picker component (used in transactions)
- ✅ Quick Category Creation from transaction form
  - "+ New" button on transaction form category selector
  - Inline form to create category without leaving transaction page
  - Auto-selects newly created category

---

### ✅ Transactions
- ✅ Unified "Add Transaction" page
- ✅ Transaction type picker: Expense / Income / Transfer
- ✅ Core fields:
  - **paid_at** (date - always filled, even for planned)
  - **effective_for** (which month it belongs to)
  - **status** (planned / paid)
  - description (dynamically labeled: Store/Merchant for expenses, Source for income)
  - notes (collapsible)
- ✅ **For Expense/Income:**
  - Account picker
  - Amount
  - Category picker OR "Split" mode
  - Split mode: add multiple category lines with amounts, show "remaining to allocate"
- ✅ **For Transfer:**
  - From account, To account, Amount
  - Auto-creates 2 transaction lines (negative + positive)
- ✅ Save to database (Transaction + TransactionLine records)
- ✅ Transactions list page with filters (account, category, status)
- ✅ **Split Transaction UI**
  - Expandable rows showing split breakdown
  - "[Split: X]" badge for multi-category transactions
  - Click to expand and see individual category amounts
  - Visual tree structure with └─ connector
  - "Multi category" label when collapsed
  - Transfers correctly show single amount (not doubled)
- ✅ Edit transaction page (pre-filled form)
- ✅ Update transaction details (status, dates, amount, categories, notes)
- ✅ Quick "Mark as Paid" button for planned transactions (on transactions list & account ledger)
- ✅ Delete transaction functionality
- ✅ Edit buttons on transactions list and account ledger
- ✅ API routes for GET/PUT/DELETE individual transactions
- ✅ Full transfer editing (accounts, amounts, dates, status)
- ✅ Batch delete transactions
  - "Select to Delete" mode with checkboxes
  - Shift-click range selection
  - Confirmation modal before deletion
- ✅ Date formatting
  - Paid At: "Jan 1st, 2026"
  - Effective For: "Jan 2026"
- ✅ Compact transaction form with collapsible sections
  - Full labels for Expense/Income/Transfer buttons
  - Clear date labels ("Paid At" / "Effective For")
  - Store/Merchant + Amount on same line
  - Collapsible notes and recurring sections
  - Branded Paid/Planned status buttons

---

### ✅ Recurring Transactions
- ✅ "Repeat" toggle on transaction form (collapsible section)
- ✅ Frequency picker (Daily, Weekly, Monthly, Yearly)
- ✅ Custom intervals (every 2 weeks, every 3 months, etc.)
- ✅ Nth weekday patterns (3rd Monday, last Friday, etc.)
- ✅ "Repeat until" date (optional - blank = forever)
- ✅ Auto-generate future planned transactions (24 months ahead)
- ✅ RecurrenceRule created and linked to transactions
- ✅ Visual indicator (🔄) on transactions list showing which are recurring
- ✅ Background auto-generation: Missing recurring transactions automatically created when viewing transactions
- ✅ Manual refresh button to generate missing recurring transactions
- ✅ Smart date detection: Only creates missing dates, doesn't duplicate existing ones
- ✅ Correct effectiveForMonth calculation preserving offset from paidAt
- ✅ Confirmation modal showing preview of generated transactions (dates, effective dates, amounts)

---

### ✅ Search
- ✅ Dedicated search page with prominent search box
- ✅ Text search across transaction descriptions and notes
- ✅ Advanced filters:
  - Status (Paid/Planned)
  - Amount range (min/max)
  - Date range (with paidAt or effectiveFor toggle)
  - Category filter
  - Account filter
- ✅ Real-time results with full transaction details
- ✅ Smart query parsing:
  - Account names
  - Week numbers (W34, Week 34)
  - Dates (various formats)
  - Months (January 2026, Jan 2026)
- ✅ Search executes on Enter key press
- ✅ Results show recurring indicator, edit button
- ✅ Case-insensitive search
- ✅ Fast search with 500 result limit

---

### ✅ Home Dashboard & Budget Analysis
- ✅ **Home Page (formerly Overview)**
  - Renamed from "Overview" to "Home"
  - Month selector
  - View by toggle (Effective For / Paid At)
  - Show Paid/Planned checkboxes
  - **Four Key Metrics:**
    - Total Spent (paid transactions)
    - Total Planned (planned transactions)
    - Total Budgeted (monthly budget targets)
    - Remaining (Budget - Spent - Planned)
  - Budget breakdown table (Budget | Planned | Paid | Total | vs Budget)
  - Spending trend chart (last 6 months)
- ✅ **Charts removed** as separate page (functionality integrated into Home)
- ✅ Terminology updated: "Target" → "Budget" throughout the app

---

### ✅ Navigation & UI
- ✅ Consistent navigation component on all pages
- ✅ Sticky navigation bar (stays at top when scrolling)
- ✅ Active page indicator
- ✅ Navigation order: Home | Transactions | Accounts | Categories
- ✅ Large "+" button for adding transactions
- ✅ Inline search field in navigation
- ✅ Sign Out button
- ✅ **Nordic Zen Styling**
  - Sage green, stone beige, charcoal color palette
  - Clean, minimal aesthetic
  - Consistent across all pages
  - Card-based layouts with shadows
  - Rounded corners and smooth transitions

---

## 🚧 IN PROGRESS / NEXT UP

### 🎯 Manual Transaction Ordering (HIGH PRIORITY)
- [ ] Add `sortOrder` integer field to Transaction model
- [ ] Default: order by date + time of creation
- [ ] **For same-day transactions:** Add drag-and-drop UI to reorder
  - Use @dnd-kit/sortable for smooth drag & drop
  - Visual handles/grip icons on transaction rows
  - Save order when dragging completes
- [ ] Apply to: Account ledger, Transactions list
- [ ] Preserve order when filtering/searching
- **Use case:** Multiple transactions on same day need chronological ordering (e.g., coffee → lunch → groceries)

---

### 🎮 Gamification & Behavioral Psychology (HIGH PRIORITY)
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

### 📸 Receipt Scanning & OCR (HIGH PRIORITY)
**Goal:** Make transaction entry effortless by scanning receipts instead of manual typing

#### Core Features:
- [ ] **Receipt Upload**
  - Camera capture (mobile) or file upload (desktop)
  - Support for photos of physical receipts
  - Support for digital receipts (screenshots, PDFs)
  - Image preview before processing

- [ ] **OCR Processing**
  - Extract key information:
    - Store/merchant name
    - Total amount
    - Date of purchase
    - Individual line items (optional)
  - Technology options:
    - Google Cloud Vision API
    - AWS Textract
    - Tesseract.js (free, client-side)
    - OpenAI GPT-4 Vision (best accuracy)
  
- [ ] **Smart Transaction Creation**
  - Auto-populate transaction form with extracted data
  - Let user review/edit before saving
  - Suggest category based on merchant name
  - Pre-fill date and amount
  - Option to save receipt image with transaction
  
- [ ] **Receipt Storage**
  - Store receipt images in Supabase Storage
  - Link to transaction record
  - View receipt from transaction details
  - Delete receipt option (GDPR compliance)
  
- [ ] **Batch Processing**
  - Upload multiple receipts at once
  - Queue processing
  - Progress indicator
  - Review all before saving

#### Advanced Features:
- [ ] Automatic category detection (AI learns from your patterns)
- [ ] Multi-currency support (read currency from receipt)
- [ ] Split receipt across multiple categories
- [ ] Tax/tip extraction for restaurants
- [ ] Mileage tracking from gas station receipts

**Why this matters:** Removes friction from expense tracking. Users more likely to track every expense if it's just "snap a photo". Major competitive advantage.

---

## 📱 MOBILE & DEPLOYMENT

### Mobile App / PWA
- [ ] Progressive Web App (PWA) setup
  - Add manifest.json
  - Service worker for offline support
  - Install prompts for iOS/Android
  - App icons and splash screens
- [ ] Mobile-optimized UI
  - Touch-friendly buttons and inputs
  - Swipe gestures (swipe to delete, swipe to mark paid)
  - Bottom navigation for easier thumb access
  - Responsive layouts for all screen sizes
- [ ] React Native / Expo version (future consideration)
  - Native iOS app for App Store
  - Native Android app for Google Play
  - Push notifications support

---

### 🚀 Beta Testing & Publishing

#### Beta Testing
- ✅ **Onboarding system** - Complete, helps beta users get started quickly
- [ ] Set up beta testing environment
  - Separate database for beta users
  - Feature flags for gradual rollout
  - Error tracking (Sentry or similar)
  - Analytics (Plausible/Google Analytics)
- [ ] Invite beta testers
  - Friends and family first
  - Small group of trusted users
  - Feedback form/survey
  - Bug reporting system
- [ ] Beta testing documentation
  - User guide / onboarding materials
  - Known issues list
  - FAQ

#### Production Deployment
- [ ] Deploy to Vercel (production)
  - Environment variables configured
  - Custom domain setup
  - SSL certificate
  - CDN configuration
- [ ] Database optimization for production
  - Connection pooling
  - Indexes for common queries
  - Backup strategy
- [ ] Monitoring & logging
  - Uptime monitoring
  - Performance monitoring
  - Error tracking
  - Usage analytics
- [ ] Legal & compliance
  - Privacy policy
  - Terms of service
  - GDPR compliance (for EU users)
  - Cookie consent

---

## 🔔 NOTIFICATIONS SYSTEM

### In-App Notifications
- [ ] **Notification Center UI**
  - Bell icon (🔔) next to Sign Out in navigation
  - Red badge showing unread count
  - Dropdown panel showing recent notifications
  - Mark as read functionality
  - "View all" link to full notifications page
- [ ] **Notification Types:**
  - Budget alerts (over budget warning)
  - Achievement unlocked
  - Savings milestones
  - Recurring transaction generated
  - End of month summary
- [ ] Database schema for notifications
  - Notification table (type, message, read status, timestamp)
  - User preferences for notification types

### Smart Notifications
- [ ] **Morning Notification**
  - "Good morning! You have X DKK budgeted for today"
  - List of planned expenses for the day (if any)
  - Motivational message
- [ ] **Evening Check-in**
  - "How much did you actually spend today?"
  - Compare planned vs actual
  - Celebrate if under budget
  - Gentle reminder if over budget
- [ ] **End of Month Summary**
  - Total spent vs budget
  - Money saved or overspent
  - Top spending categories
  - Achievement recap
  - Suggestions for next month
- [ ] **Mid-Month Warning/Encouragement**
  - "You're on track! Keep it up!" (if under budget)
  - "Warning: You're pacing to go over budget by X DKK" (if trending over)
  - Suggestion: "Consider transferring X DKK to savings"
- [ ] **Smart Suggestions**
  - "You have X DKK left this month. Want to transfer to savings?"
  - "Great month! You're Y% under budget"
  - "Heads up: Big expense planned for next week"

### Notification Delivery
- [ ] In-app notifications (database-driven, always available)
- [ ] Email notifications (optional, user preference)
- [ ] Push notifications (PWA/mobile app, optional)
- [ ] Notification scheduling system
  - Cron jobs or Vercel cron
  - Time zone aware
  - User preference for delivery times

---

## 🔐 SECURITY & USER MANAGEMENT

### Password & Authentication Security
- [ ] **Password Requirements**
  - Minimum length (12+ characters recommended)
  - Complexity requirements (uppercase, lowercase, numbers, special chars)
  - Password strength indicator on signup/change password
  - Prevent common passwords (check against known password lists)
- [ ] **Email Verification**
  - Send verification email on signup
  - Require email confirmation before full access
  - Resend verification email option
- [ ] **Forgot Password Flow**
  - "Forgot password?" link on login page
  - Send password reset email with secure token
  - Token expiration (e.g., 1 hour)
  - Password reset form
  - Confirm new password
- [ ] **General Security Best Practices**
  - Rate limiting on login attempts (prevent brute force)
  - Two-factor authentication (2FA) option
  - Session management (automatic logout after inactivity)
  - Secure headers (HSTS, CSP, etc.)
  - SQL injection prevention (Prisma handles this)
  - XSS protection
  - CSRF protection
- [ ] **Data Protection**
  - Encrypt sensitive data at rest
  - HTTPS everywhere (SSL)
  - Secure API endpoints
  - Input validation and sanitization
  - Audit logs for sensitive operations

---

## 🎓 ONBOARDING & USER EXPERIENCE

### New User Onboarding Flow
- [ ] **Welcome Screen**
  - Brief intro to app philosophy ("Plan first, spend smart")
  - Key benefits (track expenses, stay under budget, save money)
  - "Get Started" button
- [ ] **Step 1: Profile Setup**
  - Primary currency selection
  - Timezone (auto-detect with option to change)
  - Monthly income (optional, for insights)
  - Skip option available
- [ ] **Step 2: Create First Account**
  - Guided form with tooltips
  - Example accounts shown (Checking, Savings, Credit Card)
  - "Add opening balance" explanation
  - Skip option to do later
  - "Add another account" option
- [ ] **Step 3: Set Up Categories**
  - Pre-filled common categories (Groceries, Rent, Transport, Dining Out, etc.)
  - Option to customize or add more
  - Set monthly budget for each category
  - Visual guide: "This is how much you plan to spend per month"
  - Skip option to set budgets later
- [ ] **Step 4: Add First Transaction**
  - Interactive tutorial showing how to add expense
  - Explain "Planned" vs "Paid" concept
  - Explain "Paid At" vs "Effective For" dates
  - Show split transaction feature
  - Skip to dashboard option
- [ ] **Step 5: Quick Tour**
  - Highlight key features (Home, Accounts, Transactions, Search)
  - "You can explore on your own now!"
  - "Start tracking" button to close onboarding
- [ ] **Onboarding Progress Tracker**
  - Visual progress bar (Step 1 of 5)
  - "Skip tutorial" option always available
  - Save progress (can resume later)
- [ ] **Post-Onboarding**
  - "Need help?" button always visible
  - Interactive tooltips on first use of features
  - Knowledge base / Help center

---

## 🏦 BANK INTEGRATION (Future)

### Research & Planning
- [ ] **Denmark-Specific Research**
  - MitID integration possibility
  - Local bank APIs (Danske Bank, Nordea, Jyske Bank, etc.)
  - Open Banking regulations in Denmark (PSD2)
  - Feasibility of direct bank connections
- [ ] **Bank Aggregator Services**
  - Research options:
    - **Tink** (strong in Nordics)
    - **TrueLayer** (UK/Europe)
    - **Salt Edge** (global)
    - **Plaid** (US/Canada, limited Europe)
  - Compare pricing, coverage, features
  - Test API access and documentation
  - Evaluate security and compliance

### Implementation (When Ready)
- [ ] Choose aggregator and sign up for API access
- [ ] Implement OAuth flow for bank connection
- [ ] Fetch transactions from bank
- [ ] Parse and normalize transaction data
- [ ] **Smart Matching:**
  - Match imported transactions to planned transactions
  - Auto-mark planned as paid when match found
  - Suggest category based on merchant/description
- [ ] **Reconciliation Workflow:**
  - Show unmatched transactions
  - Manual review and categorization
  - Bulk import with confirmation
- [ ] **Ongoing Sync:**
  - Daily/hourly sync of new transactions
  - Notification when new transactions arrive
  - Handle duplicates gracefully
- [ ] Security considerations:
  - Encrypted bank credentials
  - Secure token storage
  - Clear consent and permissions
  - Option to disconnect bank at any time

---

## 📊 ADDITIONAL FEATURES (Backlog)

### Insight Cards & Smart Analytics
- [ ] "Biggest expense this month"
- [ ] "Most under-budget category" 🎉
- [ ] "Trending up/down" with percentages
- [ ] Quick stats (total transactions, avg per day, savings rate)
- [ ] Spending velocity: "On track to spend X by end of month"
- [ ] Comparison to previous months
- [ ] Unusual spending alerts ("You spent 2x your usual on Dining Out")

### Edit Recurring Transactions
- [ ] Edit one occurrence vs edit entire series
- [ ] Update recurrence rule (frequency, end date)
- [ ] Bulk delete future occurrences
- [ ] Pause recurring transaction (without deleting)

### Multi-Currency Support
- [ ] Currency conversion API integration
- [ ] Show original + converted amounts
- [ ] Budget totals in primary currency
- [ ] Historical exchange rates for accuracy
- [ ] Multi-currency reports

### Account Sharing (Future)
- [ ] Invite another user to an account
- [ ] Role-based permissions (owner/editor/viewer)
- [ ] Activity log (who added/edited what)
- [ ] Notifications for shared account activity

### Advanced Reporting
- [ ] Export to CSV/Excel
- [ ] PDF reports (monthly statements)
- [ ] Tax preparation reports
- [ ] Custom date ranges
- [ ] Printable summaries

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

## 📁 File Structure

```
/src
  /app
    /auth
      /login/page.tsx
      /signup/page.tsx
    /accounts
      /page.tsx                    # List all accounts
      /[id]/page.tsx               # Account ledger
      /[id]/edit/page.tsx          # Edit account
      /[id]/reconcile/page.tsx     # Reconcile balance
      /new/page.tsx                # Create account
    /categories
      /page.tsx                    # List + create + set budgets
      /new/page.tsx                # Create category
    /transactions
      /page.tsx                    # All transactions (with filters)
      /add/page.tsx                # Add transaction (expense/income/transfer)
      /[id]/edit/page.tsx          # Edit transaction
    /home/page.tsx                 # Dashboard with metrics & budget table
    /search/page.tsx               # Search page with advanced filters
    /health/page.tsx               # Database health check
    /page.tsx                      # Root (redirects to /home)
    layout.tsx
    globals.css

  /components
    Navigation.tsx                 # Consistent nav bar with search

  /lib
    prisma.ts                      # Prisma client singleton
    /supabase
      client.ts                    # Client-side Supabase
      server.ts                    # Server-side Supabase

  /api
    /accounts/route.ts
    /accounts/[id]/route.ts
    /accounts/[id]/reconcile/route.ts
    /categories/route.ts
    /transactions/route.ts
    /transactions/[id]/route.ts
    /transactions/generate-recurring/route.ts
    /overview/route.ts
    /charts/route.ts
    /search/route.ts
    /auth/signout/route.ts

/prisma
  schema.prisma
  /migrations
```

---

## 🎯 IMMEDIATE PRIORITIES

1. **Manual Transaction Ordering** - Drag & drop for same-day transactions
2. **Onboarding Flow** - Guide new users through setup
3. **Notifications System** - In-app bell icon + smart notifications
4. **Security Hardening** - Email verification, password reset, improved password requirements
5. **PWA Setup** - Make it installable on mobile devices
6. **Beta Testing** - Get feedback from real users
7. **Gamification** - Start with simple achievements and daily win/loss summaries

---

## 💡 PRODUCT DIFFERENTIATION

What makes this app unique:
1. **Planned-first approach** - Plan before you spend, not just track after
2. **Two-date system** - Separate when you pay from when it affects your budget
3. **Positive gamification** - Celebrate wins, not shame for overspending
4. **Beautiful, calming design** - Nordic Zen aesthetic, not corporate banking
5. **Flexible & powerful** - Split transactions, recurring patterns, smart search
6. **Privacy-focused** - Your data stays yours, no selling to advertisers
7. **Built by a power user** - Designed by someone who actually uses complex budgets

**Tagline ideas:**
- "Plan smart. Spend less. Feel great."
- "The budget app that celebrates your wins"
- "Your money, your plan, your peace of mind"
