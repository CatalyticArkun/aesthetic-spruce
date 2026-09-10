--- spruceOS compatibility check
---
--- This app writes files that only PyUI's theme loader understands, so it is tied to the spruceOS
--- release family it was built and tested against. launch.sh exports SPRUCE_VERSION (from
--- helperFunctions.sh get_version, i.e. /mnt/SDCARD/spruce/spruce) and SPRUCE_VERSION_COMPLEX
--- (nightly tag if any). check() returns { level = "ok" | "warn", message = ... }; a warning is
--- shown once on the main menu and the user may continue.
local compat = {}

-- Base versions this build was verified on (hardware runs, theme loaded by PyUI)
compat.TESTED_VERSIONS = { "4.3.6" }
-- Release family whose PyUI theme format this build targets (major.minor)
compat.SUPPORTED_FAMILY = "4.3"

local PYUI_THEME_LOADER = "/mnt/SDCARD/App/PyUI/main-ui/themes/theme.py"
-- Strings the loader must still contain for the generated layout to be understood
local PYUI_SENTINELS = { 'config_{width}x{height}.json', '"skin"', '"icons"', "bg-list-l", "grid-game-selected", "tips-bar-bg" }

local function parseVersion(v)
	if type(v) ~= "string" then
		return nil
	end
	local major, minor, patch = v:match("^(%d+)%.(%d+)%.?(%d*)")
	if not major then
		return nil
	end
	return { major = tonumber(major), minor = tonumber(minor), patch = tonumber(patch) or 0, family = major .. "." .. minor }
end

local function readFile(path)
	local f = io.open(path, "r")
	if not f then
		return nil
	end
	local s = f:read("*a")
	f:close()
	return s
end

function compat.currentVersion()
	local complex = os.getenv("SPRUCE_VERSION_COMPLEX")
	local base = os.getenv("SPRUCE_VERSION")
	if complex and complex ~= "" and complex ~= "0" then
		return complex, base
	end
	return base, base
end

function compat.check()
	if os.getenv("DEV") == "true" then
		return { level = "ok", message = "dev mode" }
	end
	local shown, base = compat.currentVersion()
	local parsed = parseVersion(base)
	local tested = table.concat(compat.TESTED_VERSIONS, ", ")
	local problems = {}

	if not parsed then
		problems[#problems + 1] = "The spruceOS version could not be read (expected /mnt/SDCARD/spruce/spruce)."
	elseif parsed.family ~= compat.SUPPORTED_FAMILY then
		problems[#problems + 1] = string.format(
			"This build targets spruceOS %s.x (tested on %s) but this card runs %s.",
			compat.SUPPORTED_FAMILY, tested, tostring(shown))
	end

	local loader = readFile(PYUI_THEME_LOADER)
	if not loader then
		problems[#problems + 1] = "PyUI's theme loader was not found; this does not look like a spruceOS card that can use generated themes."
	else
		for _, sentinel in ipairs(PYUI_SENTINELS) do
			if not loader:find(sentinel, 1, true) then
				problems[#problems + 1] = "PyUI's theme loader has changed since this build was made; generated themes may not load correctly."
				break
			end
		end
	end

	if #problems == 0 then
		return { level = "ok", message = "spruceOS " .. tostring(shown) }
	end
	return {
		level = "warn",
		message = table.concat(problems, "\n\n") .. "\n\nThemes made here may look wrong or fail to load. Continue anyway?",
	}
end

return compat
