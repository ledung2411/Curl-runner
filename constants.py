# constants.py - Clean Postman-inspired API client theme
# Light neutral surfaces with a focused orange accent.
# type: ignore

# Background layers
BG      = "#f5f7fb"   # base shell
BG2     = "#ffffff"   # editor/panel surface
BG3     = "#eef1f6"   # controls and raised surfaces
SIDEBAR = "#ffffff"   # navigation/sidebar
TAB_BG  = "#e9edf4"   # tab strip
BORDER  = "#d8dee9"   # subtle dividers
CODE_BG = "#fbfcff"   # code/editor tint

# Postman-style accent
ACCENT       = "#ff6c37"   # primary orange
ACCENT2      = "#e85d2a"   # hover/pressed state
ACCENT_LIGHT = "#fff1eb"   # pale accent surface
ACCENT_GLOW  = "#c94c1f"   # strong accent edge

# Text
TEXT        = "#1f2937"
TEXT_DIM    = "#667085"
TEXT_URL    = "#1668a8"
ACTIVE_TEXT = "#ffffff"
STATUS_TEXT = "#17202a"

# Semantic status
GREEN    = "#16a36d"
RED_C    = "#e5484d"
YELLOW_C = "#b7791f"
CYAN_C   = "#047d95"
MAG_C    = "#7c5dc7"

# Friendly interactive surfaces
SURFACE_HOVER  = "#e3e8ef"
SURFACE_ACTIVE = ACCENT
TITLEBAR_BG    = "#ffffff"

# Method badge colors
METHOD_COLORS: dict[str, str] = {
    "GET":     "#16a36d",
    "POST":    "#ff6c37",
    "PUT":     "#b7791f",
    "PATCH":   "#7c5dc7",
    "DELETE":  "#e5484d",
    "HEAD":    "#047d95",
    "OPTIONS": "#596579",
}

# Typography - Segoe UI Variable (Win11 system font)
FONT_FAMILY      = "Segoe UI Variable"
FONT_FAMILY_MONO = "Cascadia Code"


def status_color(code: int) -> str:
    if 200 <= code < 300: return GREEN
    if 300 <= code < 400: return YELLOW_C
    if 400 <= code < 500: return RED_C
    return MAG_C
