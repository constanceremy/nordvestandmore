import { NextRequest, NextResponse } from "next/server";
import { getStripe } from "@/lib/stripe";
import { getSupabase } from "@/lib/supabase";
import nodemailer from "nodemailer";

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

type Booking = {
  name: string;
  email: string;
  event_id: string;
  event_title: string;
  event_date: string;
  amount_paid: number;
  currency: string;
  stripe_payment_intent: string;
};

async function sendConfirmedEmail(booking: Booking) {
  const dateLabel = booking.event_date
    ? new Date(booking.event_date).toLocaleDateString("en-DK", { weekday: "long", day: "numeric", month: "long", year: "numeric" })
    : "";
  const policyUrl = booking.event_id
    ? `https://nordvestandmore.com/with-us/${booking.event_id}`
    : "https://nordvestandmore.com/with-us";
  await transporter.sendMail({
    from: `"NV & more" <${process.env.GMAIL_USER}>`,
    to: booking.email,
    subject: "Your booking is confirmed — NV & more",
    html: `
      <div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#111;">
        <h2 style="font-size:24px;margin-bottom:8px;">You're booked!</h2>
        <p>Hi ${booking.name},</p>
        <p>Great news — the event is confirmed and we look forward to seeing you${dateLabel ? ` on <strong>${dateLabel}</strong>` : ""}.</p>
        ${booking.amount_paid > 0 ? `<p>Amount charged: <strong>${booking.amount_paid} ${booking.currency}</strong></p>` : ""}
        <div style="margin-top:24px;padding:16px;border:1px solid #e5e7eb;background:#f9fafb;">
          <p style="margin:0 0 8px 0;font-weight:600;font-size:14px;">Need to cancel?</p>
          <p style="margin:0 0 8px 0;font-size:14px;color:#374151;">Reply to this email or write us at <a href="mailto:nordvestandmore@gmail.com">nordvestandmore@gmail.com</a>.</p>
          <p style="margin:0;font-size:13px;"><a href="${policyUrl}" style="color:#111;">View booking policy →</a></p>
        </div>
        <p style="margin-top:32px;">See you soon,<br/>Constance<br/><br/><a href="https://www.instagram.com/nordvestandmore">@nordvestandmore</a></p>
      </div>
    `,
  });
}

async function sendCancelledEmail(booking: Booking) {
  await transporter.sendMail({
    from: `"NV & more" <${process.env.GMAIL_USER}>`,
    to: booking.email,
    subject: "Update on your reservation — NV & more",
    html: `
      <div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#111;">
        <h2 style="font-size:24px;margin-bottom:8px;">Event update</h2>
        <p>Hi ${booking.name},</p>
        <p>Unfortunately${booking.event_title ? ` <strong>${booking.event_title}</strong>` : " the event"} isn't going ahead. Your reservation has been cancelled and <strong>no charge was made</strong> to your card.</p>
        <p>We hope to see you at a future event — keep an eye on <a href="https://nordvestandmore.com/with-us">nordvestandmore.com</a> for what's coming up.</p>
        <p style="margin-top:32px;">Thanks for your understanding,<br/>Constance<br/><br/><a href="https://www.instagram.com/nordvestandmore">@nordvestandmore</a></p>
      </div>
    `,
  });
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const sessionId = searchParams.get("session");
  const action = searchParams.get("action");
  const secret = searchParams.get("secret");

  if (!sessionId || !action || secret !== process.env.CAPTURE_SECRET || !["capture", "cancel"].includes(action)) {
    return unauthorized();
  }

  const supabase = getSupabase();
  const { data: bookings } = await supabase
    .from("bookings")
    .select("name, email, event_id, event_title, event_date, amount_paid, currency, stripe_payment_intent")
    .eq("event_id", sessionId)
    .eq("status", "pending");

  if (!bookings || bookings.length === 0) {
    return html(`<h2>No pending bookings</h2><p>There are no pending reservations for this session.</p>`);
  }

  const eventTitle = bookings[0].event_title ?? "this event";
  const eventDate = bookings[0].event_date
    ? new Date(bookings[0].event_date).toLocaleDateString("en-DK", { weekday: "long", day: "numeric", month: "long", year: "numeric" })
    : "";
  const total = bookings.reduce((sum: number, b: Booking) => sum + (b.amount_paid ?? 0), 0);
  const currency = bookings[0].currency ?? "DKK";

  const rows = bookings.map((b: Booking) =>
    `<tr><td style="padding:6px 0;border-bottom:1px solid #e5e7eb;">${b.name}</td><td style="padding:6px 0;border-bottom:1px solid #e5e7eb;color:#666;">${b.email}</td><td style="padding:6px 0;border-bottom:1px solid #e5e7eb;text-align:right;">${b.amount_paid} ${b.currency}</td></tr>`
  ).join("");

  const color = action === "capture" ? "#111" : "#dc2626";
  const label = action === "capture"
    ? `Confirm &amp; charge all ${bookings.length} ${bookings.length === 1 ? "person" : "people"}`
    : `Cancel session &amp; release all ${bookings.length} ${bookings.length === 1 ? "reservation" : "reservations"}`;
  const heading = action === "capture"
    ? `Confirm "${eventTitle}"?`
    : `Cancel "${eventTitle}"?`;
  const description = action === "capture"
    ? `This will charge all ${bookings.length} ${bookings.length === 1 ? "person" : "people"} below and send them a confirmation email.`
    : `This will release all holds and send everyone a cancellation email. No charges will be made.`;

  return html(`
    <h2>${heading}${eventDate ? `<br/><span style="font-size:16px;font-weight:400;color:#666;">${eventDate}</span>` : ""}</h2>
    <p>${description}</p>
    <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
      <thead><tr>
        <th style="text-align:left;padding:6px 0;border-bottom:2px solid #111;font-size:13px;">Name</th>
        <th style="text-align:left;padding:6px 0;border-bottom:2px solid #111;font-size:13px;">Email</th>
        <th style="text-align:right;padding:6px 0;border-bottom:2px solid #111;font-size:13px;">Amount</th>
      </tr></thead>
      <tbody>${rows}</tbody>
      ${action === "capture" ? `<tfoot><tr><td colspan="2" style="padding:8px 0;font-weight:600;">Total</td><td style="padding:8px 0;font-weight:600;text-align:right;">${total} ${currency}</td></tr></tfoot>` : ""}
    </table>
    <form method="POST">
      <input type="hidden" name="session" value="${sessionId}" />
      <input type="hidden" name="action" value="${action}" />
      <input type="hidden" name="secret" value="${secret}" />
      <button type="submit" style="padding:12px 24px;background:${color};color:#fff;border:none;font-size:15px;font-weight:600;letter-spacing:0.05em;cursor:pointer;">${label}</button>
    </form>
  `);
}

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const sessionId = formData.get("session") as string;
  const action = formData.get("action") as string;
  const secret = formData.get("secret") as string;

  if (!sessionId || !action || secret !== process.env.CAPTURE_SECRET || !["capture", "cancel"].includes(action)) {
    return unauthorized();
  }

  const stripe = getStripe();
  const supabase = getSupabase();

  const { data: bookings } = await supabase
    .from("bookings")
    .select("name, email, event_id, event_title, event_date, amount_paid, currency, stripe_payment_intent")
    .eq("event_id", sessionId)
    .eq("status", "pending");

  if (!bookings || bookings.length === 0) {
    return html(`<h2>No pending bookings</h2><p>Nothing to process.</p>`);
  }

  const results: string[] = [];

  for (const booking of bookings as Booking[]) {
    try {
      if (action === "capture") {
        await stripe.paymentIntents.capture(booking.stripe_payment_intent);
        await supabase.from("bookings").update({ status: "confirmed" }).eq("stripe_payment_intent", booking.stripe_payment_intent);
        if (booking.email) await sendConfirmedEmail(booking);
        results.push(`<li>✓ ${booking.name} — charged ${booking.amount_paid} ${booking.currency}</li>`);
      } else {
        await stripe.paymentIntents.cancel(booking.stripe_payment_intent);
        await supabase.from("bookings").update({ status: "cancelled" }).eq("stripe_payment_intent", booking.stripe_payment_intent);
        if (booking.email) await sendCancelledEmail(booking);
        results.push(`<li>✓ ${booking.name} — released</li>`);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "unknown error";
      results.push(`<li style="color:#dc2626;">✗ ${booking.name} — ${message}</li>`);
    }
  }

  const heading = action === "capture" ? "Done — all cards charged." : "Done — all reservations released.";
  return html(`<h2>${heading}</h2><ul style="line-height:1.8;">${results.join("")}</ul>`);
}
