local handlers = {}
local queue = {}
local log = {}

local function on(name, fn)
  local list = handlers[name]
  if not list then
    list = {}
    handlers[name] = list
  end
  list[#list + 1] = fn
  return function()
    for i = #list, 1, -1 do
      if list[i] == fn then table.remove(list, i) end
    end
  end
end

local function emit(name, ...)
  local list = handlers[name]
  if not list then return 0 end
  local fired = 0
  for _, fn in ipairs(list) do
    local ok, err = pcall(fn, ...)
    if ok then fired = fired + 1 else log[#log + 1] = name .. ": " .. tostring(err) end
  end
  return fired
end

local function defer(name, ...)
  queue[#queue + 1] = { name = name, n = select("#", ...), ... }
end

local function flush()
  local pending = queue
  queue = {}
  local total = 0
  for i = 1, #pending do
    local e = pending[i]
    total = total + emit(e.name, unpack(e, 1, e.n))
  end
  return total
end

local function once(name, fn)
  local off
  off = on(name, function(...)
    off()
    return fn(...)
  end)
  return off
end

local function counter()
  local n = 0
  return function(step) n = n + (step or 1); return n end
end

local function retry(times, fn, ...)
  for attempt = 1, times do
    local ok, result = pcall(fn, ...)
    if ok then return result, attempt end
  end
  return nil, times
end

local function pipe(...)
  local fns = { ... }
  return function(value)
    for i = 1, #fns do value = fns[i](value) end
    return value
  end
end

local function call_last(fn, ...) return fn(...) end

local function getters(n)
  local out = {}
  for i = 1, n do
    do
      local captured = i * 2
      out[i] = function() return captured end
    end
    if i > 8 then break end
  end
  return out
end

local function big_table()
  return { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
           21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38,
           39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55 }
end

return { on = on, emit = emit, defer = defer, flush = flush, once = once,
         counter = counter, retry = retry, pipe = pipe, call_last = call_last,
         big_table = big_table, getters = getters, log = log }
