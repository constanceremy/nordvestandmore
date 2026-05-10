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

  const statusNote = booking.status === "pending"
    ? `The payment hold will be released — no charge will be made to their card.`
    : `The booking is already confirmed and paid. A refund will be issued automatically.`;

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
    <p style="color:#666;font-size:14px;">${statusNote}</p>
    <p style="color:#666;font-size:14px;">A cancellation email will be sent to ${booking.email}.</p>
    <form method="POST">
      <input type="hidden" name="id" value="${id}" />
      <input type="hidden" name="secret" value="${secret}" />
      <button type="submit" style="padding:12px 24px;background:#dc2626;color:#fff;border:none;font-size:15px;font-weight:600;letter-spacing:0.05em;cursor:pointer;">Cancel this booking</button>
    </form>
  `);
}

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const id = formData.get("id") as string;
  const secret = formData.get("secret") as string;

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
  const wasCharged = booking.status === "confirmed";
  let stripeNote = "";

  try {
    if (booking.status === "pending" && booking.stripe_payment_intent) {
      await stripe.paymentIntents.cancel(booking.stripe_payment_intent);
      stripeNote = "Payment hold released — no charge was made.";
    } else if (booking.status === "confirmed" && booking.stripe_payment_intent) {
      await stripe.refunds.create({ payment_intent: booking.stripe_payment_intent });
      stripeNote = "Refund issued to their card.";
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
      await transporter.sendMail({
        from: `"NV & more" <${process.env.GMAIL_USER}>`,
        to: booking.email,
        subject: "Your booking has been cancelled - NV & more",
        text: `Hi ${booking.name},

Your booking${booking.event_title ? ` for ${booking.event_title}` : ""}${dateLabel ? ` on ${dateLabel}` : ""} has been cancelled.${wasCharged ? " A refund has been issued to your card." : " No charge was made to your card."}

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
            ${wasCharged ? `<p>A refund has been issued to your card.</p>` : `<p>No charge was made to your card.</p>`}
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
