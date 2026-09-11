import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MermaidPreview } from "./mermaid-preview";

const { render, initialize } = vi.hoisted(() => ({ render: vi.fn(), initialize: vi.fn() }));
vi.mock("mermaid", () => ({ default: { render, initialize } }));

let host: HTMLDivElement;
let root: Root;
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  vi.useFakeTimers();
  vi.clearAllMocks();
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});
afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  vi.useRealTimers();
});
async function show(source: string) {
  await act(async () => root.render(<MermaidPreview source={source} />));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(250);
  });
}

it("renders an isolated SVG image and removes the temporary render container", async () => {
  render.mockResolvedValue({ svg: '<svg xmlns="http://www.w3.org/2000/svg"><text>Hello</text></svg>' });
  await show("graph LR; A-->B");
  expect(host.querySelector("img")?.getAttribute("src")).toContain("data:image/svg+xml");
  expect(host.querySelector("svg")).toBeNull();
  expect(initialize).toHaveBeenCalledWith(expect.objectContaining({ securityLevel: "strict", startOnLoad: false }));
  expect(document.body.children.length).toBe(1);
});

it("keeps malformed diagram source readable and cleans up after failure", async () => {
  render.mockRejectedValue(new Error("Invalid syntax"));
  await show("broken diagram <script>");
  expect(host.textContent).toContain("Unable to render diagram");
  expect(host.querySelector("pre")?.textContent).toBe("broken diagram <script>");
  expect(host.querySelector("script")).toBeNull();
  expect(document.body.children.length).toBe(1);
});

it("serializes multiline HTML labels as valid SVG XML", async () => {
  render.mockResolvedValue({
    svg: '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject><div xmlns="http://www.w3.org/1999/xhtml"><p>First<br>Second</p></div></foreignObject></svg>',
  });
  await show("graph LR; A[First\\nSecond]");
  const image = host.querySelector("img")!;
  const svg = decodeURIComponent(image.src.slice(image.src.indexOf(",") + 1));
  const document = new DOMParser().parseFromString(svg, "image/svg+xml");
  expect(document.querySelector("parsererror")).toBeNull();
  expect(document.querySelector("p")?.textContent).toBe("FirstSecond");
});

it("ignores stale async results after the source changes", async () => {
  let finishFirst!: (value: { svg: string }) => void;
  render.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finishFirst = resolve;
      })
  );
  render.mockResolvedValue({ svg: "<svg>new</svg>" });
  await show("old source");
  await show("new source");
  await act(async () => finishFirst({ svg: "<svg>old</svg>" }));
  expect(decodeURIComponent(host.querySelector("img")!.src)).toContain(">new</svg>");
  expect(document.body.children.length).toBe(1);
});

it("cancels rendering when unmounted during the debounce", async () => {
  await act(async () => root.render(<MermaidPreview source="graph LR; A-->B" />));
  await act(async () => root.render(null));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(250);
  });
  expect(render).not.toHaveBeenCalled();
});
