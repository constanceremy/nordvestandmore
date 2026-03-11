import { createClient } from "@supabase/supabase-js";

export function getSupabase() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}

export type Booking = {
  id: string;
  event_id: string;
  event_slug: string;
  name: string;
  email: string;
  stripe_session_id: string;
  stripe_payment_intent: string;
  amount_paid: number;
  currency: string;
  status: "pending" | "confirmed" | "cancelled";
  created_at: string;
};
