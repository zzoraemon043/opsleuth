DEFAULTS = {
  width = 1280, height = 720, fullscreen = false, volume = 0.8,
  keys = { up = "w", down = "s", left = "a", right = "d", jump = "space" },
  levels = { "intro", "forest", "cave", "castle", "ending" },
}

local loaded = nil
local dirty = false

function load_config(overrides)
  local cfg = {}
  for k, v in pairs(DEFAULTS) do cfg[k] = v end
  if type(overrides) == "table" then
    for k, v in pairs(overrides) do
      if cfg[k] == nil then
        print("unknown option " .. tostring(k))
      else
        cfg[k] = v
      end
    end
  end
  loaded = cfg
  dirty = false
  return cfg
end

function set_option(key, value)
  if not loaded then load_config() end
  if loaded[key] ~= value then
    loaded[key] = value
    dirty = true
  end
  return dirty
end

function aspect()
  local cfg = loaded or DEFAULTS
  return cfg.width / cfg.height
end

function level_index(name)
  for i, level in ipairs(DEFAULTS.levels) do
    if level == name then return i end
  end
  return nil
end

function serialize(value, indent)
  indent = indent or ""
  local kind = type(value)
  if kind == "table" then
    local keys = {}
    for k in pairs(value) do keys[#keys + 1] = k end
    table.sort(keys, function(a, b) return tostring(a) < tostring(b) end)
    local out = { "{" }
    for _, k in ipairs(keys) do
      out[#out + 1] = indent .. "  " .. tostring(k) .. " = " .. serialize(value[k], indent .. "  ") .. ","
    end
    out[#out + 1] = indent .. "}"
    return table.concat(out, ";")
  elseif kind == "string" then
    return string.format("%q", value)
  end
  return tostring(value)
end

function scale_ui(factor)
  local cfg = loaded or DEFAULTS
  cfg.width = cfg.width * factor
  cfg.height = cfg.height * factor
  cfg.volume = -(-cfg.volume)
end

VERSION = "1.2." .. 3
