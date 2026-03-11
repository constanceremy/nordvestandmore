import { NextRequest, NextResponse } from "next/server";
import { getStripe } from "@/lib/stripe";

export async function POST(req: NextRequest) {
  try {
    const { eventId, eventSlug, eventTitle, price, currency, stripePriceId } =
      await req.json();

    const origin = req.headers.get("origin") || "https://nordvestandmore.com";
    const stripe = getStripe();

    let session;

    if (stripePriceId) {
      // Use existing Stripe price (set up in your Stripe dashboard)
      session = await stripe.checkout.sessions.create({
        mode: "payment",
        line_items: [{ price: stripePriceId, quantity: 1 }],
        success_url: `${origin}/booking/success?session_id={CHECKOUT_SESSION_ID}&event=${eventSlug}`,
        cancel_url: `${origin}/events/${eventSlug}`,
        metadata: { eventId, eventSlug },
      });
    } else {
      // Create a one-off price on the fly
      session = await stripe.checkout.sessions.create({
        mode: "payment",
        line_items: [
          {
            quantity: 1,
            price_data: {
              currency: currency.toLowerCase(),
              unit_amount: price * 100, // Stripe uses smallest currency unit
              product_data: {
                name: eventTitle,
                description: `NV & more — Event booking`,
              },
            },
          },
        ],
        success_url: `${origin}/booking/success?session_id={CHECKOUT_SESSION_ID}&event=${eventSlug}`,
        cancel_url: `${origin}/events/${eventSlug}`,
        metadata: { eventId, eventSlug },
      });
    }

    return NextResponse.json({ url: session.url });
  } catch (err) {
    console.error("Checkout error:", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Checkout failed" },
      { status: 500 }
    );
  }
}
