local Inventory = {}
Inventory.__index = Inventory

local MAX_STACK = 99
local slots_per_page = 24

function Inventory.new(pages)
  local self = setmetatable({}, Inventory)
  self.items = {}
  self.capacity = (pages or 1) * slots_per_page
  self.gold = 0
  return self
end

function Inventory:count(id)
  local total = 0
  for _, stack in pairs(self.items) do
    if stack.id == id then total = total + stack.n end
  end
  return total
end

function Inventory:add(id, n)
  n = n or 1
  for _, stack in pairs(self.items) do
    if stack.id == id and stack.n < MAX_STACK then
      local room = MAX_STACK - stack.n
      local moved = n < room and n or room
      stack.n = stack.n + moved
      n = n - moved
      if n <= 0 then return true end
    end
  end
  while n > 0 do
    if #self.items >= self.capacity then return false, "full" end
    local put = math.min(n, MAX_STACK)
    self.items[#self.items + 1] = { id = id, n = put }
    n = n - put
  end
  return true
end

function Inventory:remove(id, n)
  if self:count(id) < n then return false end
  for i = #self.items, 1, -1 do
    local stack = self.items[i]
    if stack.id == id then
      local take = math.min(stack.n, n)
      stack.n = stack.n - take
      n = n - take
      if stack.n == 0 then table.remove(self.items, i) end
      if n == 0 then break end
    end
  end
  return true
end

function Inventory:sort(by)
  by = by or "id"
  table.sort(self.items, function(a, b)
    if a[by] ~= b[by] then return a[by] < b[by] end
    return a.n > b.n
  end)
end

function Inventory:describe()
  local parts = {}
  for i, stack in ipairs(self.items) do
    parts[#parts + 1] = string.format("%d:%s x%d", i, tostring(stack.id), stack.n)
  end
  return table.concat(parts, ", ") .. " | gold " .. self.gold
end

function Inventory:pay(cost)
  if not cost or cost <= 0 then return true end
  if self.gold < cost then return false end
  self.gold = self.gold - cost
  return true
end

function Inventory:pages()
  return math.ceil(#self.items / slots_per_page)
end

return Inventory
