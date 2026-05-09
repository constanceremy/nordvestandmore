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

async function sendReservationEmail({
  name,
  email,
  eventDate,
  eventTitle,
  eventId,
  amount,
  currency,
}: {
  name: string;
  email: string;
  eventDate?: string;
  eventTitle?: string;
  eventId?: string;
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
  const policyUrl = eventId ? `https://nordvestandmore.com/our-events/${eventId}` : "https://nordvestandmore.com/our-events";

  await transporter.sendMail({
    from: `"NV & more" <${process.env.GMAIL_USER}>`,
    to: email,
    subject: "Your spot is reserved - NV & more",
    text: `Hi ${name},

Your spot is held${eventTitle ? ` for ${eventTitle}` : ""}${dateLabel ? ` on ${dateLabel}` : ""}. We're confirming the event is going ahead and will be in touch soon.

Your card has not been charged yet. You'll only be billed once we confirm the event is happening.
${amount > 0 ? `\nAmount to be charged if confirmed: ${amount} ${currency}\n` : ""}
Need to cancel your reservation? Just reply to this email or write us at nordvestandmore@gmail.com.

Booking policy: ${policyUrl}

See you soon,
Constance
@nordvestandmore
nordvestandmore.com`,
    html: `
      <div style="font-family: sans-serif; max-width: 560px; margin: 0 auto; color: #111;">
        <h2 style="font-size: 24px; margin-bottom: 8px;">You're reserved!</h2>
        <p>Hi ${name},</p>
        <p>Your spot is held${eventTitle ? ` for <strong>${eventTitle}</strong>` : ""}${dateLabel ? ` on <strong>${dateLabel}</strong>` : ""}. We're confirming the event is going ahead and will be in touch soon.</p>
        <p><strong>Your card has not been charged yet.</strong> You'll only be billed once we confirm the event is happening — we'll send you a confirmation email at that point.</p>
        ${amount > 0 ? `<p>Amount to be charged if confirmed: <strong>${amount} ${currency}</strong></p>` : ""}
        <div style="margin-top: 24px; padding: 16px; border: 1px solid #e5e7eb; background: #f9fafb;">
          <p style="margin: 0 0 8px 0; font-weight: 600; font-size: 14px;">Need to cancel your reservation?</p>
          <p style="margin: 0 0 12px 0; font-size: 14px; color: #374151;">Just reply to this email or write us at <a href="mailto:nordvestandmore@gmail.com">nordvestandmore@gmail.com</a>.</p>
          <p style="margin: 0; font-size: 13px;"><a href="${policyUrl}" style="color: #111;">View booking policy</a></p>
        </div>
        <p style="margin-top: 24px;">If you have any questions, reply to this email.</p>
        <p style="margin-top: 32px;">See you soon,<br/>Constance<br/><br/><a href="https://www.instagram.com/nordvestandmore">@nordvestandmore</a><br/><a href="https://nordvestandmore.com">nordvestandmore.com</a></p>
      </div>
    `,
  });
}

async function sendConfirmationEmail({
  name,
  email,
  eventDate,
  eventTitle,
  eventId,
  amount,
  currency,
  cancellationHours,
}: {
  name: string;
  email: string;
  eventDate?: string;
  eventTitle?: string;
  eventId?: string;
  amount: number;
  currency: string;
  cancellationHours?: number;
}) {
  const dateLabel = eventDate
    ? new Date(eventDate).toLocaleDateString("en-DK", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : "";

  const cancellationSubject = `Booking Cancellation -- ${eventTitle || "event"} -- ${dateLabel || eventDate || ""} -- ${name}`;
  const cancellationMailto = `mailto:nordvestandmore@gmail.com?subject=${encodeURIComponent(cancellationSubject)}`;
  const policyUrl = eventId ? `https://nordvestandmore.com/our-events/${eventId}` : "https://nordvestandmore.com/our-events";

  const cancellationSection = `
    <div style="margin-top: 24px; padding: 16px; border: 1px solid #e5e7eb; background: #f9fafb;">
      <p style="margin: 0 0 8px 0; font-weight: 600; font-size: 14px;">Need to cancel?</p>
      ${cancellationHours && cancellationHours > 0
        ? `<p style="margin: 0 0 12px 0; font-size: 14px; color: #374151;">Please contact us at least <strong>${cancellationHours} hours</strong> before the event starts.</p>`
        : `<p style="margin: 0 0 12px 0; font-size: 14px; color: #374151;">Please contact us as soon as possible if you need to cancel.</p>`
      }
      <p style="margin: 0 0 8px 0; font-size: 13px;"><a href="${policyUrl}" style="color: #111;">View booking policy →</a></p>
      <a href="${cancellationMailto}" style="display: inline-block; margin-top: 4px; padding: 8px 16px; background: #111; color: #fff; text-decoration: none; font-size: 12px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase;">Email us to cancel</a>
    </div>
  `;

  const cancellationNote = cancellationHours && cancellationHours > 0
    ? `Please contact us at least ${cancellationHours} hours before the event if you need to cancel.`
    : "Please contact us as soon as possible if you need to cancel.";

  await transporter.sendMail({
    from: `"NV & more" <${process.env.GMAIL_USER}>`,
    to: email,
    subject: "Your booking is confirmed - NV & more",
    text: `Hi ${name},

Your booking is confirmed. We look forward to seeing you${dateLabel ? ` on ${dateLabel}` : ""}.
${amount > 0 ? `\nAmount paid: ${amount} ${currency}\n` : ""}
Need to cancel? ${cancellationNote}
Email us: nordvestandmore@gmail.com
Booking policy: ${policyUrl}

Terms of Sale: https://nordvestandmore.com/terms

See you soon,
Constance
@nordvestandmore
nordvestandmore.com`,
    html: `
      <div style="font-family: sans-serif; max-width: 560px; margin: 0 auto; color: #111;">
        <h2 style="font-size: 24px; margin-bottom: 8px;">You're booked!</h2>
        <p>Hi ${name},</p>
        <p>Your booking is confirmed. We look forward to seeing you${dateLabel ? ` on <strong>${dateLabel}</strong>` : ""}.</p>
        ${amount > 0 ? `<p>Amount paid: <strong>${amount} ${currency}</strong></p>` : ""}
        ${cancellationSection}
        <p style="margin-top: 24px;">If you have any other questions, reply to this email or write us at <a href="mailto:nordvestandmore@gmail.com">nordvestandmore@gmail.com</a>.</p>
        <p style="font-size: 13px; color: #666;">You can read our <a href="https://nordvestandmore.com/terms">Terms of Sale</a> on our website.</p>
        <p style="margin-top: 32px;">See you soon,<br/>Constance<br/><br/><a href="https://www.instagram.com/nordvestandmore">@nordvestandmore</a><br/><a href="https://nordvestandmore.com">nordvestandmore.com</a></p>
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
    const { eventId, eventSlug, eventTitle, eventDate, cancellationHours: cancellationHoursStr, requiresConfirmation: requiresConfirmationStr } = session.metadata ?? {};
    const cancellationHours = cancellationHoursStr ? parseInt(cancellationHoursStr, 10) : undefined;
    const requiresConfirmation = requiresConfirmationStr === "true";
    const supabase = getSupabase();
    const name = session.customer_details?.name ?? "";
    const email = session.customer_details?.email ?? "";
    const amount = (session.amount_total ?? 0) / 100;
    const currency = session.currency?.toUpperCase() ?? "DKK";

    // Deduplicate — skip if this Stripe session was already processed
    const { data: existing } = await supabase
      .from("bookings")
      .select("id")
      .eq("stripe_session_id", session.id)
      .maybeSingle();
    if (existing) {
      console.log("Duplicate webhook event, skipping:", session.id);
      return NextResponse.json({ received: true });
    }

    // Save booking to Supabase
    const { error } = await supabase.from("bookings").insert({
      event_id: eventId,
      event_slug: eventSlug,
      event_title: eventTitle ?? null,
      event_date: eventDate ?? null,
      name,
      email,
      phone: session.customer_details?.phone ?? null,
      stripe_session_id: session.id,
      stripe_payment_intent: session.payment_intent as string,
      amount_paid: amount,
      currency,
      status: requiresConfirmation ? "pending" : "confirmed",
    });

    if (error) {
      if (error.code === "23505") {
        // Unique constraint violation — already processed, skip silently
        console.log("Duplicate booking skipped:", session.id);
        return NextResponse.json({ received: true });
      }
      console.error("Supabase insert error:", error);
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

    // Send email to booker
    if (email) {
      try {
        if (requiresConfirmation) {
          await sendReservationEmail({ name, email, eventDate, eventTitle, eventId, amount, currency });
        } else {
          await sendConfirmationEmail({ name, email, eventDate, eventTitle, eventId, amount, currency, cancellationHours });
        }
      } catch (err) {
        console.error("Email error:", err);
      }
    }

    // Notify Constance
    try {
      const captureSecret = process.env.CAPTURE_SECRET ?? "";
      const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || "https://nordvestandmore.vercel.app";
      const captureUrl = `${baseUrl}/api/capture?session=${eventId}&action=capture&secret=${captureSecret}`;
      const cancelUrl = `${baseUrl}/api/capture?session=${eventId}&action=cancel&secret=${captureSecret}`;

      const pendingActions = requiresConfirmation ? `
        <div style="margin-top: 24px; padding: 16px; border: 1px solid #e5e7eb; background: #f9fafb;">
          <p style="margin: 0 0 12px 0; font-weight: 600;">This booking requires your confirmation.</p>
          <p style="margin: 0 0 12px 0; font-size: 13px; color: #666;">These links act on <strong>all pending reservations</strong> for this session at once.</p>
          <a href="${captureUrl}" style="display: inline-block; margin-right: 12px; padding: 10px 20px; background: #111; color: #fff; text-decoration: none; font-size: 13px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;">Confirm all &amp; charge</a>
          <a href="${cancelUrl}" style="display: inline-block; padding: 10px 20px; background: #fff; color: #dc2626; border: 1px solid #dc2626; text-decoration: none; font-size: 13px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;">Cancel session &amp; release all</a>
        </div>
      ` : "";

      await transporter.sendMail({
        from: `"NV & more" <${process.env.GMAIL_USER}>`,
        to: process.env.GMAIL_USER,
        replyTo: email,
        subject: `${requiresConfirmation ? "New reservation (pending)" : "New booking"} — ${eventTitle ?? eventSlug ?? "event"}${eventDate ? ` — ${eventDate}` : ""}`,
        html: `
          <div style="font-family: sans-serif; max-width: 560px; margin: 0 auto; color: #111;">
            <h2 style="font-size: 20px; margin-bottom: 16px;">${requiresConfirmation ? "New reservation — pending your confirmation" : "New booking"}</h2>
            <table style="width: 100%; border-collapse: collapse;">
              <tr><td style="padding: 8px 0; color: #666; width: 140px;">Name</td><td style="padding: 8px 0;">${name}</td></tr>
              <tr><td style="padding: 8px 0; color: #666;">Email</td><td style="padding: 8px 0;"><a href="mailto:${email}">${email}</a></td></tr>
              <tr><td style="padding: 8px 0; color: #666;">Phone</td><td style="padding: 8px 0;">${session.customer_details?.phone ?? "—"}</td></tr>
              <tr><td style="padding: 8px 0; color: #666;">Event</td><td style="padding: 8px 0;"><strong>${eventTitle ?? "—"}</strong></td></tr>
              <tr><td style="padding: 8px 0; color: #666;">Session ID</td><td style="padding: 8px 0;">${eventSlug ?? "—"}</td></tr>
              <tr><td style="padding: 8px 0; color: #666;">Date</td><td style="padding: 8px 0;">${eventDate ?? "—"}</td></tr>
              <tr><td style="padding: 8px 0; color: #666;">${requiresConfirmation ? "Amount to charge" : "Amount paid"}</td><td style="padding: 8px 0;">${amount} ${currency}</td></tr>
            </table>
            ${pendingActions}
            <p style="margin-top: 24px; color: #666; font-size: 13px;">Reply to this email to contact ${name}.</p>
          </div>
        `,
      });
    } catch (err) {
      console.error("Notification email error:", err);
    }

    // Revalidate website cache so spots/sold-out status updates immediately
    try {
      const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || "https://nordvestandmore.vercel.app";
      await fetch(`${baseUrl}/api/revalidate`, {
        method: "POST",
        headers: { "x-revalidate-secret": process.env.REVALIDATE_SECRET ?? "" },
      });
    } catch (err) {
      console.error("Revalidation error:", err);
    }
  }

  return NextResponse.json({ received: true });
}
