"use client";

import { useState } from "react";
import { Loader2, X } from "lucide-react";

type Props = {
  experienceName: string;
  onClose: () => void;
};

export default function InquiryForm({ experienceName, onClose }: Props) {
  const [form, setForm] = useState({ name: "", email: "", dates: "", people: "", topics: "", notes: "" });
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const set = (field: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/inquire", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ experienceName, ...form }),
      });
      if (!res.ok) throw new Error("Failed to send");
      setSent(true);
    } catch {
      setError("Something went wrong. Please email us directly at nordvestandmore@gmail.com");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center bg-black/50 p-4">
      <div className="bg-white w-full max-w-lg border border-black max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-black">
          <p className="text-xs font-semibold tracking-widest uppercase">Request a private tour</p>
          <button onClick={onClose}><X size={16} /></button>
        </div>

        {sent ? (
          <div className="p-6 text-center">
            <p className="text-lg font-medium mb-2">Request sent!</p>
            <p className="text-sm text-gray-500 mb-6">We'll be in touch within a couple of days to confirm the details.</p>
            <button onClick={onClose} className="text-xs font-semibold tracking-widest uppercase border border-black px-6 py-3 hover:bg-black hover:text-white transition-colors">
              Close
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="p-6 space-y-4">
            <p className="text-sm text-gray-500 mb-2">{experienceName}</p>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-semibold tracking-widest uppercase text-gray-400 block mb-1">Name *</label>
                <input required value={form.name} onChange={set("name")} className="w-full border border-black px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-black" />
              </div>
              <div>
                <label className="text-xs font-semibold tracking-widest uppercase text-gray-400 block mb-1">Email *</label>
                <input required type="email" value={form.email} onChange={set("email")} className="w-full border border-black px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-black" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-semibold tracking-widest uppercase text-gray-400 block mb-1">Preferred dates & times</label>
                <input value={form.dates} onChange={set("dates")} placeholder="e.g. Late March, weekends" className="w-full border border-black px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-black placeholder:text-gray-300" />
              </div>
              <div>
                <label className="text-xs font-semibold tracking-widest uppercase text-gray-400 block mb-1">Number of people</label>
                <input value={form.people} onChange={set("people")} placeholder="e.g. 4" className="w-full border border-black px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-black placeholder:text-gray-300" />
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold tracking-widest uppercase text-gray-400 block mb-1">Tell us about your request</label>
              <textarea value={form.notes} onChange={set("notes")} rows={4} placeholder="Tell us a bit about what you're interested in — any topics, areas of focus, group size, or anything else we should know" className="w-full border border-black px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-black placeholder:text-gray-300 resize-none" />
            </div>

            {error && <p className="text-red-500 text-sm">{error}</p>}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-4 bg-black text-white text-xs font-semibold tracking-widest uppercase hover:bg-gray-900 transition-colors flex items-center justify-center gap-2 disabled:opacity-60"
            >
              {loading ? <><Loader2 size={14} className="animate-spin" /> Sending…</> : "Send request"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
