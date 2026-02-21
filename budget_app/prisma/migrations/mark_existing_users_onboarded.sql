-- Mark all existing profiles as having completed onboarding
-- This is for existing users who were using the app before onboarding was added

UPDATE "Profile" SET "onboardingCompleted" = true WHERE "onboardingCompleted" = false;
