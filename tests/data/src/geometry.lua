local Vec = {}
Vec.__index = Vec

local function new(x, y)
  return setmetatable({ x = x or 0, y = y or 0 }, Vec)
end

function Vec.__add(a, b) return new(a.x + b.x, a.y + b.y) end
function Vec.__sub(a, b) return new(a.x - b.x, a.y - b.y) end
function Vec.__mul(a, s) return new(a.x * s, a.y * s) end
function Vec.__div(a, s) return new(a.x / s, a.y / s) end
function Vec.__unm(a) return new(-a.x, -a.y) end
function Vec.__eq(a, b) return a.x == b.x and a.y == b.y end
function Vec.__tostring(a) return "(" .. a.x .. ", " .. a.y .. ")" end

function Vec:length() return math.sqrt(self.x ^ 2 + self.y ^ 2) end
function Vec:normalized()
  local len = self:length()
  if len == 0 then return new(0, 0) end
  return self / len
end
function Vec:angle() return math.atan2(self.y, self.x) * 180 / math.pi end
function Vec:rotate(deg)
  local r = deg * math.pi / 180
  local c, s = math.cos(r), math.sin(r)
  return new(self.x * c - self.y * s, self.x * s + self.y * c)
end

local function wrap(angle)
  angle = angle % 360
  if angle < 0 then angle = angle + 360 end
  return angle
end

local function polygon_area(points)
  local area = 0
  local n = #points
  for i = 1, n do
    local j = i % n + 1
    area = area + points[i].x * points[j].y - points[j].x * points[i].y
  end
  return math.abs(area) / 2
end

local function centroid(points)
  local sx, sy = 0, 0
  for _, p in ipairs(points) do
    sx, sy = sx + p.x, sy + p.y
  end
  return new(sx / #points, sy / #points)
end

local function clamp(v, lo, hi)
  if v < lo then return lo elseif v > hi then return hi end
  return v
end

local function lerp(a, b, t) return a + (b - a) * clamp(t, 0, 1) end

local function grid_snap(v, size) return math.floor(v / size + 0.5) * size end

local function inside(px, py, x, y, w, h)
  return px >= x and px < x + w and py >= y and py < y + h
end

return { new = new, wrap = wrap, area = polygon_area, centroid = centroid,
         clamp = clamp, lerp = lerp, snap = grid_snap, inside = inside, Vec = Vec }
