# -*- coding: utf-8 -*-
from __future__ import annotations

import ctypes
import json
import random
import sys
import threading
import webbrowser
import time
import traceback
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except Exception:  # pragma: no cover - tkinter is expected on Windows installs.
    tk = None
    messagebox = None
    ttk = None

try:
    import bettercam
    import cv2
    import numpy as np
    import win32api
    import win32con
    import win32gui
    import win32process
except ImportError as exc:
    bettercam = None
    cv2 = None
    np = None
    win32api = None
    win32con = None
    win32gui = None
    win32process = None
    DEPENDENCY_ERROR = exc
else:
    DEPENDENCY_ERROR = None

import config


ROOT = Path(__file__).resolve().parent
TEMPLATE_DIR = ROOT / "assets" / "templates"
SETTINGS_FILE = ROOT / "settings.json"

CONFIG_DEFAULTS = {
    "LANGUAGE": getattr(config, "LANGUAGE", "en"),
    "WINDOW_TITLES": list(getattr(config, "WINDOW_TITLES", [])),
    "CAPTURE_CLIENT_AREA": getattr(config, "CAPTURE_CLIENT_AREA", False),
    "SELL_FISH": getattr(config, "SELL_FISH", False),
    "BUY_BAIT": getattr(config, "BUY_BAIT", True),
    "BUY_BAIT_STACK_COUNT": getattr(config, "BUY_BAIT_STACK_COUNT", 5),
    "GREEN_BAR_SAFE_PROPORTION": getattr(config, "GREEN_BAR_SAFE_PROPORTION", 0.4),
    "TARGET_FPS": getattr(config, "TARGET_FPS", 240),
    "SCAN_INTERVAL": getattr(config, "SCAN_INTERVAL", 0.08),
    "FISH_BAR_FAST_POLL_INTERVAL": getattr(config, "FISH_BAR_FAST_POLL_INTERVAL", 0.01),
    "FISH_BAR_MISSING_FRAMES": getattr(config, "FISH_BAR_MISSING_FRAMES", 14),
    "FISH_BAR_LOST_CURSOR_FRAMES": getattr(config, "FISH_BAR_LOST_CURSOR_FRAMES", 8),
    "FISH_BAR_APPEAR_TIMEOUT": getattr(config, "FISH_BAR_APPEAR_TIMEOUT", 8.0),
    "CLICK_BLANK_TIMEOUT": getattr(config, "CLICK_BLANK_TIMEOUT", 15.0),
    "FISH_BAR_SCAN_REGION": tuple(getattr(config, "FISH_BAR_SCAN_REGION", (0.30, 0.052, 0.70, 0.087))),
    "FISH_BAR_TRACK_REGION": tuple(getattr(config, "FISH_BAR_TRACK_REGION", (0.31, 0.69))),
    "AUTO_START": getattr(config, "AUTO_START", False),
    "AUTO_AVOID_FISH_BAR": getattr(config, "AUTO_AVOID_FISH_BAR", True),
    "OVERLAY_TOP_MARGIN": getattr(config, "OVERLAY_TOP_MARGIN", 14),
    "OVERLAY_ALPHA": getattr(config, "OVERLAY_ALPHA", 0.94),
}


def clamp_float(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def normalize_setting(name: str, value):
    if name in {"CAPTURE_CLIENT_AREA", "SELL_FISH", "BUY_BAIT", "AUTO_START", "AUTO_AVOID_FISH_BAR"}:
        return bool(value)
    if name in {
        "BUY_BAIT_STACK_COUNT",
        "TARGET_FPS",
        "FISH_BAR_MISSING_FRAMES",
        "FISH_BAR_LOST_CURSOR_FRAMES",
        "OVERLAY_TOP_MARGIN",
    }:
        return int(value)
    if name in {
        "GREEN_BAR_SAFE_PROPORTION",
        "SCAN_INTERVAL",
        "FISH_BAR_FAST_POLL_INTERVAL",
        "FISH_BAR_APPEAR_TIMEOUT",
        "CLICK_BLANK_TIMEOUT",
        "OVERLAY_ALPHA",
    }:
        return float(value)
    if name == "LANGUAGE":
        return str(value).lower() if str(value).lower() in {"en", "vi"} else "en"
    if name == "WINDOW_TITLES":
        if isinstance(value, str):
            titles = [line.strip() for line in value.splitlines()]
        else:
            titles = [str(item).strip() for item in value]
        return [title for title in titles if title]
    if name == "FISH_BAR_SCAN_REGION":
        values = [float(item) for item in value]
        if len(values) != 4:
            raise ValueError("Fish bar scan region needs 4 values")
        left, top, right, bottom = [clamp_float(item, 0.0, 1.0) for item in values]
        if left >= right or top >= bottom:
            raise ValueError("Fish bar scan region must be left, top, right, bottom")
        return (left, top, right, bottom)
    if name == "FISH_BAR_TRACK_REGION":
        values = [float(item) for item in value]
        if len(values) != 2:
            raise ValueError("Fish bar track region needs 2 values")
        left, right = [clamp_float(item, 0.0, 1.0) for item in values]
        if left >= right:
            raise ValueError("Fish bar track region must be left, right")
        return (left, right)
    return value


def load_saved_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        with SETTINGS_FILE.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except Exception:
        return {}
    settings = {}
    for name in CONFIG_DEFAULTS:
        if name in raw:
            settings[name] = normalize_setting(name, raw[name])
    return settings


def apply_settings(settings: dict) -> None:
    for name, value in settings.items():
        if name in CONFIG_DEFAULTS:
            setattr(config, name, normalize_setting(name, value))


def current_settings() -> dict:
    return {name: getattr(config, name, default) for name, default in CONFIG_DEFAULTS.items()}


def save_settings(settings: dict) -> None:
    normalized = {}
    for name in CONFIG_DEFAULTS:
        value = normalize_setting(name, settings.get(name, getattr(config, name, CONFIG_DEFAULTS[name])))
        normalized[name] = list(value) if isinstance(value, tuple) else value
    with SETTINGS_FILE.open("w", encoding="utf-8") as handle:
        json.dump(normalized, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    apply_settings(normalized)


apply_settings(load_saved_settings())


TEXT = {
    "en": {
        "app_title": "NTE AutoFish",
        "start": "Start",
        "pause": "Pause",
        "resume": "Resume",
        "stop": "Stop",
        "close": "Close",
        "idle": "Idle",
        "ready": "Ready",
        "running": "Running",
        "paused": "Paused",
        "stopping": "Stopping",
        "stopped": "Stopped",
        "error": "Error",
        "finding_window": "Finding game window",
        "waiting_hook": "Waiting for hook",
        "casting": "Casting",
        "waiting_bait": "Taking bait",
        "waiting_fish_bar": "Waiting for fishing bar",
        "tracking_bar": "Balancing fishing bar",
        "collecting": "Collecting fish",
        "handling_event": "Handling event",
        "storage_full": "Storage full",
        "buying_bait": "Buying bait",
        "month_card": "Closing monthly card",
        "unknown_event": "Unknown event",
        "admin_needed": "Run as administrator",
        "deps_missing": "Missing dependencies",
        "fish": "Fish",
        "res": "Res",
        "sell": "Sell",
        "bait": "Bait",
        "on": "On",
        "off": "Off",
        "hotkeys": "F8 / `",
        "settings": "Cfg",
        "saved": "Saved",
    },
    "vi": {
        "app_title": "NTE AutoFish",
        "start": "Bắt đầu",
        "pause": "Tạm dừng",
        "resume": "Tiếp tục",
        "stop": "Dừng",
        "close": "Đóng",
        "idle": "Chờ",
        "ready": "Sẵn sàng",
        "running": "Đang chạy",
        "paused": "Tạm dừng",
        "stopping": "Đang dừng",
        "stopped": "Đã dừng",
        "error": "Lỗi",
        "finding_window": "Đang tìm cửa sổ game",
        "waiting_hook": "Đợi móc câu",
        "casting": "Thả câu",
        "waiting_bait": "Lấy mồi",
        "waiting_fish_bar": "Đợi thanh câu cá",
        "tracking_bar": "Giữ thanh câu cá",
        "collecting": "Nhận cá",
        "handling_event": "Xử lý sự kiện",
        "storage_full": "Túi cá đầy",
        "buying_bait": "Mua mồi câu",
        "month_card": "Đóng thẻ tháng",
        "unknown_event": "Sự kiện chưa rõ",
        "admin_needed": "Chạy bằng quyền admin",
        "deps_missing": "Thiếu thư viện",
        "fish": "Cá",
        "res": "Độ phân giải",
        "sell": "Bán",
        "bait": "Mồi",
        "on": "Bật",
        "off": "Tắt",
        "hotkeys": "F8 / `",
        "settings": "Cfg",
        "saved": "Saved",
    },
}


SCAN_CODES = {
    "a": 0x1E,
    "d": 0x20,
    "f": 0x21,
    "q": 0x10,
    "e": 0x12,
    "r": 0x13,
    "esc": 0x01,
}


class StopAutomation(Exception):
    pass


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))


class StateStore:
    def __init__(self) -> None:
        language = getattr(config, "LANGUAGE", "en").lower()
        if language not in TEXT:
            language = "en"
        self._lock = threading.Lock()
        self._data = {
            "language": language,
            "status": "idle",
            "message": "ready",
            "resolution": "--",
            "fish_count": 0,
            "started_at": None,
            "last_error": "",
        }

    def update(self, **kwargs) -> None:
        with self._lock:
            self._data.update(kwargs)

    def increment_fish(self) -> None:
        with self._lock:
            self._data["fish_count"] += 1

    def toggle_language(self) -> None:
        with self._lock:
            self._data["language"] = "vi" if self._data["language"] == "en" else "en"

    def set_language(self, language: str) -> None:
        language = language.lower()
        if language not in TEXT:
            language = "en"
        with self._lock:
            self._data["language"] = language

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._data)


class KeyboardDriver:
    _send_input = ctypes.windll.user32.SendInput if hasattr(ctypes, "windll") else None

    @staticmethod
    def _send_scan(scan_code: int, flags: int) -> None:
        extra = ctypes.c_ulong(0)

        class KeyBdInput(ctypes.Structure):
            _fields_ = [
                ("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class HardwareInput(ctypes.Structure):
            _fields_ = [
                ("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort),
            ]

        class MouseInput(ctypes.Structure):
            _fields_ = [
                ("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class InputUnion(ctypes.Union):
            _fields_ = [("ki", KeyBdInput), ("mi", MouseInput), ("hi", HardwareInput)]

        class Input(ctypes.Structure):
            _fields_ = [("type", ctypes.c_ulong), ("ii", InputUnion)]

        ii = InputUnion()
        ii.ki = KeyBdInput(0, scan_code, flags, 0, ctypes.pointer(extra))
        command = Input(ctypes.c_ulong(1), ii)
        ctypes.windll.user32.SendInput(1, ctypes.pointer(command), ctypes.sizeof(command))

    @classmethod
    def press(cls, key: str) -> None:
        scan_code = SCAN_CODES.get(key)
        if scan_code is not None:
            cls._send_scan(scan_code, 0x0008)

    @classmethod
    def release(cls, key: str) -> None:
        scan_code = SCAN_CODES.get(key)
        if scan_code is not None:
            cls._send_scan(scan_code, 0x0008 | 0x0002)

    @classmethod
    def click(cls, key: str, duration: float = 0.09) -> None:
        cls.press(key)
        time.sleep(duration)
        cls.release(key)

    @classmethod
    def release_all(cls) -> None:
        for key in ("a", "d"):
            cls.release(key)


class ScaledTemplate:
    def __init__(
        self,
        filename: str,
        *,
        search_rect: tuple[int, int, int, int] | None = None,
        similarity: float = 0.85,
    ) -> None:
        self.path = TEMPLATE_DIR / filename
        self.name = self.path.stem
        self.similarity = similarity
        img = cv2.imread(str(self.path), cv2.IMREAD_UNCHANGED)
        if img is None:
            raise FileNotFoundError(f"Template not found: {self.path}")

        self.source_w = img.shape[1]
        self.source_h = img.shape[0]

        if len(img.shape) == 3 and img.shape[2] == 4:
            alpha = img[:, :, 3]
            coords = cv2.findNonZero(alpha)
            if coords is None:
                raise ValueError(f"Template has no visible pixels: {self.path}")
            x, y, w, h = cv2.boundingRect(coords)
            crop = img[y : y + h, x : x + w, :3]
            self.template_rect = (x, y, w, h)
        else:
            crop = img[:, :, :3] if len(img.shape) == 3 else img
            self.template_rect = (0, 0, self.source_w, self.source_h)

        self.search_rect = search_rect or self.template_rect
        self.template_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        self.pos = (
            self.template_rect[0] + self.template_rect[2] // 2,
            self.template_rect[1] + self.template_rect[3] // 2,
        )
        self.last_score = 0.0

    def scale(self, screenshot) -> tuple[float, float]:
        h, w = screenshot.shape[:2]
        return w / self.source_w, h / self.source_h

    def _scaled_rect(self, rect: tuple[int, int, int, int], sx: float, sy: float) -> tuple[int, int, int, int]:
        x, y, w, h = rect
        return round(x * sx), round(y * sy), max(1, round(w * sx)), max(1, round(h * sy))

    def match(self, screenshot, offset: int = 14, similarity: float | None = None) -> bool:
        if screenshot is None:
            return False

        sx, sy = self.scale(screenshot)
        x, y, w, h = self._scaled_rect(self.search_rect, sx, sy)
        tw = max(1, round(self.template_gray.shape[1] * sx))
        th = max(1, round(self.template_gray.shape[0] * sy))
        scaled_template = cv2.resize(self.template_gray, (tw, th), interpolation=cv2.INTER_LINEAR)

        img_h, img_w = screenshot.shape[:2]
        margin = max(offset, round(min(img_w, img_h) * 0.012))
        x1 = clamp(x - margin, 0, img_w)
        y1 = clamp(y - margin, 0, img_h)
        x2 = clamp(x + w + margin, 0, img_w)
        y2 = clamp(y + h + margin, 0, img_h)

        roi = screenshot[y1:y2, x1:x2]
        if roi.shape[0] < th or roi.shape[1] < tw:
            return False

        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(roi_gray, scaled_template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        self.last_score = float(max_val)

        if max_val >= (similarity or self.similarity):
            self.pos = (x1 + max_loc[0] + tw // 2, y1 + max_loc[1] + th // 2)
            return True
        return False

    def match_anywhere(self, screenshot, similarity: float | None = None) -> bool:
        if screenshot is None:
            return False

        sx, sy = self.scale(screenshot)
        tw = max(1, round(self.template_gray.shape[1] * sx))
        th = max(1, round(self.template_gray.shape[0] * sy))
        if screenshot.shape[0] < th or screenshot.shape[1] < tw:
            return False

        scaled_template = cv2.resize(self.template_gray, (tw, th), interpolation=cv2.INTER_LINEAR)
        screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(screenshot_gray, scaled_template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        self.last_score = float(max_val)

        if max_val >= (similarity or self.similarity):
            self.pos = (max_loc[0] + tw // 2, max_loc[1] + th // 2)
            return True
        return False


class TemplateBank:
    def __init__(self) -> None:
        self.take_bait = ScaledTemplate("TAKE_BAIT.png")
        self.hook = ScaledTemplate("HOOK.png", similarity=0.82)
        self.click_blank = ScaledTemplate("CLICK_BLANK.png")
        self.full = ScaledTemplate("FULL.png")
        self.fish_storage = ScaledTemplate("FISH_STORAGE.png")
        self.sell = ScaledTemplate("SELL.png")
        self.sell_confirm = ScaledTemplate("SELL_CONFIRM.png")
        self.month_card = ScaledTemplate("MONTH_CARD.png")
        self.get_item = ScaledTemplate("GET_ITEM.png")
        self.need_bait = ScaledTemplate("NEED_BAIT.png")
        self.bait = ScaledTemplate("BAIT.png", search_rect=(39, 118, 409, 476), similarity=0.82)
        self.max = ScaledTemplate("MAX.png")
        self.buy = ScaledTemplate("BUY.png")
        self.confirm = ScaledTemplate("CONFIRM.png")
        self.change = ScaledTemplate("CHANGE.png")
        self.sell_success = ScaledTemplate("SELL_SUCCESS.png")
        self.fish_icon = ScaledTemplate("FISH_ICON.png", similarity=0.82)


class GameController:
    def __init__(self, state: StateStore, stop_event: threading.Event) -> None:
        self.state = state
        self.stop_event = stop_event
        self.window_titles = [title.lower() for title in getattr(config, "WINDOW_TITLES", [])]
        self.hwnd = None
        self.rect = None
        self.last_rect_check = 0.0
        self.camera = bettercam.create(output_color="BGR")
        self.camera.start(target_fps=getattr(config, "TARGET_FPS", 120), video_mode=True)

    def _visible_windows(self) -> list[tuple[int, str]]:
        windows: list[tuple[int, str]] = []

        def callback(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd).strip()
            lower = title.lower()
            if "autofish overlay" in lower or "autofish settings" in lower:
                return True
            if title:
                windows.append((hwnd, title))
            return True

        win32gui.EnumWindows(callback, None)
        return windows

    def _find_window(self) -> int | None:
        windows = self._visible_windows()
        for hwnd, title in windows:
            lower = title.lower()
            if lower in self.window_titles:
                return hwnd
        for hwnd, title in windows:
            lower = title.lower()
            if any(needle and needle in lower for needle in self.window_titles):
                return hwnd
        return None

    def ensure_window(self) -> int:
        while not self.stop_event.is_set():
            if self.hwnd and win32gui.IsWindow(self.hwnd):
                return self.hwnd
            self.state.update(status="running", message="finding_window")
            self.hwnd = self._find_window()
            self.rect = None
            if self.hwnd:
                return self.hwnd
            time.sleep(1.0)
        raise StopAutomation()

    def _game_rect(self) -> tuple[int, int, int, int]:
        hwnd = self.ensure_window()
        now = time.time()
        if self.rect is not None and now - self.last_rect_check < 0.4:
            return self.rect

        if getattr(config, "CAPTURE_CLIENT_AREA", False):
            left, top = win32gui.ClientToScreen(hwnd, (0, 0))
            client_right, client_bottom = win32gui.GetClientRect(hwnd)[2:]
            right, bottom = win32gui.ClientToScreen(hwnd, (client_right, client_bottom))
            rect = (left, top, right, bottom)
        else:
            rect = win32gui.GetWindowRect(hwnd)

        self.rect = rect
        self.last_rect_check = now
        return rect

    def focus_game(self) -> None:
        hwnd = self.ensure_window()
        if win32gui.GetForegroundWindow() == hwnd:
            return
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            foreground = win32gui.GetForegroundWindow()
            current_thread = win32api.GetCurrentThreadId()
            foreground_thread = win32process.GetWindowThreadProcessId(foreground)[0] if foreground else 0
            target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]

            attached_threads = []
            for thread_id in {foreground_thread, target_thread}:
                if thread_id and thread_id != current_thread:
                    try:
                        win32process.AttachThreadInput(current_thread, thread_id, True)
                        attached_threads.append(thread_id)
                    except Exception:
                        pass

            try:
                win32gui.BringWindowToTop(hwnd)
                win32gui.SetForegroundWindow(hwnd)
                win32gui.SetFocus(hwnd)
            finally:
                for thread_id in attached_threads:
                    try:
                        win32process.AttachThreadInput(current_thread, thread_id, False)
                    except Exception:
                        pass
            time.sleep(0.02)
        except Exception:
            pass

    def screenshot(self):
        self.focus_game()
        frame = self.camera.get_latest_frame()
        if frame is None:
            frame = self.camera.grab()
        if frame is None:
            return None

        left, top, right, bottom = self._game_rect()
        screen_h, screen_w = frame.shape[:2]
        left = clamp(left, 0, screen_w)
        right = clamp(right, 0, screen_w)
        top = clamp(top, 0, screen_h)
        bottom = clamp(bottom, 0, screen_h)
        cropped = frame[top:bottom, left:right]
        if cropped.shape[0] < 700 or cropped.shape[1] < 1200:
            raise ValueError(f"Unsupported capture size: {cropped.shape[1]}x{cropped.shape[0]}")

        self.state.update(resolution=f"{cropped.shape[1]}x{cropped.shape[0]}")
        return cropped

    def mouse_click(self, pos: tuple[int, int] | None = None) -> None:
        self.focus_game()
        if pos is None:
            frame = self.screenshot()
            if frame is None:
                return
            h, w = frame.shape[:2]
            pos = (w // 2, h - round(h * 0.075))
        left, top, _, _ = self._game_rect()
        x = int(left + pos[0])
        y = int(top + pos[1])
        win32api.SetCursorPos((x, y))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.045)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


class FishBarTracker:
    GREEN_BAR_BGR = (173, 202, 42)
    YELLOW_CURSOR_BGR_TARGETS = (
        (157, 246, 254),
        (128, 250, 255),
        (190, 252, 255),
    )
    GREEN_HSV_LOW = (35, 45, 115)
    GREEN_HSV_HIGH = (100, 255, 255)
    YELLOW_HSV_LOW = (20, 25, 200)
    YELLOW_HSV_HIGH = (38, 255, 255)

    def __init__(
        self,
        controller: GameController,
        templates: TemplateBank,
        stop_event: threading.Event,
        pause_event: threading.Event,
        state: StateStore,
    ) -> None:
        self.controller = controller
        self.templates = templates
        self.stop_event = stop_event
        self.pause_event = pause_event
        self.state = state
        self.current_key = None
        self.safe_proportion = clamp_float(
            getattr(config, "GREEN_BAR_SAFE_PROPORTION", 0.4), 0.05, 0.80
        )
        self.rect: tuple[int, int, int, int] | None = None
        self.last_focus_time = 0.0

    def _pause_gate(self) -> None:
        if not self.pause_event.is_set():
            return
        self._release_all()
        self.state.update(status="paused", message="paused")
        while self.pause_event.is_set():
            if self.stop_event.is_set():
                raise StopAutomation()
            time.sleep(0.08)
        self.state.update(status="running", message="tracking_bar")

    def _release_all(self) -> None:
        if self.current_key:
            self._focus_for_input()
            KeyboardDriver.release(self.current_key)
            self.current_key = None

    def _focus_for_input(self, force: bool = False) -> None:
        now = time.perf_counter()
        if force or now - self.last_focus_time > 0.12:
            self.controller.focus_game()
            self.last_focus_time = now

    def _press(self, key: str | None) -> None:
        if self.current_key == key:
            if key:
                self._focus_for_input()
            return
        self._release_all()
        if key:
            self._focus_for_input(force=True)
            KeyboardDriver.press(key)
            self.current_key = key

    def reset(self) -> None:
        self._release_all()
        self.rect = None

    def _hsv_mask(self, roi, low: tuple[int, int, int], high: tuple[int, int, int]):
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        return cv2.inRange(hsv, np.array(low, dtype=np.uint8), np.array(high, dtype=np.uint8))

    def _green_mask(self, roi):
        exact_target = np.array(self.GREEN_BAR_BGR, dtype=np.int16)
        exact_dist = np.sum(np.abs(roi.astype(np.int16) - exact_target), axis=2)
        exact_mask = (exact_dist < 48).astype(np.uint8) * 255
        hsv_mask = self._hsv_mask(roi, self.GREEN_HSV_LOW, self.GREEN_HSV_HIGH)
        return cv2.bitwise_or(exact_mask, hsv_mask)

    def _yellow_masks(self, roi):
        roi_i = roi.astype(np.int16)
        exact_mask = np.zeros(roi.shape[:2], dtype=np.uint8)
        for target in self.YELLOW_CURSOR_BGR_TARGETS:
            exact_target = np.array(target, dtype=np.int16)
            exact_dist = np.sum(np.abs(roi_i - exact_target), axis=2)
            exact_mask = cv2.bitwise_or(exact_mask, (exact_dist < 54).astype(np.uint8) * 255)

        b = roi_i[:, :, 0]
        g = roi_i[:, :, 1]
        r = roi_i[:, :, 2]
        reference_mask = cv2.bitwise_or(
            exact_mask,
            (
                (r >= 235)
                & (g >= 215)
                & (b <= 225)
                & ((r - b) >= 20)
                & ((g - b) >= 8)
            ).astype(np.uint8)
            * 255,
        )
        pale_core_mask = (
            (r >= 245)
            & (g >= 235)
            & (b >= 120)
            & (b <= 240)
            & ((r - b) >= 8)
        ).astype(np.uint8) * 255
        reference_mask = cv2.bitwise_or(reference_mask, pale_core_mask)

        hsv_mask = self._hsv_mask(roi, self.YELLOW_HSV_LOW, self.YELLOW_HSV_HIGH)
        hsv_mask = cv2.bitwise_and(
            hsv_mask,
            (
                (r >= 230)
                & (g >= 210)
                & (b <= 230)
                & ((r - b) >= 12)
            ).astype(np.uint8)
            * 255,
        )
        return reference_mask, cv2.bitwise_or(reference_mask, hsv_mask)

    @staticmethod
    def _column_spans(cols) -> list[tuple[int, int]]:
        if cols.size == 0:
            return []
        spans: list[tuple[int, int]] = []
        start = prev = int(cols[0])
        for col in cols[1:]:
            col = int(col)
            if col == prev + 1:
                prev = col
                continue
            spans.append((start, prev))
            start = prev = col
        spans.append((start, prev))
        return spans

    def _yellow_cursor_candidates(self, roi, origin: tuple[int, int], frame_shape: tuple[int, int]):
        exact_mask, mask = self._yellow_masks(roi)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        img_h, img_w = frame_shape
        min_height = max(8, round(img_h * 0.008))
        max_height = max(min_height + 1, round(img_h * 0.045))
        max_width = max(14, round(img_w * 0.012))
        candidates: list[tuple[float, int]] = []

        for contour in contours:
            cx, cy, cw, ch = cv2.boundingRect(contour)
            if ch < min_height or ch > max_height or cw > max_width:
                continue
            aspect = ch / max(1, cw)
            if aspect < 1.8:
                continue
            lane_y = roi.shape[0] / 2
            if not cy <= lane_y <= cy + ch:
                continue
            exact_pixels = cv2.countNonZero(exact_mask[cy : cy + ch, cx : cx + cw])
            if exact_pixels < max(2, round(cw * ch * 0.04)):
                continue
            center_penalty = abs(cy + ch / 2 - roi.shape[0] / 2) / max(1, roi.shape[0])
            score = ch * min(cw, 6) - center_penalty * 4.0
            candidates.append((score, int(origin[0] + cx + cw / 2)))

        return sorted(candidates, reverse=True)

    def _has_cursor_near_green(self, frame, green_rect: tuple[int, int, int, int]) -> bool:
        img_h, img_w = frame.shape[:2]
        _, gy, _, gh = green_rect
        track_left, track_right = getattr(config, "FISH_BAR_TRACK_REGION", (0.31, 0.69))
        x1 = clamp(round(img_w * track_left), 0, img_w)
        x2 = clamp(round(img_w * track_right), 0, img_w)
        margin_y = max(12, round(img_h * 0.012))
        y1 = clamp(gy - margin_y, 0, img_h)
        y2 = clamp(gy + gh + margin_y, 0, img_h)
        if x2 <= x1 or y2 <= y1:
            return False

        roi = frame[y1:y2, x1:x2]
        return bool(self._yellow_cursor_candidates(roi, (x1, y1), (img_h, img_w)))

    def _locate_bar_region(self, frame) -> tuple[int, int, int, int] | None:
        img_h, img_w = frame.shape[:2]
        left, top, right, bottom = getattr(config, "FISH_BAR_SCAN_REGION", (0.30, 0.052, 0.70, 0.087))
        x1 = clamp(round(img_w * left), 0, img_w)
        y1 = clamp(round(img_h * top), 0, img_h)
        x2 = clamp(round(img_w * right), 0, img_w)
        y2 = clamp(round(img_h * bottom), 0, img_h)
        if x2 <= x1 or y2 <= y1:
            return None

        roi = frame[y1:y2, x1:x2]
        mask = self._green_mask(roi)
        open_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3))
        close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates: list[tuple[float, tuple[int, int, int, int]]] = []
        min_width = max(45, round(img_w * 0.028))
        max_width = max(min_width + 1, round(img_w * 0.28))
        min_height = max(4, round(img_h * 0.004))
        max_height = max(24, round(img_h * 0.035))

        for contour in contours:
            cx, cy, cw, ch = cv2.boundingRect(contour)
            if cw < min_width or cw > max_width or ch < min_height or ch > max_height:
                continue
            aspect = cw / max(1, ch)
            if aspect < 4.0:
                continue
            score = cw * aspect
            candidates.append((score, (x1 + cx, y1 + cy, cw, ch)))

        if not candidates:
            return None

        valid_candidates = [item for item in candidates if self._has_cursor_near_green(frame, item[1])]
        if not valid_candidates:
            return None

        _, green_rect = max(valid_candidates, key=lambda item: item[0])
        _, gy, _, gh = green_rect
        track_left, track_right = getattr(config, "FISH_BAR_TRACK_REGION", (0.31, 0.69))
        tx1 = clamp(round(img_w * track_left), 0, img_w)
        tx2 = clamp(round(img_w * track_right), 0, img_w)
        margin_y = max(12, round(img_h * 0.012))
        ty1 = clamp(gy - margin_y, 0, img_h)
        ty2 = clamp(gy + gh + margin_y, 0, img_h)
        return (tx1, ty1, max(1, tx2 - tx1), max(1, ty2 - ty1))

    def set_rect(self, frame) -> bool:
        rect = self._locate_bar_region(frame)
        if rect is None:
            self.rect = None
            return False
        self.rect = rect
        return True

    def _region(self, frame):
        if self.rect is None:
            return None, None
        x, y, w, h = self.rect
        img_h, img_w = frame.shape[:2]
        x1 = clamp(x, 0, img_w)
        y1 = clamp(y, 0, img_h)
        x2 = clamp(x + w, 0, img_w)
        y2 = clamp(y + h, 0, img_h)
        if x2 <= x1 or y2 <= y1:
            return None, None
        return frame[y1:y2, x1:x2], (x1, y1)

    def _bar_range(self, frame) -> tuple[int, int] | None:
        """Return (safe_left, safe_right) pixel boundaries for the cursor."""
        roi, origin = self._region(frame)
        if roi is None or origin is None:
            return None
        mask = self._green_mask(roi)
        min_hits = max(1, round(roi.shape[0] * 0.08))
        cols = np.where(np.count_nonzero(mask, axis=0) >= min_hits)[0]
        if cols.size == 0:
            return None
        span_left, span_right = max(self._column_spans(cols), key=lambda span: span[1] - span[0])
        left = int(span_left + origin[0])
        right = int(span_right + origin[0])
        width = max(1, right - left)
        safe_left = int(left + width * (0.5 - self.safe_proportion / 2))
        safe_right = int(left + width * (0.5 + self.safe_proportion / 2))
        return (safe_left, safe_right)

    def _cursor_pos(self, frame) -> int | None:
        roi, origin = self._region(frame)
        if roi is None or origin is None:
            return None
        candidates = self._yellow_cursor_candidates(roi, origin, frame.shape[:2])
        if not candidates:
            return None
        return candidates[0][1]

    def _catch_prompt_visible(self, frame) -> bool:
        return self.templates.click_blank.match(frame, offset=80, similarity=0.76) or self.templates.click_blank.match_anywhere(
            frame,
            similarity=0.76,
        )

    def track(self) -> None:
        missing = 0
        cursor_missing = 0
        seen_bar = False
        appear_deadline = time.time() + getattr(config, "FISH_BAR_APPEAR_TIMEOUT", 8.0)
        self.state.update(status="running", message="waiting_fish_bar")
        try:
            while not self.stop_event.is_set():
                self._pause_gate()
                frame = self.controller.screenshot()
                if frame is None:
                    continue
                if self.rect is None and not self.set_rect(frame):
                    if not seen_bar and time.time() > appear_deadline:
                        raise TimeoutError("Timed out waiting for fish bar")
                    time.sleep(getattr(config, "FISH_BAR_FAST_POLL_INTERVAL", 0.01))
                    continue
                green_bar = self._bar_range(frame)
                if green_bar is None:
                    if seen_bar:
                        missing += 1
                        if missing >= 3 and self._catch_prompt_visible(frame):
                            return
                    if seen_bar and missing > getattr(config, "FISH_BAR_MISSING_FRAMES", 14):
                        self.rect = None
                        return
                    if not seen_bar and time.time() > appear_deadline:
                        raise TimeoutError("Timed out waiting for fish bar")
                    time.sleep(getattr(config, "FISH_BAR_FAST_POLL_INTERVAL", 0.01))
                    continue
                cursor = self._cursor_pos(frame)
                if cursor is None:
                    if seen_bar:
                        cursor_missing += 1
                        if cursor_missing >= 3 and self._catch_prompt_visible(frame):
                            return
                        self._press(None)
                    if not seen_bar and time.time() > appear_deadline:
                        raise TimeoutError("Timed out waiting for fish bar")
                    continue
                if not seen_bar:
                    self.state.update(status="running", message="tracking_bar")
                seen_bar = True
                missing = 0
                cursor_missing = 0
                safe_left, safe_right = green_bar
                # Simple boundary decision — matches the proven NTE_AutoFish logic.
                if cursor < safe_left:
                    self._press("d")
                elif cursor > safe_right:
                    self._press("a")
                else:
                    self._press(None)
        finally:
            self._release_all()


class AutomationWorker(threading.Thread):
    def __init__(self, state: StateStore) -> None:
        super().__init__(daemon=True)
        self.state = state
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.templates = TemplateBank()
        self.controller: GameController | None = None

    def request_stop(self) -> None:
        self.stop_event.set()
        self.pause_event.clear()
        KeyboardDriver.release_all()

    def toggle_pause(self) -> None:
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.state.update(status="running", message="ready")
        else:
            self.pause_event.set()
            self.state.update(status="paused", message="paused")
            KeyboardDriver.release_all()

    def _pause_gate(self) -> None:
        if not self.pause_event.is_set():
            return
        KeyboardDriver.release_all()
        self.state.update(status="paused", message="paused")
        while self.pause_event.is_set():
            if self.stop_event.is_set():
                raise StopAutomation()
            time.sleep(0.08)
        self.state.update(status="running", message="ready")

    def _sleep(self, seconds: float, variance: float = 0.2) -> None:
        duration = sum(random.uniform(seconds * (1 - variance), seconds * (1 + variance)) for _ in range(3)) / 3
        end_at = time.time() + max(0.0, duration)
        while time.time() < end_at:
            if self.stop_event.is_set():
                raise StopAutomation()
            self._pause_gate()
            time.sleep(min(0.08, end_at - time.time()))

    def _click_key(self, key: str, duration: float = 0.09) -> None:
        if self.controller:
            self.controller.focus_game()
        KeyboardDriver.click(key, duration)

    def wait_until_appear(self, template: ScaledTemplate, timeout: float, message: str) -> None:
        self.state.update(status="running", message=message)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.stop_event.is_set():
                raise StopAutomation()
            self._pause_gate()
            frame = self.controller.screenshot()
            if template.match(frame):
                self._sleep(0.18)
                return
            time.sleep(getattr(config, "SCAN_INTERVAL", 0.08))
        raise TimeoutError(f"Timed out waiting for {template.name}")

    def wait_until_appear_or_bar(
        self,
        template: ScaledTemplate,
        timeout: float,
        message: str,
        tracker: FishBarTracker,
    ) -> str:
        self.state.update(status="running", message=message)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.stop_event.is_set():
                raise StopAutomation()
            self._pause_gate()
            frame = self.controller.screenshot()
            if frame is None:
                continue
            if tracker.set_rect(frame):
                tracker.track()
                self.finish_current_fish()
                return "bar"
            if template.match(frame):
                self._sleep(0.05)
                return "template"
            time.sleep(getattr(config, "FISH_BAR_FAST_POLL_INTERVAL", 0.01))
        raise TimeoutError(f"Timed out waiting for {template.name}")

    def _latest_frame(self):
        frame = self.controller.screenshot()
        if frame is None:
            raise TimeoutError("No screenshot available")
        return frame

    def handle_event(self) -> None:
        self.state.update(status="running", message="handling_event")
        self._click_key("f")
        self._sleep(0.5)
        image = self._latest_frame()

        if self.templates.full.match(image):
            self.state.update(message="storage_full")
            if not getattr(config, "SELL_FISH", True):
                self.state.update(status="stopped", message="storage_full")
                raise StopAutomation()
            self._sleep(2.0)
            self._click_key("q")
            self.wait_until_appear(self.templates.fish_storage, 2.0, "storage_full")
            self.controller.mouse_click(self.templates.fish_storage.pos)
            self.wait_until_appear(self.templates.sell, 2.0, "storage_full")
            self.controller.mouse_click(self.templates.sell.pos)
            self.wait_until_appear(self.templates.sell_confirm, 2.0, "storage_full")
            self.controller.mouse_click(self.templates.sell_confirm.pos)
            self.wait_until_appear(self.templates.sell_success, 10.0, "collecting")
            self.controller.mouse_click()
            while not self.stop_event.is_set():
                try:
                    self.wait_until_appear(self.templates.hook, 3.0, "waiting_hook")
                    return
                except TimeoutError:
                    self._click_key("esc")
            raise StopAutomation()

        if self.templates.month_card.match(image):
            self.state.update(message="month_card")
            self.controller.mouse_click()
            self.wait_until_appear(self.templates.get_item, 5.0, "month_card")
            self.controller.mouse_click()
            return

        if self.templates.need_bait.match(image):
            self.state.update(message="buying_bait")
            if not getattr(config, "BUY_BAIT", True):
                self.state.update(status="stopped", message="buying_bait")
                raise StopAutomation()
            self._sleep(2.0)
            self._click_key("r")
            self.wait_until_appear(self.templates.bait, 5.0, "buying_bait")
            self.controller.mouse_click(self.templates.bait.pos)

            for _ in range(getattr(config, "BUY_BAIT_STACK_COUNT", 5)):
                image = self._latest_frame()
                if not self.templates.max.match(image):
                    self.wait_until_appear(self.templates.max, 2.0, "buying_bait")
                if not self.templates.buy.match(image):
                    self.wait_until_appear(self.templates.buy, 2.0, "buying_bait")
                self.controller.mouse_click(self.templates.max.pos)
                self._sleep(0.2)
                self.controller.mouse_click(self.templates.buy.pos)
                self.wait_until_appear(self.templates.confirm, 5.0, "buying_bait")
                self.controller.mouse_click(self.templates.confirm.pos)
                self.wait_until_appear(self.templates.get_item, 5.0, "collecting")
                self.controller.mouse_click()
                self.wait_until_appear(self.templates.bait, 5.0, "buying_bait")

            self._click_key("esc")
            self.wait_until_appear(self.templates.hook, 5.0, "waiting_hook")
            self._click_key("e")
            self.wait_until_appear(self.templates.change, 5.0, "buying_bait")
            self.controller.mouse_click(self.templates.change.pos)
            return

        self.state.update(message="unknown_event")
        self._sleep(0.8)

    def finish_current_fish(self) -> None:
        self.state.update(status="running", message="collecting")
        deadline = time.time() + getattr(config, "CLICK_BLANK_TIMEOUT", 15.0)
        while time.time() < deadline:
            if self.stop_event.is_set():
                raise StopAutomation()
            self._pause_gate()
            frame = self.controller.screenshot()
            if frame is None:
                continue
            if self.templates.click_blank.match(frame, offset=48, similarity=0.78):
                self.controller.mouse_click()
                self._sleep(0.35)
                self.state.increment_fish()
                return
            if self.templates.click_blank.match_anywhere(frame, similarity=0.78):
                self.controller.mouse_click()
                self._sleep(0.35)
                self.state.increment_fish()
                return
            time.sleep(getattr(config, "SCAN_INTERVAL", 0.08))

        self.controller.mouse_click()
        self._sleep(0.35)
        self.state.increment_fish()

    def track_visible_bar(self, tracker: FishBarTracker) -> bool:
        frame = self._latest_frame()
        if not tracker.set_rect(frame):
            return False
        tracker.track()
        self.finish_current_fish()
        return True

    def run(self) -> None:
        self.state.update(status="running", message="finding_window", started_at=time.time(), last_error="")
        try:
            self.controller = GameController(self.state, self.stop_event)
            tracker = FishBarTracker(self.controller, self.templates, self.stop_event, self.pause_event, self.state)

            while not self.stop_event.is_set():
                try:
                    if self.track_visible_bar(tracker):
                        continue

                    if self.wait_until_appear_or_bar(self.templates.hook, 3.0, "waiting_hook", tracker) == "bar":
                        continue
                    self.state.update(message="casting")
                    self._click_key("f")
                    if self.wait_until_appear_or_bar(self.templates.take_bait, 10.0, "waiting_bait", tracker) == "bar":
                        continue
                    self._click_key("f")

                    tracker.reset()
                    tracker.track()
                    self.finish_current_fish()
                except TimeoutError:
                    try:
                        if self.track_visible_bar(tracker):
                            continue
                    except TimeoutError:
                        pass
                    self.handle_event()

        except StopAutomation:
            self.state.update(status="stopped", message="stopped")
        except Exception as exc:
            KeyboardDriver.release_all()
            self.state.update(status="error", message="error", last_error=str(exc))
            log_dir = ROOT / "logs"
            log_dir.mkdir(exist_ok=True)
            with (log_dir / "modern_autofish_error.log").open("a", encoding="utf-8") as handle:
                handle.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}]\n")
                handle.write(traceback.format_exc())
        finally:
            KeyboardDriver.release_all()


class OverlayBar:
    TRANSPARENT = "#010203"

    def __init__(self, state: StateStore) -> None:
        if tk is None:
            raise RuntimeError("tkinter is not available")
        self.state = state
        self.worker: AutomationWorker | None = None
        self.settings_window = None
        self.root = tk.Tk()
        self.root.title("AutoFish Overlay")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", getattr(config, "OVERLAY_ALPHA", 0.94))
        try:
            self.root.attributes("-transparentcolor", self.TRANSPARENT)
        except tk.TclError:
            pass

        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()
        self.width = min(980, max(840, round(self.screen_w * 0.46)))
        self.height = 64
        x = (self.screen_w - self.width) // 2
        y = getattr(config, "OVERLAY_TOP_MARGIN", 14)
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
        self.root.configure(bg=self.TRANSPARENT)
        self.root.update_idletasks()
        self._make_overlay_non_activating()

        self.canvas = tk.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg=self.TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.drag_offset = (0, 0)
        self.canvas.bind("<ButtonPress-1>", self._begin_drag)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)
        self._install_hotkeys()
        self._refresh()
        self.root.after(250, self._make_overlay_non_activating)

        if getattr(config, "AUTO_START", False):
            self.root.after(300, self.start_or_toggle)

    def _begin_drag(self, event) -> None:
        self.drag_offset = (event.x, event.y)

    def _drag(self, event) -> None:
        x = self.root.winfo_x() + event.x - self.drag_offset[0]
        y = self.root.winfo_y() + event.y - self.drag_offset[1]
        self.root.geometry(f"+{x}+{y}")

    def _make_overlay_non_activating(self) -> None:
        if win32gui is None or win32con is None:
            return
        try:
            hwnd = self.root.winfo_id()
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            ex_style |= getattr(win32con, "WS_EX_NOACTIVATE", 0x08000000)
            ex_style |= getattr(win32con, "WS_EX_TOOLWINDOW", 0x00000080)
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0,
                0,
                0,
                0,
                win32con.SWP_NOMOVE
                | win32con.SWP_NOSIZE
                | win32con.SWP_NOACTIVATE
                | win32con.SWP_FRAMECHANGED,
            )
        except Exception:
            pass

    def _avoid_fish_bar_scan_area(self, running: bool) -> None:
        if not running or not getattr(config, "AUTO_AVOID_FISH_BAR", True):
            return
        try:
            _, scan_top, _, scan_bottom = getattr(config, "FISH_BAR_SCAN_REGION", (0.30, 0.052, 0.70, 0.087))
            y1 = round(self.screen_h * scan_top) - 8
            y2 = round(self.screen_h * scan_bottom) + 10
            overlay_y1 = self.root.winfo_y()
            overlay_y2 = overlay_y1 + self.height
            if overlay_y1 < y2 and overlay_y2 > y1:
                new_y = min(self.screen_h - self.height - 12, max(8, y2 + 16))
                self.root.geometry(f"+{self.root.winfo_x()}+{new_y}")
        except Exception:
            pass

    def _rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def _button(self, x: int, y: int, w: int, h: int, label: str, tag: str, fill: str, text_fill: str = "#f8fafc") -> None:
        self._rounded_rect(x, y, x + w, y + h, 10, fill=fill, outline="", tags=(tag, "button"))
        self.canvas.create_text(
            x + w // 2,
            y + h // 2,
            text=label,
            fill=text_fill,
            font=("Segoe UI", 9, "bold"),
            tags=(tag, "button"),
        )

    def _bind_buttons(self) -> None:
        self.canvas.tag_bind("primary", "<Button-1>", lambda _: self.start_or_toggle())
        self.canvas.tag_bind("stop", "<Button-1>", lambda _: self.stop_worker())
        self.canvas.tag_bind("language", "<Button-1>", lambda _: self.switch_language())
        self.canvas.tag_bind("settings", "<Button-1>", lambda _: self.open_settings())
        self.canvas.tag_bind("close", "<Button-1>", lambda _: self.shutdown())
        self.canvas.tag_bind("credit_link", "<Button-1>", lambda _: webbrowser.open("https://del4yowo.id.vn"))

    def _status_color(self, status: str) -> str:
        return {
            "running": "#34d399",
            "paused": "#fbbf24",
            "error": "#fb7185",
            "stopping": "#93c5fd",
            "stopped": "#94a3b8",
            "idle": "#94a3b8",
        }.get(status, "#94a3b8")

    def _refresh(self) -> None:
        data = self.state.snapshot()
        lang = data["language"]
        text = TEXT.get(lang, TEXT["en"])
        status = data["status"]
        message = data["message"]
        running = self.worker is not None and self.worker.is_alive()
        paused = running and self.worker.pause_event.is_set()
        self._avoid_fish_bar_scan_area(running)

        self.canvas.delete("all")
        self._rounded_rect(2, 2, self.width - 2, self.height - 2, 18, fill="#0f172a", outline="#243244", width=1)
        self.canvas.create_rectangle(22, self.height - 8, self.width - 22, self.height - 6, fill="#22d3ee", outline="")
        self.canvas.create_oval(18, 22, 30, 34, fill=self._status_color(status), outline="")
        title_item = self.canvas.create_text(
            42,
            20,
            anchor="w",
            text=text["app_title"],
            fill="#f8fafc",
            font=("Segoe UI", 11, "bold"),
        )
        # Credit text with clickable author link (next to title)
        title_bbox = self.canvas.bbox(title_item)
        credit_x = (title_bbox[2] + 8) if title_bbox else 160
        tmp = self.canvas.create_text(0, 0, text="Made with \u2764 by ", font=("Segoe UI", 7))
        tmp_bbox = self.canvas.bbox(tmp)
        prefix_w = (tmp_bbox[2] - tmp_bbox[0]) if tmp_bbox else 85
        self.canvas.delete(tmp)
        self.canvas.create_text(
            credit_x, 20, anchor="w",
            text="Made with \u2764 by ",
            fill="#64748b", font=("Segoe UI", 7),
        )
        self.canvas.create_text(
            credit_x + prefix_w, 20, anchor="w",
            text="HighDel4y",
            fill="#22d3ee", font=("Segoe UI", 7, "underline"),
            tags=("credit_link",),
        )
        self.canvas.create_text(
            42,
            42,
            anchor="w",
            text=f"{text.get(status, status)} | {text.get(message, message)}",
            fill="#cbd5e1",
            font=("Segoe UI", 9),
        )

        elapsed = "--:--"
        if data["started_at"]:
            seconds = max(0, int(time.time() - data["started_at"]))
            elapsed = f"{seconds // 60:02}:{seconds % 60:02}"
        middle = (
            f"{text['fish']}: {data['fish_count']}   "
            f"{text['res']}: {data['resolution']}   "
            f"{elapsed}"
        )
        self.canvas.create_text(
            self.width // 2 - 10,
            24,
            anchor="center",
            text=middle,
            fill="#e2e8f0",
            font=("Segoe UI", 9, "bold"),
        )
        self.canvas.create_text(
            self.width // 2 - 10,
            44,
            anchor="center",
            text=f"{text['sell']} (BETA): {text['on'] if getattr(config, 'SELL_FISH', False) else text['off']}  "
            f"{text['bait']}: {text['on'] if getattr(config, 'BUY_BAIT', True) else text['off']}  "
            f"{text['hotkeys']}",
            fill="#94a3b8",
            font=("Segoe UI", 8),
        )

        if not running:
            primary_label = text["start"]
            primary_fill = "#0891b2"
        elif paused:
            primary_label = text["resume"]
            primary_fill = "#0d9488"
        else:
            primary_label = text["pause"]
            primary_fill = "#334155"

        right = self.width - 18
        self._button(right - 34, 17, 28, 30, "X", "close", "#1e293b")
        right -= 44
        self._button(right - 52, 17, 52, 30, lang.upper(), "language", "#1e293b")
        right -= 62
        self._button(right - 52, 17, 52, 30, text["settings"], "settings", "#1e293b")
        right -= 62
        self._button(right - 56, 17, 56, 30, text["stop"], "stop", "#3f1d2b")
        right -= 66
        self._button(right - 72, 17, 72, 30, primary_label, "primary", primary_fill)
        self._bind_buttons()

        if data.get("last_error"):
            self.canvas.create_text(
                self.width - 22,
                self.height - 12,
                anchor="e",
                text=data["last_error"][:72],
                fill="#fecdd3",
                font=("Segoe UI", 7),
            )



        self.root.after(100, self._refresh)

    def _format_region(self, values) -> str:
        return ", ".join(f"{float(value):.3f}".rstrip("0").rstrip(".") for value in values)

    def _parse_region(self, text: str, expected_count: int) -> tuple[float, ...]:
        parts = text.replace(",", " ").split()
        if len(parts) != expected_count:
            raise ValueError(f"Expected {expected_count} numbers")
        return tuple(float(part) for part in parts)

    def open_settings(self) -> None:
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            self.settings_window.focus_force()
            return

        settings = current_settings()
        window = tk.Toplevel(self.root)
        self.settings_window = window
        window.title("AutoFish Settings")
        window.configure(bg="#0f172a")
        window.attributes("-topmost", True)
        window.resizable(False, False)
        window.protocol("WM_DELETE_WINDOW", window.destroy)

        if ttk is not None:
            style = ttk.Style(window)
            style.configure("AutoFish.TFrame", background="#0f172a")
            style.configure("AutoFish.TLabel", background="#0f172a", foreground="#e2e8f0")
            style.configure("AutoFish.TCheckbutton", background="#0f172a", foreground="#e2e8f0")
            frame = ttk.Frame(window, padding=16, style="AutoFish.TFrame")
            label_cls = ttk.Label
            check_cls = ttk.Checkbutton
            button_cls = ttk.Button
        else:
            frame = tk.Frame(window, padx=16, pady=16, bg="#0f172a")
            label_cls = tk.Label
            check_cls = tk.Checkbutton
            button_cls = tk.Button

        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        def make_label(parent, text, **kwargs):
            if ttk is not None:
                return label_cls(parent, text=text, style="AutoFish.TLabel", **kwargs)
            return label_cls(parent, text=text, bg="#0f172a", fg="#e2e8f0", **kwargs)

        row = 0

        def add_row(label: str, widget) -> None:
            nonlocal row
            make_label(frame, label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
            widget.grid(row=row, column=1, sticky="ew", pady=4)
            row += 1

        make_label(frame, "Settings", font=("Segoe UI", 12, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 10))
        row += 1

        language_var = tk.StringVar(value=str(settings["LANGUAGE"]))
        language_box = ttk.Combobox(frame, textvariable=language_var, values=("en", "vi"), state="readonly", width=10) if ttk else tk.OptionMenu(frame, language_var, "en", "vi")
        add_row("Language", language_box)

        sell_var = tk.BooleanVar(value=bool(settings["SELL_FISH"]))
        buy_var = tk.BooleanVar(value=bool(settings["BUY_BAIT"]))
        capture_client_var = tk.BooleanVar(value=bool(settings["CAPTURE_CLIENT_AREA"]))
        auto_start_var = tk.BooleanVar(value=bool(settings["AUTO_START"]))
        auto_avoid_var = tk.BooleanVar(value=bool(settings["AUTO_AVOID_FISH_BAR"]))

        for text, var in (
            ("Auto sell fish when storage is full (BETA)", sell_var),
            ("Auto buy bait when empty", buy_var),
            ("Capture client area only", capture_client_var),
            ("Start automatically when overlay opens", auto_start_var),
            ("Move overlay away from fishing gauge", auto_avoid_var),
        ):
            if ttk is not None:
                widget = check_cls(frame, text=text, variable=var, style="AutoFish.TCheckbutton")
            else:
                widget = check_cls(frame, text=text, variable=var, bg="#0f172a", fg="#e2e8f0", selectcolor="#1e293b")
            widget.grid(row=row, column=0, columnspan=2, sticky="w", pady=3)
            row += 1

        bait_stack_var = tk.IntVar(value=int(settings["BUY_BAIT_STACK_COUNT"]))
        add_row("Bait stacks", tk.Spinbox(frame, from_=1, to=99, textvariable=bait_stack_var, width=8))

        safe_var = tk.DoubleVar(value=float(settings["GREEN_BAR_SAFE_PROPORTION"]))
        safe_frame = tk.Frame(frame, bg="#0f172a")
        safe_scale = tk.Scale(
            safe_frame,
            from_=0.10,
            to=0.80,
            resolution=0.05,
            orient="horizontal",
            variable=safe_var,
            length=230,
            bg="#0f172a",
            fg="#e2e8f0",
            highlightthickness=0,
        )
        safe_scale.pack(side="left")
        safe_value = make_label(safe_frame, f"{safe_var.get():.2f}", width=5)
        safe_value.pack(side="left", padx=(8, 0))
        safe_var.trace_add("write", lambda *_: safe_value.configure(text=f"{safe_var.get():.2f}"))
        add_row("Safe center width", safe_frame)

        fps_var = tk.IntVar(value=int(settings["TARGET_FPS"]))
        add_row("Capture FPS", tk.Spinbox(frame, from_=30, to=240, increment=10, textvariable=fps_var, width=8))

        interval_var = tk.StringVar(value=str(settings["SCAN_INTERVAL"]))
        add_row("Scan interval", tk.Entry(frame, textvariable=interval_var, width=12))

        fast_poll_var = tk.StringVar(value=str(settings["FISH_BAR_FAST_POLL_INTERVAL"]))
        add_row("Bar fast poll", tk.Entry(frame, textvariable=fast_poll_var, width=12))

        missing_var = tk.IntVar(value=int(settings["FISH_BAR_MISSING_FRAMES"]))
        add_row("Missing frames", tk.Spinbox(frame, from_=3, to=60, textvariable=missing_var, width=8))

        lost_cursor_var = tk.IntVar(value=int(settings["FISH_BAR_LOST_CURSOR_FRAMES"]))
        add_row("Lost cursor frames", tk.Spinbox(frame, from_=0, to=30, textvariable=lost_cursor_var, width=8))

        appear_timeout_var = tk.StringVar(value=str(settings["FISH_BAR_APPEAR_TIMEOUT"]))
        add_row("Bar appear timeout", tk.Entry(frame, textvariable=appear_timeout_var, width=12))

        click_blank_timeout_var = tk.StringVar(value=str(settings["CLICK_BLANK_TIMEOUT"]))
        add_row("Click blank timeout", tk.Entry(frame, textvariable=click_blank_timeout_var, width=12))

        scan_region_var = tk.StringVar(value=self._format_region(settings["FISH_BAR_SCAN_REGION"]))
        add_row("Bar scan region", tk.Entry(frame, textvariable=scan_region_var, width=34))

        track_region_var = tk.StringVar(value=self._format_region(settings["FISH_BAR_TRACK_REGION"]))
        add_row("Bar track region", tk.Entry(frame, textvariable=track_region_var, width=34))

        alpha_var = tk.DoubleVar(value=float(settings["OVERLAY_ALPHA"]))
        alpha_frame = tk.Frame(frame, bg="#0f172a")
        alpha_scale = tk.Scale(
            alpha_frame,
            from_=0.35,
            to=1.0,
            resolution=0.05,
            orient="horizontal",
            variable=alpha_var,
            length=230,
            bg="#0f172a",
            fg="#e2e8f0",
            highlightthickness=0,
        )
        alpha_scale.pack(side="left")
        alpha_value = make_label(alpha_frame, f"{alpha_var.get():.2f}", width=5)
        alpha_value.pack(side="left", padx=(8, 0))
        alpha_var.trace_add("write", lambda *_: alpha_value.configure(text=f"{alpha_var.get():.2f}"))
        add_row("Overlay opacity", alpha_frame)

        top_margin_var = tk.IntVar(value=int(settings["OVERLAY_TOP_MARGIN"]))
        add_row("Overlay top margin", tk.Spinbox(frame, from_=0, to=300, textvariable=top_margin_var, width=8))

        make_label(frame, "Window titles").grid(row=row, column=0, sticky="nw", padx=(0, 12), pady=4)
        titles_text = tk.Text(frame, width=42, height=4, bg="#111827", fg="#e5e7eb", insertbackground="#e5e7eb", relief="flat")
        titles_text.insert("1.0", "\n".join(settings["WINDOW_TITLES"]))
        titles_text.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        status_label = make_label(frame, "")
        status_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(6, 2))
        row += 1

        def collect_settings() -> dict:
            return {
                "LANGUAGE": language_var.get(),
                "SELL_FISH": sell_var.get(),
                "BUY_BAIT": buy_var.get(),
                "CAPTURE_CLIENT_AREA": capture_client_var.get(),
                "AUTO_START": auto_start_var.get(),
                "AUTO_AVOID_FISH_BAR": auto_avoid_var.get(),
                "BUY_BAIT_STACK_COUNT": bait_stack_var.get(),
                "GREEN_BAR_SAFE_PROPORTION": safe_var.get(),
                "TARGET_FPS": fps_var.get(),
                "SCAN_INTERVAL": float(interval_var.get()),
                "FISH_BAR_FAST_POLL_INTERVAL": float(fast_poll_var.get()),
                "FISH_BAR_MISSING_FRAMES": missing_var.get(),
                "FISH_BAR_LOST_CURSOR_FRAMES": lost_cursor_var.get(),
                "FISH_BAR_APPEAR_TIMEOUT": float(appear_timeout_var.get()),
                "CLICK_BLANK_TIMEOUT": float(click_blank_timeout_var.get()),
                "FISH_BAR_SCAN_REGION": self._parse_region(scan_region_var.get(), 4),
                "FISH_BAR_TRACK_REGION": self._parse_region(track_region_var.get(), 2),
                "OVERLAY_ALPHA": alpha_var.get(),
                "OVERLAY_TOP_MARGIN": top_margin_var.get(),
                "WINDOW_TITLES": titles_text.get("1.0", "end").splitlines(),
            }

        def save_from_panel() -> None:
            try:
                save_settings(collect_settings())
            except Exception as exc:
                status_label.configure(text=f"Error: {exc}")
                if messagebox:
                    messagebox.showerror("NTE AutoFish Settings", str(exc), parent=window)
                return
            self.state.set_language(getattr(config, "LANGUAGE", "en"))
            self.root.attributes("-alpha", getattr(config, "OVERLAY_ALPHA", 0.94))
            status_label.configure(text=f"Saved to {SETTINGS_FILE.name}")
            self.state.update(message="saved", last_error="")

        def reset_defaults() -> None:
            try:
                save_settings(CONFIG_DEFAULTS)
            except Exception as exc:
                status_label.configure(text=f"Error: {exc}")
                return
            window.destroy()
            self.state.set_language(getattr(config, "LANGUAGE", "en"))
            self.open_settings()

        buttons = tk.Frame(frame, bg="#0f172a")
        buttons.grid(row=row, column=0, columnspan=2, sticky="e", pady=(10, 0))
        button_cls(buttons, text="Save", command=save_from_panel).pack(side="left", padx=(0, 8))
        button_cls(buttons, text="Reset defaults", command=reset_defaults).pack(side="left", padx=(0, 8))
        button_cls(buttons, text="Close", command=window.destroy).pack(side="left")

    def _install_hotkeys(self) -> None:
        def watch() -> None:
            vk_f8 = 0x77
            vk_backtick = 0xC0
            last_f8 = False
            last_backtick = False
            while True:
                try:
                    f8 = bool(ctypes.windll.user32.GetAsyncKeyState(vk_f8) & 0x8000)
                    backtick = bool(ctypes.windll.user32.GetAsyncKeyState(vk_backtick) & 0x8000)
                    if f8 and not last_f8:
                        self.root.after(0, self.start_or_toggle)
                    if backtick and not last_backtick:
                        self.root.after(0, self.shutdown)
                    last_f8 = f8
                    last_backtick = backtick
                    time.sleep(0.08)
                except Exception:
                    return

        thread = threading.Thread(target=watch, daemon=True)
        thread.start()

    def start_or_toggle(self) -> None:
        if DEPENDENCY_ERROR is not None:
            self.state.update(status="error", message="deps_missing", last_error=str(DEPENDENCY_ERROR))
            if messagebox:
                messagebox.showerror("NTE AutoFish", f"Missing dependency:\n{DEPENDENCY_ERROR}")
            return
        if not is_admin():
            self.state.update(status="error", message="admin_needed")
            if messagebox:
                messagebox.showerror("NTE AutoFish", "Please run this script as administrator.")
            return

        if self.worker and self.worker.is_alive():
            self.worker.toggle_pause()
            return

        self.state.update(status="running", message="finding_window", fish_count=0, started_at=time.time(), last_error="")
        try:
            self.worker = AutomationWorker(self.state)
        except Exception as exc:
            self.state.update(status="error", message="error", last_error=str(exc))
            if messagebox:
                messagebox.showerror("NTE AutoFish", str(exc))
            return
        self.worker.start()

    def stop_worker(self) -> None:
        if self.worker and self.worker.is_alive():
            self.state.update(status="stopping", message="stopping")
            self.worker.request_stop()
        else:
            self.state.update(status="stopped", message="stopped")

    def switch_language(self) -> None:
        self.state.toggle_language()
        settings = current_settings()
        settings["LANGUAGE"] = self.state.snapshot()["language"]
        try:
            save_settings(settings)
        except Exception as exc:
            self.state.update(status="error", message="error", last_error=str(exc))

    def shutdown(self) -> None:
        self.stop_worker()
        self.root.after(150, self.root.destroy)

    def run(self) -> None:
        self.root.mainloop()


def show_startup_error(message: str) -> None:
    print(message, file=sys.stderr)
    if tk is not None and messagebox is not None:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("NTE AutoFish", message)
        root.destroy()


def main() -> int:
    if tk is None:
        print("tkinter is not available; cannot create overlay UI.", file=sys.stderr)
        return 1
    state = StateStore()
    try:
        app = OverlayBar(state)
        app.run()
    except Exception as exc:
        show_startup_error(str(exc))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
