import { useEffect, useId, useState } from "react";

type Preview = { source: string; image?: string; failed?: boolean };

export function MermaidPreview({ source }: { source: string }) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [preview, setPreview] = useState<Preview>();

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(() => {
      void (async () => {
        // Load the renderer only for diagrams, and only in the browser.
        const { default: mermaid } = await import("mermaid");
        if (cancelled) return;
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict", suppressErrorRendering: true });
        const container = document.createElement("div");
        container.style.position = "absolute";
        container.style.visibility = "hidden";
        document.body.appendChild(container);
        try {
          const { svg } = await mermaid.render(`mermaid-${id}`, source, container);
          if (!cancelled) {
            // Mermaid's HTML labels can contain HTML void tags (such as <br>).
            // Serialize them as XML so the SVG also works as an image resource.
            const element = new DOMParser().parseFromString(svg, "text/html").querySelector("svg");
            if (!element) throw new Error("Mermaid did not return an SVG");
            // HTML namespace declarations are recreated by the XML serializer.
            element.querySelectorAll("[xmlns]").forEach((label) => label.removeAttribute("xmlns"));
            const image = new XMLSerializer().serializeToString(element);
            // An image isolates SVG styles and links from the surrounding editor.
            setPreview({ source, image: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(image)}` });
          }
        } finally {
          container.remove();
        }
      })().catch(() => {
        if (!cancelled) setPreview({ source, failed: true });
      });
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [id, source]);

  const current = preview?.source === source ? preview : undefined;
  return (
    <div contentEditable={false} className="my-2 overflow-auto rounded-lg border border-subtle bg-white p-4">
      {current?.image ? (
        <img src={current.image} alt="Mermaid diagram" className="mx-auto h-auto w-full" />
      ) : current?.failed ? (
        <>
          <p role="status" className="text-sm text-gray-700">
            Unable to render diagram. Select Show source to edit it.
          </p>
          <pre className="text-gray-900 whitespace-pre-wrap">{source}</pre>
        </>
      ) : (
        <p role="status" className="text-sm text-gray-700">
          Rendering diagram…
        </p>
      )}
    </div>
  );
}
