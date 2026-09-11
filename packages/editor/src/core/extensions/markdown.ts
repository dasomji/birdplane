import type { Content } from "@tiptap/core";
import { Markdown } from "tiptap-markdown";
import type { MarkdownStorage } from "tiptap-markdown";

function preserveHtmlCodeBlocks(content: Content): Content {
  if (typeof content !== "string" || !/^\s*<[a-z][\s\S]*>/i.test(content)) return content;
  // Markdown-it can end an enclosing HTML block at a blank line inside <pre>.
  // Character references survive Markdown parsing and become literal newlines
  // again when ProseMirror parses the resulting HTML.
  return content.replace(
    /(<pre\b[^>]*>)([\s\S]*?)(<\/pre>)/gi,
    (_match, open, body: string, close) => open + body.replace(/\r\n?|\n/g, "&#10;") + close
  );
}

type Parser = { parse: (content: Content, options?: { inline?: boolean }) => Content };

export const EditorMarkdown = Markdown.extend({
  onBeforeCreate() {
    this.editor.options.content = preserveHtmlCodeBlocks(this.editor.options.content);
    this.parent?.();
    const { parser } = this.editor.storage.markdown as MarkdownStorage & { parser: Parser };
    const parse = parser.parse.bind(parser);
    parser.parse = (content, options) => parse(preserveHtmlCodeBlocks(content), options);
  },
});
