# -*- coding: utf-8 -*-
"""Configuration for the modern NTE AutoFish script."""

# UI language: "en" or "vi".
LANGUAGE = "en"

# The script searches visible windows by exact or partial title match.
# Keep the Chinese/mojibake variants because different launchers/locales expose
# the game title differently.
WINDOW_TITLES = [
    "异环",
    "å¼‚çŽ¯",
    "Neverness to Everness",
    "NTE",
]

# Capture the whole game window rectangle. This matches the supplied templates.
# If your templates were captured from the client area only, set this to True.
CAPTURE_CLIENT_AREA = False

# Fishing/event automation.
SELL_FISH = False
BUY_BAIT = True
BUY_BAIT_STACK_COUNT = 5

# 0.0-1.0: proportion of the green bar treated as the safe center zone.
# The cursor will not be corrected while inside this zone.
# Larger values = more relaxed tracking, less A/D key toggling.
GREEN_BAR_SAFE_PROPORTION = 0.4

# Capture/timing.
TARGET_FPS = 120
SCAN_INTERVAL = 0.08
FISH_BAR_FAST_POLL_INTERVAL = 0.002
FISH_BAR_MISSING_FRAMES = 14
FISH_BAR_LOST_CURSOR_FRAMES = 8
FISH_BAR_APPEAR_TIMEOUT = 8.0
CLICK_BLANK_TIMEOUT = 15.0
SAVE_FISH_BAR_DEBUG_IMAGE = False

# Normalized screen area used to find the top fishing gauge.
# Values are fractions of the captured game image: left, top, right, bottom.
# Keep this tight around the gauge lane so evening/night sky colors do not get
# mistaken for the cursor or target bar.
FISH_BAR_SCAN_REGION = (0.30, 0.052, 0.70, 0.087)
FISH_BAR_TRACK_REGION = (0.31, 0.69)

# Overlay.
AUTO_START = False
AUTO_AVOID_FISH_BAR = True
OVERLAY_TOP_MARGIN = 14
OVERLAY_ALPHA = 0.94
