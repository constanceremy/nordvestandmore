import { NextRequest, NextResponse } from "next/server";
import nodemailer from "nodemailer";

const transporter = nodemailer.createTransport({
  service: "gmail",
  auth: {
    user: process.env.GMAIL_USER,
    pass: process.env.GMAIL_APP_PASSWORD,
  },
});

export async function POST(req: NextRequest) {
  const { experienceName, name, email, dates, people, topics, notes, phone, canCall } = await req.json();

  if (!name || !email) {
    return NextResponse.json({ error: "Name and email are required" }, { status: 400 });
  }

  try {
    // Email to Constance
    await transporter.sendMail({
      from: `"NV & more" <${process.env.GMAIL_USER}>`,
      to: process.env.GMAIL_USER,
      replyTo: email,
      subject: `Private tour request — ${experienceName}`,
      html: `
        <div style="font-family: sans-serif; max-width: 560px; margin: 0 auto; color: #111;">
          <h2 style="font-size: 20px; margin-bottom: 16px;">New private tour request</h2>
          <table style="width: 100%; border-collapse: collapse;">
            <tr><td style="padding: 8px 0; color: #666; width: 140px;">Experience</td><td style="padding: 8px 0;"><strong>${experienceName}</strong></td></tr>
            <tr><td style="padding: 8px 0; color: #666;">Name</td><td style="padding: 8px 0;">${name}</td></tr>
            <tr><td style="padding: 8px 0; color: #666;">Email</td><td style="padding: 8px 0;"><a href="mailto:${email}">${email}</a></td></tr>
            <tr><td style="padding: 8px 0; color: #666;">Preferred dates</td><td style="padding: 8px 0;">${dates || "—"}</td></tr>
            <tr><td style="padding: 8px 0; color: #666;">Number of people</td><td style="padding: 8px 0;">${people || "—"}</td></tr>
            <tr><td style="padding: 8px 0; color: #666;">Phone</td><td style="padding: 8px 0;">${phone || "—"}${phone && canCall ? " <strong>(ok to call)</strong>" : ""}</td></tr>
            <tr><td style="padding: 8px 0; color: #666;">Topics / focus</td><td style="padding: 8px 0;">${topics || "—"}</td></tr>
            <tr><td style="padding: 8px 0; color: #666;">Notes</td><td style="padding: 8px 0;">${notes || "—"}</td></tr>
          </table>
          <p style="margin-top: 24px; color: #666; font-size: 13px;">Reply directly to this email to respond to ${name}.</p>
        </div>
      `,
    });

    // Confirmation to the enquirer
    await transporter.sendMail({
      from: `"NV & more" <${process.env.GMAIL_USER}>`,
      to: email,
      subject: `We received your request — NV & more`,
      html: `
        <div style="font-family: sans-serif; max-width: 560px; margin: 0 auto; color: #111;">
          <h2 style="font-size: 20px; margin-bottom: 8px;">Thanks for your interest!</h2>
          <p>Hi ${name},</p>
          <p>We've received your request for <strong>${experienceName}</strong> and will get back to you within a couple of days to confirm the details.</p>
          <p>If you have any questions in the meantime, reply to this email or write us at <a href="mailto:nordvestandmore@gmail.com">nordvestandmore@gmail.com</a>.</p>
          <p style="font-size: 13px; color: #666;">You can read our <a href="https://nordvestandmore.com/terms">Terms of Sale</a> on our website.</p>
          <p style="margin-top: 32px;">See you soon,<br/>Constance<br/><br/><a href="https://www.instagram.com/nordvestandmore">@nordvestandmore</a><br/><a href="https://nordvestandmore.com">nordvestandmore.com</a></p>
        </div>
      `,
    });

    return NextResponse.json({ sent: true });
  } catch (err) {
    console.error("Inquiry email error:", err);
    return NextResponse.json({ error: "Failed to send" }, { status: 500 });
  }
}
