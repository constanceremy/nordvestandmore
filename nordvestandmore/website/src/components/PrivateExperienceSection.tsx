"use client";

import { useState } from "react";
import { MapPin } from "lucide-react";
import InquiryForm from "./InquiryForm";
import type { Experience } from "@/lib/notion";

export default function PrivateExperienceSection({ experiences }: { experiences: Experience[] }) {
  const [selected, setSelected] = useState<string | null>(null);

  if (experiences.length === 0) return null;

  const active = experiences.find((e) => e.name === selected) ?? null;

  return (
    <>
      <div className="mt-20 border-t border-black pt-12">
        <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-3">
          Private & on request
        </p>
        <h2 className="text-3xl md:text-4xl mb-2" style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}>
          Book a private experience
        </h2>
        <p className="text-sm text-gray-500 max-w-lg leading-relaxed mb-10">
          These experiences can be arranged at a time that works for you and your group. Send a request and we'll get back to you within a couple of days.
        </p>

        <div className="divide-y divide-black">
          {experiences.map((exp) => (
            <div key={exp.id} className="py-8 grid grid-cols-1 md:grid-cols-[1fr_auto] gap-6 items-center">
              <div className="min-w-0">
                {exp.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-1">
                    {exp.tags.slice(0, 2).map((tag) => (
                      <span key={tag} className="text-xs font-semibold tracking-widest uppercase border border-black px-2 py-0.5">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                <h3 className="text-xl md:text-2xl font-medium mt-1 leading-snug">{exp.name}</h3>
                {exp.shortDescription && (
                  <p className="text-sm text-gray-500 mt-1">{exp.shortDescription}</p>
                )}
                <div className="flex flex-wrap items-center gap-4 mt-2 text-sm text-gray-500">
                  {exp.location && (
                    <span className="flex items-center gap-1"><MapPin size={12} />{exp.location}</span>
                  )}
                  {exp.duration && (
                    <span>{exp.duration}</span>
                  )}
                  {exp.priceLabel ? (
                    <span className="font-medium">{exp.priceLabel}</span>
                  ) : exp.price > 0 ? (
                    <span className="font-medium">{exp.price} {exp.currency}</span>
                  ) : null}
                </div>
              </div>

              <button
                onClick={() => setSelected(exp.name)}
                className="shrink-0 text-xs font-semibold tracking-widest uppercase border border-black px-6 py-3 hover:bg-black hover:text-white transition-colors"
              >
                Request a private tour
              </button>
            </div>
          ))}
        </div>
      </div>

      {active && (
        <InquiryForm experienceName={active.name} onClose={() => setSelected(null)} />
      )}
    </>
  );
}
