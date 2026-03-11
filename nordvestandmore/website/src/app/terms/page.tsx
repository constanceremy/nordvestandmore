import { getPageBlocks } from "@/lib/notion";
import NotionBlocks from "@/components/NotionBlocks";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Sale | NV & more",
  description: "Terms of sale for bookings made through NV & more.",
};

export const revalidate = 3600;

export default async function TermsPage() {
  const blocks = await getPageBlocks(process.env.NOTION_TC_PAGE_ID!);

  return (
    <div className="max-w-3xl mx-auto px-6 py-16">
      <div className="mb-12 border-b border-black pb-10">
        <p className="text-xs font-semibold tracking-widest uppercase text-gray-400 mb-3">
          Legal
        </p>
        <h1 className="text-5xl md:text-7xl" style={{ fontFamily: "DM Serif Display, serif" }}>
          Terms of Sale
        </h1>
      </div>

      <div className="prose prose-sm max-w-none">
        <NotionBlocks blocks={blocks} />
      </div>
    </div>
  );
}
