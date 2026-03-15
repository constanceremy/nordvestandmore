import { NextRequest, NextResponse } from "next/server";
import { getStripe } from "@/lib/stripe";
import { getSupabase } from "@/lib/supabase";
import Stripe from "stripe";
import nodemailer from "nodemailer";
import { Client } from "@notionhq/client";

export const dynamic = "force-dynamic";

const transporter = nodemailer.createTransport({
  service: "gmail",
  auth: {
    user: process.env.GMAIL_USER,
    pass: process.env.GMAIL_APP_PASSWORD,
  },
});

async function sendConfirmationEmail({
  name,
  email,
  eventDate,
  amount,
  currency,
}: {
  name: string;
  email: string;
  eventDate?: string;
  amount: number;
  currency: string;
}) {
  const dateLabel = eventDate
    ? new Date(eventDate).toLocaleDateString("en-DK", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : "";

  await transporter.sendMail({
    from: `"NV & more" <${process.env.GMAIL_USER}>`,
    to: email,
    subject: "Your booking is confirmed — NV & more",
    html: `
      <div style="font-family: sans-serif; max-width: 560px; margin: 0 auto; color: #111;">
        <h2 style="font-size: 24px; margin-bottom: 8px;">You're booked!</h2>
        <p>Hi ${name},</p>
        <p>Your booking is confirmed. We look forward to seeing you${dateLabel ? ` on <strong>${dateLabel}</strong>` : ""}.</p>
        ${amount > 0 ? `<p>Amount paid: <strong>${amount} ${currency}</strong></p>` : ""}
        <p>If you have any questions, reply to this email or write us at <a href="mailto:nordvestandmore@gmail.com">nordvestandmore@gmail.com</a>.</p>
        <p style="margin-top: 32px;">See you soon,<br/>Constance<br/>NV & more</p>
      </div>
    `,
  });
}

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
    const { eventId, eventSlug, eventDate } = session.metadata ?? {};
    const supabase = getSupabase();
    const name = session.customer_details?.name ?? "";
    const email = session.customer_details?.email ?? "";
    const amount = (session.amount_total ?? 0) / 100;
    const currency = session.currency?.toUpperCase() ?? "DKK";

    // Save booking to Supabase
    const { error } = await supabase.from("bookings").insert({
      event_id: eventId,
      event_slug: eventSlug,
      event_date: eventDate ?? null,
      name,
      email,
      phone: session.customer_details?.phone ?? null,
      stripe_session_id: session.id,
      stripe_payment_intent: session.payment_intent as string,
      amount_paid: amount,
      currency,
      status: "confirmed",
    });

    if (error) {
      console.error("Supabase insert error:", error);
      // Don't return 500 — Stripe would retry endlessly. Log and continue.
    }

    // Increment "Booked spots" in Notion Sessions DB
    if (eventId) {
      try {
        const notion = new Client({ auth: process.env.NOTION_TOKEN });
        const page = await notion.pages.retrieve({ page_id: eventId }) as { properties: Record<string, { type: string; number?: number | null }> };
        const current = page.properties["Booked spots"]?.number ?? 0;
        await notion.pages.update({
          page_id: eventId,
          properties: { "Booked spots": { number: current + 1 } },
        });
      } catch (err) {
        console.error("Notion update error:", err);
      }
    }

    // Send confirmation email
    if (email) {
      try {
        await sendConfirmationEmail({ name, email, eventDate, amount, currency });
      } catch (err) {
        console.error("Email error:", err);
        // Don't fail the webhook if email fails
      }
    }
  }

  return NextResponse.json({ received: true });
}
