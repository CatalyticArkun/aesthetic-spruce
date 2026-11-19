--- Procedural preview of the theme being edited: a little PyUI-like screen drawn with the
--- current colours (replaces the muOS screenshots the original app shipped)
local love = require("love")
local state = require("state")
local colorUtils = require("utils.color")
local imageGenerator = require("utils.image_generator")

local themePreview = {}

--- Draw a mock screen in the rectangle (x, y, w, h).
--- opts.layout  "Grid" | "List" (defaults to state.homeScreenLayout)
--- opts.icons   boolean, draw icon tiles instead of text rows (defaults to state.systemIcons)
function themePreview.draw(x, y, w, h, opts)
	opts = opts or {}
	local layout = opts.layout or state.homeScreenLayout
	local icons = opts.icons
	if icons == nil then
		icons = state.systemIcons
	end
	local bg = colorUtils.hexToLove(state.getColorValue("background"))
	local fg = colorUtils.hexToLove(state.getColorValue("foreground"))
	local radius = math.max(6, h * 0.04)

	love.graphics.push("all")
	love.graphics.setLineStyle("smooth")
	-- background (solid or gradient), clipped to the rounded frame with a stencil
	love.graphics.stencil(function()
		love.graphics.rectangle("fill", x, y, w, h, radius, radius)
	end, "replace", 1)
	love.graphics.setStencilTest("greater", 0)
	if state.backgroundType == "Gradient" then
		local mesh = imageGenerator.createGradientMesh(state.backgroundGradientDirection or "Vertical", bg, colorUtils.hexToLove(state.getColorValue("backgroundGradient")))
		love.graphics.setColor(1, 1, 1, 1)
		love.graphics.draw(mesh, x, y, 0, w, h)
	else
		love.graphics.setColor(bg)
		love.graphics.rectangle("fill", x, y, w, h)
	end

	-- top bar: title + clock/battery marks
	local barH = h * 0.11
	if state.showTopBarText then
		love.graphics.setColor(fg[1], fg[2], fg[3], 0.9)
		love.graphics.rectangle("fill", x + w * 0.04, y + barH * 0.35, w * 0.22, barH * 0.3, 2, 2)
	end
	if state.showClock then
		love.graphics.setColor(fg[1], fg[2], fg[3], 0.9)
		love.graphics.rectangle("fill", x + w * 0.72, y + barH * 0.35, w * 0.12, barH * 0.3, 2, 2)
	end
	if state.showBattery then
		love.graphics.setColor(colorUtils.hexToLove(state.getColorValue("batteryActive")))
		love.graphics.rectangle("fill", x + w * 0.88, y + barH * 0.3, w * 0.07, barH * 0.4, 2, 2)
	end

	-- content
	local top = y + barH * 1.3
	local bottomH = state.showBottomBar and h * 0.11 or 0
	local contentH = h - (top - y) - bottomH - h * 0.04
	if layout == "Grid" then
		-- The device's own main-menu grid (one row of 4 or 5, SPRUCE's 2x3 on the Zero 40), filled
		-- row by row with the tiles the current options turn on, as PyUI lays them out
		local cols, rows = state.mainMenuGrid(state.screenWidth, state.screenHeight)
		local count = 3 + (state.showFavorites and 1 or 0) + (state.showRecents and 1 or 0) + (state.showCollections and 1 or 0)
		count = math.min(count, cols * rows)
		rows = math.ceil(count / cols)
		local gap = w * 0.03
		local tileW = (w - gap * (cols + 1)) / cols
		local tileH = math.min(tileW * 1.1, (contentH * 0.9 - gap * (rows - 1)) / rows)
		tileW = math.min(tileW, tileH / 1.1)
		local gridX = x + (w - (cols * tileW + (cols - 1) * gap)) / 2
		local gridY = top + (contentH - (rows * tileH + (rows - 1) * gap)) / 2
		for i = 1, count do
			local col, row = (i - 1) % cols, math.floor((i - 1) / cols)
			local tx = gridX + col * (tileW + gap)
			local ty = gridY + row * (tileH + gap)
			local selected = i == 2
			if selected then
				love.graphics.setColor(fg)
				love.graphics.rectangle("fill", tx, ty, tileW, tileH, radius, radius)
			else
				love.graphics.setLineWidth(1.5)
				love.graphics.setColor(fg[1], fg[2], fg[3], 0.55)
				love.graphics.rectangle("line", tx, ty, tileW, tileH, radius, radius)
			end
			local ink = selected and bg or fg
			if icons then
				love.graphics.setColor(ink)
				love.graphics.rectangle("fill", tx + tileW * 0.3, ty + tileH * 0.22, tileW * 0.4, tileH * 0.3, 3, 3)
			end
			love.graphics.setColor(ink[1], ink[2], ink[3], 0.9)
			love.graphics.rectangle("fill", tx + tileW * 0.25, ty + tileH * 0.68, tileW * 0.5, tileH * 0.08, 2, 2)
		end
	else
		local rows = 4
		local rowH = contentH / rows
		for i = 1, rows do
			local ry = top + (i - 1) * rowH
			local selected = i == 2
			if selected then
				love.graphics.setColor(fg)
				love.graphics.rectangle("fill", x + w * 0.03, ry + rowH * 0.1, w * 0.94, rowH * 0.8, radius * 0.7, radius * 0.7)
			end
			local ink = selected and bg or fg
			local textX = x + w * 0.08
			if icons then
				love.graphics.setColor(ink)
				love.graphics.rectangle("fill", textX, ry + rowH * 0.3, rowH * 0.4, rowH * 0.4, 2, 2)
				textX = textX + rowH * 0.6
			end
			love.graphics.setColor(ink[1], ink[2], ink[3], 0.9)
			love.graphics.rectangle("fill", textX, ry + rowH * 0.38, w * (0.25 + (i % 3) * 0.08), rowH * 0.24, 2, 2)
		end
	end

	-- bottom bar hints
	if state.showBottomBar then
		local by = y + h - bottomH
		love.graphics.setColor(fg[1], fg[2], fg[3], 0.12)
		love.graphics.rectangle("fill", x, by, w, bottomH)
		love.graphics.setColor(fg[1], fg[2], fg[3], 0.9)
		-- sized by the narrower side too, so a portrait preview keeps the marks apart
		local dot, line = math.min(bottomH * 0.22, w * 0.025), math.min(bottomH * 0.24, w * 0.02)
		love.graphics.circle("fill", x + w * 0.06, by + bottomH / 2, dot)
		love.graphics.rectangle("fill", x + w * 0.1, by + (bottomH - line) / 2, w * 0.1, line, 2, 2)
		love.graphics.circle("fill", x + w * 0.26, by + bottomH / 2, dot)
		love.graphics.rectangle("fill", x + w * 0.3, by + (bottomH - line) / 2, w * 0.1, line, 2, 2)
	end
	love.graphics.setStencilTest()
	love.graphics.pop()

	-- frame
	love.graphics.push("all")
	love.graphics.setLineWidth(1)
	love.graphics.setColor(require("colors").ui.foreground)
	love.graphics.rectangle("line", x, y, w, h, radius, radius)
	love.graphics.pop()
end

--- Largest rectangle with the device's own shape (4:3 until the screen size is known) centred in
--- the given area, so a portrait panel previews as portrait
function themePreview.fitRect(areaX, areaY, areaW, areaH)
	local sw, sh = state.screenWidth or 0, state.screenHeight or 0
	local aspect = (sw > 0 and sh > 0) and sw / sh or 4 / 3
	local w = areaW
	local h = w / aspect
	if h > areaH then
		h = areaH
		w = h * aspect
	end
	return areaX + (areaW - w) / 2, areaY + (areaH - h) / 2, w, h
end

return themePreview
