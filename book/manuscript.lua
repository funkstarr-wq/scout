-- Pandoc filter used by scripts/build_book.py to make the EPUB from the Word manuscript.
--
-- The manuscript is designed in Word with named paragraph styles. For the EPUB:
--   * "Source Code" paragraphs become proper code blocks.
--   * The cover page, the typed title block, the typed contents list and the decorative rules
--     are dropped: the EPUB has its own cover, title page and contents.
--   * Boxes and labels (exercises, checkpoints, part and chapter openers, the copyright page)
--     keep their content, in a <div> named after the style, so epub.css can style them.

local DROP = {
  ["Cover Page"] = true, ["Book Title"] = true, ["Book Subtitle"] = true, ["Book Author"] = true,
  ["Contents Title"] = true, ["TOC Entry"] = true, ["TOC Part"] = true,
  ["Opener Rule"] = true, ["Section Rule"] = true, ["Review Rule"] = true, ["Part Spacer"] = true,
}
local PLAIN = { ["Body Text"] = true, ["First Paragraph"] = true, ["Normal"] = true, ["Captioned Figure"] = true,
                ["Image Caption"] = true }

local function slug(name)
  return (name:lower():gsub("[^%w]+", "-"))
end

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
  local style = span.attributes["custom-style"]
  if style == "Fig Num" then
    return pandoc.Strong(span.content)
  end
  if style then
    return span.content
  end
end

function Div(div)
  local style = div.attributes["custom-style"]
  if not style then return nil end
  if DROP[style] then return {} end
  if style == "Source Code" then
    local lines = {}
    for _, block in ipairs(div.content) do
      if block.t == "Para" or block.t == "Plain" then lines[#lines + 1] = as_text(block.content) end
    end
    return pandoc.CodeBlock(table.concat(lines, "\n"))
  end
  if PLAIN[style] then return div.content end
  div.attributes["custom-style"] = nil
  div.classes:insert(slug(style))
  return div
end

function Figure(figure)
  figure.attributes["custom-style"] = nil
  return figure
end

function Table(table)
  table.attributes["custom-style"] = nil
  return table
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
  doc.blocks = merged
  return doc
end
