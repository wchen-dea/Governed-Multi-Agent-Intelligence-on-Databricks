import { memo } from "react";

function MessageMarkdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const blocks: JSX.Element[] = [];
  let table: string[] = [];
  let paragraph: string[] = [];
  const flushParagraph = () => {
    const content = paragraph.join("\n").trim();
    if (content) {
      blocks.push(
        <p key={`p-${blocks.length}`}>
          {content.split(/(\[[0-9]+\])/g).map((part, index) =>
            part.match(/^\[[0-9]+\]$/) ? (
              <a
                href={`#citation-${part.slice(1, -1)}`}
                className="citation"
                key={index}
              >
                {part}
              </a>
            ) : (
              part
            ),
          )}
        </p>,
      );
    }
    paragraph = [];
  };
  const flushTable = () => {
    const rows = table.filter((line) => !/^\s*\|?\s*[-| ]+\s*$/.test(line));
    if (rows.length)
      blocks.push(
        <table key={`table-${blocks.length}`}>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {row
                  .split("|")
                  .map((cell) => cell.trim())
                  .filter(
                    (cell, index, cells) =>
                      !(index === 0 && cell === "") &&
                      !(index === cells.length - 1 && cell === ""),
                  )
                  .map((cell, index) => (
                    <td key={index}>{cell}</td>
                  ))}
              </tr>
            ))}
          </tbody>
        </table>,
      );
    table = [];
  };
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      flushParagraph();
      flushTable();
      continue;
    }
    const heading = trimmed.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushTable();
      const Tag = `h${heading[1].length}` as "h1" | "h2" | "h3";
      blocks.push(<Tag key={`h-${blocks.length}`}>{heading[2]}</Tag>);
      continue;
    }
    if (trimmed.includes("|")) {
      flushParagraph();
      table.push(line);
    } else {
      flushTable();
      paragraph.push(line);
    }
  }
  flushParagraph();
  flushTable();
  return <div className="rich-text">{blocks}</div>;
}

export default memo(MessageMarkdown);
