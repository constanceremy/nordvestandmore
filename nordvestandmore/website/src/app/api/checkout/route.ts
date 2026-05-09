import { NextRequest, NextResponse } from "next/server";
import { getStripe } from "@/lib/stripe";

export async function POST(req: NextRequest) {
  try {
    const { eventId, eventSlug, eventTitle, eventDate, price, currency, stripeProductId, cancellationHours, requiresConfirmation } =
      await req.json();

    const origin = req.headers.get("origin") || "https://nordvestandmore.com";
    const stripe = getStripe();

    const session = await stripe.checkout.sessions.create({
      mode: "payment",
      ...(requiresConfirmation ? { payment_intent_data: { capture_method: "manual" } } : {}),
      line_items: [
        {
          quantity: 1,
          price_data: {
            currency: currency.toLowerCase(),
            unit_amount: price * 100,
            ...(stripeProductId
              ? { product: stripeProductId }
              : { product_data: { name: eventTitle, description: "NV & more — Event booking" } }
            ),
          },
        },
      ],
      success_url: `${origin}/booking/success?session_id={CHECKOUT_SESSION_ID}&event=${eventSlug}`,
      cancel_url: `${origin}/our-events/${eventSlug}`,
      allow_promotion_codes: true,
      phone_number_collection: { enabled: true },
      metadata: { eventId, eventSlug, ...(eventTitle ? { eventTitle } : {}), ...(eventDate ? { eventDate } : {}), ...(cancellationHours != null ? { cancellationHours: String(cancellationHours) } : {}), ...(requiresConfirmation ? { requiresConfirmation: "true" } : {}) },
    });

    return NextResponse.json({ url: session.url });
  } catch (err) {
    console.error("Checkout error:", err);
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Checkout failed" },
      { status: 500 }
    );
  }
}
