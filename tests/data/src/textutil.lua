local M = {}

function M.split(s, sep)
  sep = sep or ","
  local out = {}
  local start = 1
  while true do
    local i, j = string.find(s, sep, start, true)
    if not i then
      out[#out + 1] = string.sub(s, start)
      break
    end
    out[#out + 1] = string.sub(s, start, i - 1)
    start = j + 1
  end
  return out
end

function M.trim(s) return (s:gsub("^%s+", ""):gsub("%s+$", "")) end

function M.pad(s, width, ch)
  s = tostring(s)
  ch = ch or " "
  if #s >= width then return s end
  return string.rep(ch, width - #s) .. s
end

function M.wrap(text, width)
  local lines, line = {}, ""
  for word in text:gmatch("%S+") do
    if #line + #word + 1 > width and #line > 0 then
      lines[#lines + 1] = line
      line = word
    elseif #line == 0 then
      line = word
    else
      line = line .. " " .. word
    end
  end
  if #line > 0 then lines[#lines + 1] = line end
  return lines
end

function M.count(s, pattern)
  local n = 0
  for _ in s:gmatch(pattern) do n = n + 1 end
  return n
end

function M.format_time(seconds)
  local h = math.floor(seconds / 3600)
  local m = math.floor(seconds % 3600 / 60)
  local s = seconds % 60
  return string.format("%02d:%02d:%02d", h, m, s)
end

function M.is_blank(s) return s == nil or not s:find("%S") end

function M.join(list, sep, last)
  if #list == 0 then return "" end
  if #list == 1 or not last then return table.concat(list, sep) end
  return table.concat(list, sep, 1, #list - 1) .. last .. list[#list]
end

local entities = { ["&"] = "&amp;", ["<"] = "&lt;", [">"] = "&gt;" }

function M.escape(s)
  return (s:gsub("[&<>]", entities))
end

function M.title(s)
  return (s:gsub("(%a)([%w]*)", function(first, rest)
    return first:upper() .. rest:lower()
  end))
end

return M
