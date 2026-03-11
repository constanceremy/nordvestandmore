import { getPageBlocks } from "@/lib/notion";
import NotionBlocks from "@/components/NotionBlocks";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy | NV & more",
  description: "How NV & more handles your personal data.",
};

export const revalidate = 3600;

export default async function PrivacyPage() {
  const blocks = await getPageBlocks("320375efa2cc80beaa21d8119d085d55");

  return (
    <div className="max-w-3xl mx-auto px-6 py-16">
      <div className="mb-12 border-b border-black pb-10">
        <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-3">
          Legal
        </p>
        <h1 className="text-5xl md:text-7xl" style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}>
          Privacy Policy
        </h1>
      </div>

      <div className="prose prose-sm max-w-none">
        <NotionBlocks blocks={blocks} />
      </div>
    </div>
  );
}
