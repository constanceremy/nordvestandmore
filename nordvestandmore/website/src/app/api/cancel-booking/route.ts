import { NextRequest, NextResponse } from "next/server";
import { getStripe } from "@/lib/stripe";
import { getSupabase } from "@/lib/supabase";
import nodemailer from "nodemailer";
import { Client } from "@notionhq/client";

const transporter = nodemailer.createTransport({
  service: "gmail",
  auth: {
    user: process.env.GMAIL_USER,
    pass: process.env.GMAIL_APP_PASSWORD,
  },
});

function unauthorized() {
  return new NextResponse("Unauthorized", { status: 401 });
}

function html(body: string) {
  return new NextResponse(
    `<!DOCTYPE html><html><head><meta charset="utf-8"><title>NV & more</title></head><body style="font-family:sans-serif;max-width:560px;margin:80px auto;color:#111;">${body}</body></html>`,
    { headers: { "Content-Type": "text/html" } }
  );
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const id = searchParams.get("id");
  const secret = searchParams.get("secret");

  if (!id || secret !== process.env.CAPTURE_SECRET) {
    return unauthorized();
  }

  const supabase = getSupabase();
  const { data: booking } = await supabase
    .from("bookings")
    .select("id, name, email, event_title, event_date, amount_paid, currency, status")
    .eq("id", id)
    .single();

  if (!booking) {
    return html(`<h2>Booking not found</h2><p>No booking found with this ID.</p>`);
  }

  if (booking.status === "cancelled") {
    return html(`<h2>Already cancelled</h2><p>${booking.name}'s booking is already cancelled.</p>`);
  }

  const dateLabel = booking.event_date
    ? new Date(booking.event_date).toLocaleDateString("en-DK", { weekday: "long", day: "numeric", month: "long", year: "numeric" })
    : "";

  const isPending = booking.status === "pending";

  const refundNote = isPending
    ? `This is a pending reservation — the hold is on their card but not yet captured.`
    : `The booking was paid (${booking.amount_paid} ${booking.currency}). Choose whether to issue a refund.`;

  const withRefundLabel = isPending
    ? `Cancel + charge them (${booking.amount_paid} ${booking.currency}) — per booking policy`
    : `Cancel + refund ${booking.amount_paid} ${booking.currency}`;
  const noRefundLabel = isPending
    ? "Cancel + release hold (be nice, no charge)"
    : "Cancel (keep payment)";

  return html(`
    <h2>Cancel booking?</h2>
    <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
      <tr><td style="padding:6px 0;color:#666;width:120px;">Name</td><td style="padding:6px 0;">${booking.name}</td></tr>
      <tr><td style="padding:6px 0;color:#666;">Email</td><td style="padding:6px 0;">${booking.email}</td></tr>
      <tr><td style="padding:6px 0;color:#666;">Event</td><td style="padding:6px 0;">${booking.event_title ?? "—"}</td></tr>
      ${dateLabel ? `<tr><td style="padding:6px 0;color:#666;">Date</td><td style="padding:6px 0;">${dateLabel}</td></tr>` : ""}
      <tr><td style="padding:6px 0;color:#666;">Amount</td><td style="padding:6px 0;">${booking.amount_paid} ${booking.currency}</td></tr>
      <tr><td style="padding:6px 0;color:#666;">Status</td><td style="padding:6px 0;">${booking.status}</td></tr>
    </table>
    <p style="color:#666;font-size:14px;margin-bottom:20px;">${refundNote}</p>
    <p style="color:#666;font-size:13px;margin-bottom:20px;">A cancellation email will be sent to ${booking.email} either way. The spot will be freed up in both cases.</p>
    <form method="POST" style="display:flex;flex-direction:column;gap:12px;">
      <input type="hidden" name="id" value="${id}" />
      <input type="hidden" name="secret" value="${secret}" />
      <button type="submit" name="refund" value="yes" style="padding:12px 24px;background:#dc2626;color:#fff;border:none;font-size:14px;font-weight:600;letter-spacing:0.05em;cursor:pointer;text-align:left;">${withRefundLabel}</button>
      <button type="submit" name="refund" value="no" style="padding:12px 24px;background:#fff;color:#111;border:1px solid #111;font-size:14px;font-weight:600;letter-spacing:0.05em;cursor:pointer;text-align:left;">${noRefundLabel}</button>
    </form>
  `);
}

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const id = formData.get("id") as string;
  const secret = formData.get("secret") as string;
  const refund = formData.get("refund") === "yes";

  if (!id || secret !== process.env.CAPTURE_SECRET) {
    return unauthorized();
  }

  const supabase = getSupabase();
  const { data: booking } = await supabase
    .from("bookings")
    .select("id, name, email, event_id, event_title, event_date, amount_paid, currency, status, stripe_payment_intent")
    .eq("id", id)
    .single();

  if (!booking) {
    return html(`<h2>Booking not found</h2>`);
  }

  if (booking.status === "cancelled") {
    return html(`<h2>Already cancelled</h2><p>${booking.name}'s booking is already cancelled.</p>`);
  }

  const stripe = getStripe();
  let stripeNote = "";

  try {
    if (booking.status === "pending" && booking.stripe_payment_intent) {
      if (refund) {
        // "Be nice" — release the hold, no charge
        await stripe.paymentIntents.cancel(booking.stripe_payment_intent);
        stripeNote = "Hold released — no charge was made.";
      } else {
        // Per booking policy — capture the hold, then they're charged
        await stripe.paymentIntents.capture(booking.stripe_payment_intent);
        stripeNote = `${booking.amount_paid} ${booking.currency} charged per booking policy.`;
      }
    } else if (booking.status === "confirmed" && booking.stripe_payment_intent) {
      if (refund) {
        await stripe.refunds.create({ payment_intent: booking.stripe_payment_intent });
        stripeNote = "Refund issued to their card.";
      } else {
        stripeNote = "No refund issued — payment kept.";
      }
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : "unknown error";
    return html(`<h2>Stripe error</h2><p style="color:#dc2626;">${message}</p><p>Booking was not cancelled. Try again or handle manually in Stripe.</p>`);
  }

  await supabase.from("bookings").update({ status: "cancelled" }).eq("id", id);

  if (booking.event_id) {
    try {
      const notion = new Client({ auth: process.env.NOTION_TOKEN });
      const page = await notion.pages.retrieve({ page_id: booking.event_id }) as { properties: Record<string, { type: string; number?: number | null }> };
      const current = page.properties["Booked spots"]?.number ?? 0;
      await notion.pages.update({
        page_id: booking.event_id,
        properties: { "Booked spots": { number: Math.max(0, current - 1) } },
      });
    } catch (err) {
      console.error("Notion update error:", err);
    }
  }

  if (booking.email) {
    try {
      const dateLabel = booking.event_date
        ? new Date(booking.event_date).toLocaleDateString("en-DK", { weekday: "long", day: "numeric", month: "long", year: "numeric" })
        : "";
      const wasPending = booking.status === "pending";
      const wasCharged = booking.status === "confirmed";
      // pending + no refund = we captured (charged them per policy)
      // pending + refund = we released the hold (no charge, being nice)
      // confirmed + refund = we issued a refund
      // confirmed + no refund = payment kept
      const refundLine = wasPending && !refund
        ? ` As per our booking policy, your card has been charged ${booking.amount_paid} ${booking.currency}.`
        : wasPending && refund
        ? " Your payment hold has been released — no charge was made."
        : wasCharged && refund
        ? " A refund has been issued to your card."
        : "";

      await transporter.sendMail({
        from: `"NV & more" <${process.env.GMAIL_USER}>`,
        to: booking.email,
        subject: "Your booking has been cancelled - NV & more",
        text: `Hi ${booking.name},

Your booking${booking.event_title ? ` for ${booking.event_title}` : ""}${dateLabel ? ` on ${dateLabel}` : ""} has been cancelled.${refundLine}

If you have any questions, reply to this email or write us at nordvestandmore@gmail.com.

See you at a future event,
Constance
@nordvestandmore
nordvestandmore.com`,
        html: `
          <div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#111;">
            <h2 style="font-size:24px;margin-bottom:8px;">Booking cancelled</h2>
            <p>Hi ${booking.name},</p>
            <p>Your booking${booking.event_title ? ` for <strong>${booking.event_title}</strong>` : ""}${dateLabel ? ` on <strong>${dateLabel}</strong>` : ""} has been cancelled.</p>
            ${wasPending && !refund ? `<p>As per our booking policy, your card has been charged <strong>${booking.amount_paid} ${booking.currency}</strong>.</p>` : wasPending && refund ? `<p>Your payment hold has been released — no charge was made.</p>` : wasCharged && refund ? `<p>A refund has been issued to your card.</p>` : ""}
            <p>If you have any questions, reply to this email or write us at <a href="mailto:nordvestandmore@gmail.com">nordvestandmore@gmail.com</a>.</p>
            <p style="margin-top:32px;">See you at a future event,<br/>Constance<br/><br/><a href="https://www.instagram.com/nordvestandmore">@nordvestandmore</a><br/><a href="https://nordvestandmore.com">nordvestandmore.com</a></p>
          </div>
        `,
      });
    } catch (err) {
      console.error("Cancellation email error:", err);
    }
  }

  try {
    const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || "https://nordvestandmore.vercel.app";
    await fetch(`${baseUrl}/api/revalidate`, {
      method: "POST",
      headers: { "x-revalidate-secret": process.env.REVALIDATE_SECRET ?? "" },
    });
  } catch (err) {
    console.error("Revalidation error:", err);
  }

  return html(`<h2>Done.</h2><p>${booking.name}'s booking has been cancelled and they've been notified by email.</p><p style="color:#666;font-size:14px;">${stripeNote}</p>`);
}
