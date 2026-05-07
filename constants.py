# constants.py — Postman-inspired dark API client theme
# Neutral charcoal surfaces with a focused orange accent.
# type: ignore
# ── Background layers
BG      = "#171717"   # base shell
BG2     = "#202020"   # editor/panel surface
BG3     = "#2a2a2a"   # controls and raised surfaces
SIDEBAR = "#121212"   # navigation/sidebar
TAB_BG  = "#1b1b1b"   # tab strip
BORDER  = "#3a3a3a"   # subtle dividers

# ── Postman-style accent
ACCENT       = "#ff6c37"   # primary orange
ACCENT2      = "#ff875c"   # hover state
ACCENT_LIGHT = "#ffb199"   # light accent text
ACCENT_GLOW  = "#c84f27"   # pressed / shadow

# ── Text
TEXT     = "#f5f5f5"
TEXT_DIM = "#a7a7a7"
TEXT_URL = "#78c7ff"

# ── Semantic status
GREEN    = "#49cc90"
RED_C    = "#ff5a5f"
YELLOW_C = "#f6c343"
CYAN_C   = "#62d6e8"
MAG_C    = "#b48cff"

# ── Win11 surface
SURFACE_HOVER  = "#333333"
SURFACE_ACTIVE = "#3a2a22"
TITLEBAR_BG    = "#111111"

# ── Method badge colors
METHOD_COLORS: dict[str, str] = {
    "GET":     "#4ec99a",
    "POST":    "#ff6c37",
    "PUT":     "#f0b840",
    "PATCH":   "#9b7ff0",
    "DELETE":  "#f55c5c",
    "HEAD":    "#3ec9e0",
    "OPTIONS": "#7a9bbf",
}

# ── Typography — Segoe UI Variable (Win11 system font)
FONT_FAMILY      = "Segoe UI Variable"
FONT_FAMILY_MONO = "Cascadia Code"


def status_color(code: int) -> str:
    if 200 <= code < 300: return GREEN
    if 300 <= code < 400: return YELLOW_C
    if 400 <= code < 500: return RED_C
    return MAG_C
