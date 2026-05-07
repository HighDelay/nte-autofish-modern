# NTE AutoFish Modern

A standalone Python autofish script for NTE, built as a separate project from the reference repository. It uses OpenCV template matching, simulated keyboard/mouse input, and a sleek transparent horizontal overlay bar that stays above the game.

## Features

- Transparent topmost horizontal overlay UI.
- English and Vietnamese interface.
- `F8` to pause/resume, backtick to exit.
- Resolution-aware template matching for 720p-style captures and 1080p captures.
- 1080p English template images under `assets/templates`.
- Automatic fishing bar control.
- Optional automatic fish selling.
- Optional automatic bait buying.
- In-app configuration panel with saved settings.
- Overlay can automatically move away from the fishing gauge while running.
- Uses the included `assets/templates` images, so the repo is self-contained.

## Requirements

- Windows
- Python 3.11+ recommended
- Administrator privileges
- NTE running in windowed or borderless fullscreen mode

Install Python dependencies:

```bat
pip install -r requirements.txt
```

## Usage

1. Start NTE and enter the fishing screen.
2. Run `run.bat` as administrator.
3. Click `Start` on the overlay.
4. Use `F8` to pause/resume.
5. Press backtick to close the tool.

You can also run it directly:

```bat
python main.py
```

## Configuration

Click `Cfg` on the overlay to change settings from the UI. Press `Save` to persist them to `settings.json`; saved values are loaded automatically on the next launch.

`config.py` is only the default/fallback configuration.

Common settings:

- `LANGUAGE = "en"` or `"vi"`
- `SELL_FISH = True`
- `BUY_BAIT = True`
- `BUY_BAIT_STACK_COUNT = 5`
- `GREEN_BAR_SAFE_PROPORTION = 0.12`
- `CAPTURE_CLIENT_AREA = False`
- `FISH_BAR_FAST_POLL_INTERVAL = 0.002`
- `FISH_BAR_LOST_CURSOR_FRAMES = 8`
- `CLICK_BLANK_TIMEOUT = 15.0`
- `AUTO_AVOID_FISH_BAR = True`

If the overlay stays on "Finding game window", add your game window title in the `Window titles` box.

Use `CAPTURE_CLIENT_AREA = True` only if your templates were captured from the game client area instead of the full window rectangle.

## Building a Standalone EXE

You can compile the script into a single portable `.exe` using [PyInstaller](https://pyinstaller.org/).

1. Install PyInstaller:

```bat
pip install pyinstaller
```

2. Build the executable (run from the project root):

```bat
pyinstaller --onefile --noconsole --add-data "assets;assets" --add-data "config.py;." --name NTE-AutoFish-Modern main.py
```

3. The compiled `NTE-AutoFish-Modern.exe` will be in the `dist/` folder.

> **Note:** You must run the `.exe` as **administrator** for keyboard/mouse input to work.

**What the flags do:**

| Flag | Purpose |
|---|---|
| `--onefile` | Bundles everything into a single `.exe` |
| `--noconsole` | Hides the console window (GUI only) |
| `--add-data "assets;assets"` | Includes the `assets/templates` folder |
| `--add-data "config.py;."` | Includes the default config |
| `--name NTE-AutoFish-Modern` | Names the output executable |

## Notes

This project does not modify game files or inspect network traffic. It only reads the screen and sends normal keyboard/mouse input. Use it at your own risk.
