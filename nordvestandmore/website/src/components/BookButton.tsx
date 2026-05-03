"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";

type Props = {
  eventId: string;
  eventSlug: string;
  eventTitle: string;
  eventDate?: string;
  price: number;
  currency: string;
  stripeProductId?: string;
  soldOut: boolean;
  cancellationHours?: number;
  requiresConfirmation?: boolean;
};

export default function BookButton({
  eventId,
  eventSlug,
  eventTitle,
  eventDate,
  price,
  currency,
  stripeProductId,
  soldOut,
  cancellationHours,
  requiresConfirmation,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleBook() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ eventId, eventSlug, eventTitle, eventDate, price, currency, stripeProductId, cancellationHours, requiresConfirmation }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Something went wrong");
      window.location.href = data.url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setLoading(false);
    }
  }

  if (soldOut) {
    return (
      <button
        disabled
        className="w-full py-4 bg-gray-100 text-gray-400 text-sm font-semibold tracking-widest uppercase cursor-not-allowed"
      >
        Sold out
      </button>
    );
  }

  return (
    <>
      <button
        onClick={handleBook}
        disabled={loading}
        className="w-full py-4 bg-black text-white text-sm font-semibold tracking-widest uppercase hover:bg-gray-900 transition-colors flex items-center justify-center gap-2 disabled:opacity-60"
      >
        {loading ? (
          <>
            <Loader2 size={14} className="animate-spin" />
            Redirecting to payment…
          </>
        ) : (
          price === 0
            ? "Reserve my spot — Free"
            : requiresConfirmation
            ? `Reserve my spot — ${price} ${currency}`
            : `Book now — ${price} ${currency}`
        )}
      </button>
      {requiresConfirmation && (
        <p className="text-xs text-gray-500 mt-3 text-center">
          Your card won&apos;t be charged until we confirm this event is going ahead.
        </p>
      )}
      {error && (
        <p className="text-red-500 text-sm mt-2 text-center">{error}</p>
      )}
    </>
  );
}
