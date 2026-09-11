import { Editor } from "@tiptap/core";
import { StarterKit } from "@tiptap/starter-kit";
import { EditorMarkdown } from "../markdown";
import { expect, it } from "vitest";

const source = "flowchart TB\n  A[Browser]\n\n  subgraph App\n    B[API]\n  end\n  A --> B\n";
const html = `<h2>Architecture</h2>\n<pre><code class="language-mermaid">${source.replaceAll(">", "&gt;")}</code></pre>\n<p>After diagram</p>`;

it("keeps the full imported diagram in one code block across blank lines", () => {
  const editor = new Editor({ extensions: [StarterKit, EditorMarkdown], content: html });
  const blocks = editor.getJSON().content!.filter((node) => node.type === "codeBlock");
  expect(blocks).toHaveLength(1);
  expect(blocks[0]!.content?.map((node) => node.text).join("")).toBe(source.trimEnd());
  editor.destroy();
});

it("preserves imported code when content is refreshed or inserted", () => {
  const editor = new Editor({ extensions: [StarterKit, EditorMarkdown] });
  editor.commands.setContent(html);
  expect(editor.getJSON().content![1]!.content?.[0]?.text).toBe(source.trimEnd());
  editor.commands.setContent("<p></p>");
  editor.commands.insertContent(html);
  const block = editor.getJSON().content!.find((node) => node.type === "codeBlock");
  expect(block?.content?.[0]?.text).toBe(source.trimEnd());
  editor.destroy();
});

it("still parses fenced Markdown diagrams and preserves literal HTML inside them", () => {
  const editor = new Editor({ extensions: [StarterKit, EditorMarkdown], content: "```mermaid\n" + source + "```" });
  expect(editor.getJSON().content![0]!.content?.[0]?.text).toBe(source.trimEnd());
  editor.commands.setContent("```html\n<pre>one\n\ntwo</pre>\n```");
  expect(editor.getJSON().content![0]!.content?.[0]?.text).toBe("<pre>one\n\ntwo</pre>");
  editor.destroy();
});
