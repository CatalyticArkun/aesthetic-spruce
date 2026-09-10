--- Renders the PyUI icons/ set (system tiles, selected variants, app icons) for one resolution
---
local love = require("love")
local state = require("state")
local paths = require("paths")
local colorUtils = require("utils.color")
local svg = require("utils.svg")
local pyuiConfig = require("utils.pyui_config")
local imageGenerator = require("utils.image_generator")
local system = require("utils.system")
local fail = require("utils.fail")
local skinSpec = require("spruce.skin_spec")
local glyphs = require("spruce.system_glyphs")

local iconRenderer = {}

-- App icons not in the SPRUCE reference set but worth theming (keyed by the app's config.json icon name)
iconRenderer.EXTRA_APP_ICONS = { "aestheticspruce" }

-- Glyphs come from the Lucide glyph set; a few names only exist in the smaller UI set
local function glyphPath(name)
	local glyph = paths.UI_ICON_PNG_DIR .. "/lucide/glyph/" .. name .. ".png"
	if system.isFile(glyph) then
		return glyph
	end
	return paths.UI_ICON_PNG_DIR .. "/lucide/ui/" .. name .. ".png"
end

-- A landscape handheld drawn in Lucide's idiom (2/24 stroke, rounded joins): body, screen, d-pad, two buttons.
-- `size` is the glyph box, centred on (cx, cy); the body spans the box width at 0.58 of its height.
-- Device glyphs are drawn here rather than taken from Lucide so they can carry a heavier stroke
-- (2.6/24 instead of Lucide's 2/24), which reads better on a 60 px tile.
local DEVICE_STROKE = 2.6 / 24

-- Landscape handheld: body, screen, d-pad, two buttons. Proportions are chosen so every gap is at
-- least ~0.7 stroke at the smallest tile (57 px glyph box at 640x480).
local function drawHandheldGlyph(size, cx, cy, color)
	local stroke = size * (1.7 / 24) -- lighter than the TV so the screen gets room
	local bw, bh = size, size * 0.56
	local x, y = cx - bw / 2, cy - bh / 2
	love.graphics.push("all")
	love.graphics.setColor(color)
	love.graphics.setLineWidth(stroke)
	love.graphics.setLineJoin("bevel")
	love.graphics.setLineStyle("smooth")
	love.graphics.rectangle("line", x, y, bw, bh, bh * 0.3, bh * 0.3)
	-- screen: narrow, centred slightly right so the d-pad column is clear
	local sw, sh = bw * 0.31, bh * 0.54
	local sx = cx - sw / 2 + bw * 0.02
	love.graphics.rectangle("line", sx, cy - sh / 2, sw, sh, stroke * 0.7, stroke * 0.7)
	-- d-pad cross: thinner and longer than the body stroke so it stays a cross at 57 px
	local dx, arm = x + bw * 0.19, bh * 0.17 -- arms 10% shorter
	love.graphics.setLineWidth(stroke * 0.73) -- unchanged in absolute terms after the body stroke went to 1.7/24
	love.graphics.line(dx - arm, cy, dx + arm, cy)
	love.graphics.line(dx, cy - arm, dx, cy + arm)
	love.graphics.setLineWidth(stroke)
	-- two buttons in the right column
	local r = stroke * 0.56 -- 10% smaller than before the body stroke went to 1.7/24
	local bx = x + bw * 0.81
	love.graphics.circle("fill", bx - r * 0.7, cy + r * 1.4, r) -- inner button, nudged towards the outer one
	love.graphics.circle("fill", bx + r * 1.2, cy - r * 1.4, r)
	love.graphics.pop()
	return true
end

-- Console unit seen from the front: low wide body, a cartridge slot across the top, a power button
-- and an LED on the left, two controller ports on the right. Same weight as the handheld.
local function drawConsoleGlyph(size, cx, cy, color)
	local stroke = size * (1.7 / 24)
	local bw, bh = size, size * 0.44
	local x, y = cx - bw / 2, cy - bh / 2
	love.graphics.push("all")
	love.graphics.setColor(color)
	love.graphics.setLineWidth(stroke)
	love.graphics.setLineJoin("bevel")
	love.graphics.setLineStyle("smooth")
	love.graphics.rectangle("line", x, y, bw, bh, bh * 0.22, bh * 0.22)
	-- cartridge slot: a slim rounded slot in the upper half
	local slotW, slotH = bw * 0.5, bh * 0.18
	love.graphics.setLineWidth(stroke * 0.73)
	love.graphics.rectangle("line", cx - slotW / 2, y + bh * 0.2, slotW, slotH, slotH / 2, slotH / 2)
	-- power button (short bar) and LED (dot) on the lower left
	local r = stroke * 0.56
	local ly = y + bh * 0.7
	love.graphics.setLineWidth(stroke * 0.73)
	love.graphics.line(x + bw * 0.14, ly, x + bw * 0.28, ly)
	love.graphics.circle("fill", x + bw * 0.36, ly, r)
	-- two controller ports on the lower right
	local pw, ph = bw * 0.09, bh * 0.16
	love.graphics.rectangle("line", x + bw * 0.62, ly - ph / 2, pw, ph, ph * 0.3, ph * 0.3)
	love.graphics.rectangle("line", x + bw * 0.76, ly - ph / 2, pw, ph, ph * 0.3, ph * 0.3)
	love.graphics.pop()
	return true
end

-- Television: screen body with a V antenna, Lucide's proportions at the heavier stroke
local function drawTvGlyph(size, cx, cy, color)
	local stroke = size * DEVICE_STROKE
	local u = size / 24
	local bw, bh = 20 * u, 15 * u
	local x, y = cx - bw / 2, cy - 12 * u + 7 * u
	love.graphics.push("all")
	love.graphics.setColor(color)
	love.graphics.setLineWidth(stroke)
	love.graphics.setLineJoin("bevel")
	love.graphics.setLineStyle("smooth")
	love.graphics.rectangle("line", x, y, bw, bh, 2 * u, 2 * u)
	love.graphics.line(cx - 5 * u, y - 5 * u, cx, y, cx + 5 * u, y - 5 * u)
	love.graphics.pop()
	return true
end

local fontCache = {}
local function fontAt(ttfPath, size)
	local key = ttfPath .. "@" .. size
	if not fontCache[key] then
		fontCache[key] = love.graphics.newFont(ttfPath, size)
	end
	return fontCache[key]
end

-- Draw the tile's symbol: a glyph PNG, the procedural handheld, or a letter in the theme font
local function drawSymbol(opts, side, cx, cy, ink)
	if opts.letter then
		local font = fontAt(opts.ttfPath, math.floor(side * 0.58))
		love.graphics.setFont(font)
		love.graphics.setColor(ink)
		local tw = font:getWidth(opts.letter)
		love.graphics.print(opts.letter, math.floor(cx - tw / 2), math.floor(cy - font:getHeight() / 2))
		return true
	end
	if opts.glyph == "@handheld" then
		return drawHandheldGlyph(side * 0.64, cx, cy, ink)
	elseif opts.glyph == "@tv" then
		return drawTvGlyph(side * 0.56, cx, cy, ink)
	elseif opts.glyph == "@console" then
		return drawConsoleGlyph(side * 0.64, cx, cy, ink)
	end
	return svg.drawImageOnCanvas(glyphPath(opts.glyph), side * 0.52, cx, cy, ink, false)
end

-- Draw one tile into the current canvas.
-- System tiles: PyUI draws the system's display name under the image (systemSelectShowTextGridMode),
-- at the bottom of the grid cell, so the plate sits in the TOP of the image and the band below stays
-- transparent, exactly like the main-menu tiles in skin_renderer. App tiles fill their square.
local function drawTile(opts)
	local w, h, scale = opts.w, opts.h, opts.scale
	local fg = colorUtils.hexToLove(state.getColorValue("foreground"))
	local bg = colorUtils.hexToLove(state.getColorValue("background"))
	local ink = opts.selected and bg or fg
	local side = opts.square and math.min(w, h) or math.min(w, math.floor(h * 0.78))
	local x0 = (w - side) / 2
	local radius = side * 0.16
	local lw = math.max(2, 2 * scale)
	love.graphics.setBlendMode("alpha")
	love.graphics.setLineStyle("smooth")
	if opts.selected then
		love.graphics.setColor(fg)
		love.graphics.rectangle("fill", x0, 0, side, side, radius, radius)
	else
		love.graphics.setLineWidth(lw)
		love.graphics.setColor(fg[1], fg[2], fg[3], 0.6)
		love.graphics.rectangle("line", x0 + lw / 2, lw / 2, side - lw, side - lw, radius, radius)
	end
	local ok, err = drawSymbol(opts, side, w / 2, side / 2, ink)
	if not ok then
		return false, err
	end
	return true
end

local function renderTileFile(path, opts)
	local canvas = love.graphics.newCanvas(opts.w, opts.h)
	local previousCanvas = love.graphics.getCanvas()
	love.graphics.push("all")
	love.graphics.setCanvas(canvas)
	love.graphics.clear(0, 0, 0, 0)
	local ok, err = drawTile(opts)
	love.graphics.setCanvas(previousCanvas)
	love.graphics.pop()
	if not ok then
		canvas:release()
		return fail(err)
	end
	-- plates are foreground-coloured (filled or outlined); transparent pixels take that colour
	local pngData = imageGenerator.encodeCanvas(canvas, false, colorUtils.hexToLove(state.getColorValue("foreground")))
	canvas:release()
	if not pngData then
		return fail("Failed to encode icon " .. path)
	end
	return system.writeFile(path, pngData:getString())
end

local function sortedKeys(t)
	local keys = {}
	for k in pairs(t or {}) do
		keys[#keys + 1] = k
	end
	table.sort(keys)
	return keys
end

-- Render icons/<system>.png, icons/sel/<system>.png and icons/app/<app>.png into outDir
function iconRenderer.renderIcons(width, height, outDir, progress)
	local resolution = string.format("%dx%d", width, height)
	local systems = skinSpec.icons[resolution]
	local selected = skinSpec.icons_sel[resolution] or {}
	local apps = skinSpec.icons_app[resolution] or {}
	if not systems then
		return fail("No reference icon dimensions for " .. resolution)
	end
	for _, sub in ipairs({ "", "/sel", "/app" }) do
		if not system.ensurePath(outDir .. sub .. "/") then
			return fail("Failed to create icon directory: " .. outDir .. sub)
		end
	end
	local scale = math.min(width / 640, height / 480)
	local _, ttfPath = pyuiConfig.fontFile()
	local letters = state.systemIconStyle == "Letter"

	for _, id in ipairs(sortedKeys(systems)) do
		if progress then
			progress(id)
		end
		local dims = systems[id]
		local base = { glyph = glyphs.forSystem(id), scale = scale, ttfPath = ttfPath }
		if letters and ttfPath then
			base.letter = glyphs.letterFor(id)
		end
		base.w, base.h, base.selected = dims[1], dims[2], false
		local ok, err = renderTileFile(outDir .. "/" .. id .. ".png", base)
		if not ok then
			return false, err
		end
		local selDims = selected[id] or dims
		base.w, base.h, base.selected = selDims[1], selDims[2], true
		ok, err = renderTileFile(outDir .. "/sel/" .. id .. ".png", base)
		if not ok then
			return false, err
		end
	end

	local appNames = sortedKeys(apps)
	local anyDims = apps[appNames[1]] or { math.floor(70 * scale + 0.5), math.floor(70 * scale + 0.5) }
	for _, extra in ipairs(iconRenderer.EXTRA_APP_ICONS) do
		if not apps[extra] then
			appNames[#appNames + 1] = extra
		end
	end
	for _, id in ipairs(appNames) do
		if progress then
			progress("app/" .. id)
		end
		local dims = apps[id] or anyDims
		local ok, err = renderTileFile(outDir .. "/app/" .. id .. ".png", {
			w = dims[1], h = dims[2], scale = scale, glyph = glyphs.forApp(id), selected = true, square = true,
		})
		if not ok then
			return false, err
		end
	end
	return true
end

return iconRenderer
