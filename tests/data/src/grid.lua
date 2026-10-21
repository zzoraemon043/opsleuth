local Grid = {}
Grid.__index = Grid

function Grid.new(w, h, fill)
  local cells = {}
  for y = 1, h do
    local row = {}
    for x = 1, w do row[x] = fill end
    cells[y] = row
  end
  return setmetatable({ w = w, h = h, cells = cells }, Grid)
end

function Grid:get(x, y)
  if x < 1 or y < 1 or x > self.w or y > self.h then return nil end
  return self.cells[y][x]
end

function Grid:set(x, y, v)
  if self:get(x, y) == nil and v == nil then return end
  self.cells[y][x] = v
end

function Grid:neighbors(x, y)
  local out = {}
  for dy = -1, 1 do
    for dx = -1, 1 do
      if not (dx == 0 and dy == 0) then
        local v = self:get(x + dx, y + dy)
        if v ~= nil then out[#out + 1] = v end
      end
    end
  end
  return out
end

function Grid:step()
  local nxt = Grid.new(self.w, self.h, false)
  for y = 1, self.h do
    for x = 1, self.w do
      local alive = 0
      for _, v in ipairs(self:neighbors(x, y)) do
        if v then alive = alive + 1 end
      end
      local cur = self:get(x, y)
      nxt:set(x, y, alive == 3 or (cur and alive == 2))
    end
  end
  return nxt
end

function Grid:path(sx, sy, tx, ty)
  local frontier = { { sx, sy } }
  local seen = { [sy * 1000 + sx] = true }
  local steps = 0
  while #frontier > 0 do
    local nextf = {}
    for _, p in ipairs(frontier) do
      if p[1] == tx and p[2] == ty then return steps end
      for _, d in ipairs({ { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } }) do
        local nx, ny = p[1] + d[1], p[2] + d[2]
        local key = ny * 1000 + nx
        if not seen[key] and self:get(nx, ny) == false then
          seen[key] = true
          nextf[#nextf + 1] = { nx, ny }
        end
      end
    end
    frontier = nextf
    steps = steps + 1
  end
  return -1
end

function Grid:render()
  local rows = {}
  for y = 1, self.h do
    local line = {}
    for x = 1, self.w do line[x] = self.cells[y][x] and "#" or "." end
    rows[y] = table.concat(line)
  end
  return table.concat(rows, "|")
end

return Grid
