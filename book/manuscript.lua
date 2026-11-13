-- Pandoc filter used by scripts/build_book.py to turn the Word manuscript into the PDF and EPUB.
--
-- 1. Paragraphs in the manuscript's "Code" style (commands and prompts the reader types)
--    become proper code blocks, keeping their line breaks.
-- 2. The manuscript's own title block (title, subtitle, author, date line) is removed,
--    because the book gets a real cover and title page instead.

local function as_text(inlines)
  local out = {}
  for _, el in ipairs(inlines) do
    if el.t == "LineBreak" or el.t == "SoftBreak" then
      out[#out + 1] = "\n"
    elseif el.t == "Space" then
      out[#out + 1] = " "
    else
      out[#out + 1] = pandoc.utils.stringify(el)
    end
  end
  return table.concat(out)
end

function Span(span)
  -- Words in the manuscript's "Code Char" style (file names, commands in a sentence).
  if span.attributes["custom-style"] == "Code Char" then
    return pandoc.Code(pandoc.utils.stringify(span))
  end
  if span.attributes["custom-style"] then
    return span.content
  end
end

function Div(div)
  if div.attributes["custom-style"] == "Code" then
    local lines = {}
    for _, block in ipairs(div.content) do
      if block.t == "Para" or block.t == "Plain" then
        lines[#lines + 1] = as_text(block.content)
      end
    end
    return pandoc.CodeBlock(table.concat(lines, "\n"))
  end
  -- Other named styles (headings, list paragraphs) need no special treatment.
  if div.attributes["custom-style"] then
    return div.content
  end
end

function Pandoc(doc)
  -- Join code paragraphs that follow one another into a single block.
  local merged = pandoc.List()
  for _, block in ipairs(doc.blocks) do
    local last = merged[#merged]
    if block.t == "CodeBlock" and last and last.t == "CodeBlock" then
      last.text = last.text .. "\n" .. block.text
    else
      merged:insert(block)
    end
  end
  -- Drop everything before the first chapter-level heading ("Before you begin").
  local first = 1
  for i, block in ipairs(merged) do
    if block.t == "Header" and block.level == 2 then
      first = i
      break
    end
  end
  local kept = pandoc.List()
  for i = first, #merged do
    kept:insert(merged[i])
  end
  doc.blocks = kept
  return doc
end

function Table(table)
  -- Word's table style name isn't needed in the book.
  table.attributes["custom-style"] = nil
  return table
end
