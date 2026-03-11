import type { BlockObjectResponse } from "@notionhq/client/build/src/api-endpoints";

type Block = BlockObjectResponse | { object: string };

function RichText({ text }: { text: Array<{ plain_text: string; href?: string | null; annotations?: { bold?: boolean; italic?: boolean; code?: boolean; strikethrough?: boolean } }> }) {
  return (
    <>
      {text.map((t, i) => {
        let node: React.ReactNode = t.plain_text;
        if (t.annotations?.bold) node = <strong key={i}>{node}</strong>;
        if (t.annotations?.italic) node = <em key={i}>{node}</em>;
        if (t.annotations?.code) node = <code key={i} className="bg-gray-100 px-1 py-0.5 rounded text-sm font-mono">{node}</code>;
        if (t.annotations?.strikethrough) node = <s key={i}>{node}</s>;
        if (t.href) node = <a key={i} href={t.href} className="underline" target="_blank" rel="noopener noreferrer">{node}</a>;
        return <span key={i}>{node}</span>;
      })}
    </>
  );
}

export default function NotionBlocks({ blocks }: { blocks: Block[] }) {
  return (
    <div className="space-y-4">
      {blocks.map((block) => {
        if (!("type" in block)) return null;
        const b = block as BlockObjectResponse;

        switch (b.type) {
          case "paragraph":
            return (
              <p key={b.id} className="text-gray-700 leading-relaxed">
                <RichText text={b.paragraph.rich_text as Parameters<typeof RichText>[0]["text"]} />
              </p>
            );

          case "heading_1":
            return (
              <h2 key={b.id} className="text-3xl mt-10 mb-4" style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}>
                <RichText text={b.heading_1.rich_text as Parameters<typeof RichText>[0]["text"]} />
              </h2>
            );

          case "heading_2":
            return (
              <h3 key={b.id} className="text-2xl mt-8 mb-3" style={{ fontFamily: "Neue Haas Grotesk Display Pro, Helvetica, sans-serif" }}>
                <RichText text={b.heading_2.rich_text as Parameters<typeof RichText>[0]["text"]} />
              </h3>
            );

          case "heading_3":
            return (
              <h4 key={b.id} className="text-xl font-semibold mt-6 mb-2">
                <RichText text={b.heading_3.rich_text as Parameters<typeof RichText>[0]["text"]} />
              </h4>
            );

          case "bulleted_list_item":
            return (
              <li key={b.id} className="ml-4 list-disc text-gray-700 leading-relaxed">
                <RichText text={b.bulleted_list_item.rich_text as Parameters<typeof RichText>[0]["text"]} />
              </li>
            );

          case "numbered_list_item":
            return (
              <li key={b.id} className="ml-4 list-decimal text-gray-700 leading-relaxed">
                <RichText text={b.numbered_list_item.rich_text as Parameters<typeof RichText>[0]["text"]} />
              </li>
            );

          case "quote":
            return (
              <blockquote key={b.id} className="border-l-4 border-black pl-4 italic text-gray-600 my-6">
                <RichText text={b.quote.rich_text as Parameters<typeof RichText>[0]["text"]} />
              </blockquote>
            );

          case "divider":
            return <hr key={b.id} className="border-black my-8" />;

          case "image": {
            const url =
              b.image.type === "external"
                ? b.image.external.url
                : b.image.file.url;
            const caption =
              b.image.caption?.map((c) => c.plain_text).join("") || "";
            return (
              <figure key={b.id} className="my-8">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={url} alt={caption} className="w-full grayscale border border-black" />
                {caption && (
                  <figcaption className="text-xs text-gray-400 text-center mt-2">
                    {caption}
                  </figcaption>
                )}
              </figure>
            );
          }

          case "code":
            return (
              <pre key={b.id} className="bg-gray-100 p-4 overflow-x-auto text-sm font-mono border border-gray-200 my-4">
                <code>
                  {b.code.rich_text.map((t) => t.plain_text).join("")}
                </code>
              </pre>
            );

          default:
            return null;
        }
      })}
    </div>
  );
}
