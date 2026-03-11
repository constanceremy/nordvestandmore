import Link from "next/link";
import { CheckCircle } from "lucide-react";

export default function BookingSuccessPage({
  searchParams,
}: {
  searchParams: Promise<{ event?: string }>;
}) {
  return (
    <div className="max-w-lg mx-auto px-6 py-32 text-center">
      <CheckCircle size={48} className="mx-auto mb-6" />
      <h1
        className="text-4xl mb-4"
        style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}
      >
        You're booked!
      </h1>
      <p className="text-gray-500 mb-8 leading-relaxed">
        Your spot is confirmed. You'll receive a confirmation email shortly.
        We can't wait to see you!
      </p>
      <div className="flex gap-4 justify-center">
        <Link
          href="/events"
          className="inline-block bg-black text-white px-6 py-3 text-sm font-semibold tracking-widest uppercase hover:bg-gray-900 transition-colors"
        >
          More events
        </Link>
        <Link
          href="/"
          className="inline-block border border-black px-6 py-3 text-sm font-semibold tracking-widest uppercase hover:bg-black hover:text-white transition-colors"
        >
          Home
        </Link>
      </div>
    </div>
  );
}
