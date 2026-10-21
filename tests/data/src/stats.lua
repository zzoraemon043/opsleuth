local stats = {}

function stats.sum(t)
  local s = 0
  for i = 1, #t do s = s + t[i] end
  return s
end

function stats.mean(t) return #t > 0 and stats.sum(t) / #t or 0 end

function stats.variance(t)
  local m = stats.mean(t)
  local acc = 0
  for i = 1, #t do acc = acc + (t[i] - m) ^ 2 end
  return acc / math.max(#t - 1, 1)
end

function stats.median(t)
  local copy = { unpack(t) }
  table.sort(copy)
  local n = #copy
  if n % 2 == 1 then return copy[(n + 1) / 2] end
  return (copy[n / 2] + copy[n / 2 + 1]) / 2
end

function stats.histogram(t, buckets, lo, hi)
  local h = {}
  for i = 1, buckets do h[i] = 0 end
  local width = (hi - lo) / buckets
  for _, v in ipairs(t) do
    local b = math.floor((v - lo) / width) + 1
    if b >= 1 and b <= buckets then h[b] = h[b] + 1 end
  end
  return h
end

function stats.percent(part, whole)
  if whole == 0 then return 0 end
  return math.floor(part * 10000 / whole + 0.5) / 100
end

function stats.gcd(a, b)
  while b ~= 0 do a, b = b, a % b end
  return a
end

function stats.is_prime(n)
  if n < 2 then return false end
  for d = 2, math.floor(n ^ 0.5) do
    if n % d == 0 then return false end
  end
  return true
end

function stats.compound(principal, rate, years)
  return principal * (1 + rate / 100) ^ years
end

function stats.minmax(...)
  local lo, hi = math.huge, -math.huge
  for i = 1, select("#", ...) do
    local v = select(i, ...)
    if v < lo then lo = v end
    if v > hi then hi = v end
  end
  return lo, hi
end

function stats.normalize(t)
  local lo, hi = stats.minmax(unpack(t))
  local out = {}
  for i, v in ipairs(t) do out[i] = (v - lo) / (hi - lo) end
  return out
end

return stats
