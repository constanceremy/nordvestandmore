import { NextRequest, NextResponse } from "next/server";
import { getStripe } from "@/lib/stripe";
import { getSupabase } from "@/lib/supabase";
import Stripe from "stripe";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = await req.text();
  const sig = req.headers.get("stripe-signature")!;
  const stripe = getStripe();

  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(
      body,
      sig,
      process.env.STRIPE_WEBHOOK_SECRET!
    );
  } catch (err) {
    console.error("Webhook signature error:", err);
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  if (event.type === "checkout.session.completed") {
    const session = event.data.object as Stripe.Checkout.Session;
    const { eventId, eventSlug } = session.metadata ?? {};
    const supabase = getSupabase();

    // Save booking to Supabase
    const { error } = await supabase.from("bookings").insert({
      event_id: eventId,
      event_slug: eventSlug,
      name: session.customer_details?.name ?? "",
      email: session.customer_details?.email ?? "",
      stripe_session_id: session.id,
      stripe_payment_intent: session.payment_intent as string,
      amount_paid: (session.amount_total ?? 0) / 100,
      currency: session.currency?.toUpperCase() ?? "DKK",
      status: "confirmed",
    });

    if (error) {
      console.error("Supabase insert error:", error);
      return NextResponse.json({ error: "DB error" }, { status: 500 });
    }
  }

  return NextResponse.json({ received: true });
}
