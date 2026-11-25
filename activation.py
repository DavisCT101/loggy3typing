"""Types mycode.txt into VS Code with real key presses (Windows).

Setup:   pip install pyautogui
Run:     python typer_keys.py
Stop:    hold Esc, or slam the mouse into the top-left corner of the screen.
"""

import ctypes
import random
import subprocess
import sys
import time
from pathlib import Path

try:
    import pyautogui
except ImportError:
    print("Missing dependency. Run:  pip install pyautogui")
    raise SystemExit(1)

# ---------------- Settings ----------------
SOURCE_FILE = "Mycode.txt"            # the code to type
OUTPUT_FILE = "sortingAlgorithm.c"     # file opened in VS Code
OPEN_IN_VSCODE = True                 # runs: code presented_code.py
WINDOW_MATCH = "Visual Studio Code"   # typing only happens while this is in the window title
START_DELAY = 15                      # seconds to wait so you can click inside the editor
MAX_SESSION_HOURS = 5                 # hard stop
HOLD_UNTIL_END = False                # True = keep the script alive until MAX_SESSION_HOURS

# End-of-line pauses (seconds): the first few are fixed, then random
INITIAL_LINE_PAUSES = [20.0, 30.0, 15.0, 50.0]
MIN_RANDOM_PAUSE = 2.0
MAX_RANDOM_PAUSE = 25.0

# Per-character typing speed (seconds)
MIN_CHAR_DELAY = 0.05
MAX_CHAR_DELAY = 0.16

TYPO_CHANCE = 0.02                    # per letter; every typo is corrected
CLEAN_AUTO_INDENT = True              # after Enter, delete any indent VS Code inserted itself
# ------------------------------------------

if sys.platform != "win32":
    print("This version uses the Windows API to check the active window. Windows only.")
    raise SystemExit(1)

pyautogui.PAUSE = 0
pyautogui.FAILSAFE = True

user32 = ctypes.windll.user32

NEIGHBORS = {
    "a": "sqwz", "b": "vghn", "c": "xdfv", "d": "serfcx", "e": "wsdr", "f": "drtgvc",
    "g": "ftyhbv", "h": "gyujnb", "i": "ujko", "j": "huikmn", "k": "jiolm", "l": "kop",
    "m": "njk", "n": "bhjm", "o": "iklp", "p": "ol", "q": "wa", "r": "edft", "s": "awedxz",
    "t": "rfgy", "u": "yhji", "v": "cfgb", "w": "qase", "x": "zsdc", "y": "tghu", "z": "asx",
}


class StopTyping(Exception):
    pass


def active_title() -> str:
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def esc_held() -> bool:
    return bool(user32.GetAsyncKeyState(0x1B) & 0x8000)


def remaining_text(end_time: float) -> str:
    rem = max(0, int(end_time - time.monotonic()))
    h, r = divmod(rem, 3600)
    m, s = divmod(r, 60)
    return f"{h:02}:{m:02}:{s:02}"


def show_status(end_time: float, text: str) -> None:
    print(f"\rRemaining: {remaining_text(end_time)} | {text}   ", end="", flush=True)


def check(end_time: float) -> None:
    if esc_held():
        raise StopTyping("Stopped (Esc held).")
    if time.monotonic() >= end_time:
        raise StopTyping("Session timer reached.")


def wait_for_vscode(end_time: float) -> None:
    warned = False
    while WINDOW_MATCH not in active_title():
        check(end_time)
        if not warned:
            print("\nVS Code is not focused - paused...")
            warned = True
        time.sleep(0.4)
    if warned:
        time.sleep(0.8)


def pause(seconds: float, end_time: float, status: str) -> None:
    target = time.monotonic() + seconds
    while time.monotonic() < target:
        check(end_time)
        left = max(0.0, target - time.monotonic())
        show_status(end_time, f"{status} (pause {left:4.1f}s)")
        time.sleep(min(0.25, left))


def line_pause(line_num: int) -> float:
    idx = line_num - 1
    if idx < len(INITIAL_LINE_PAUSES):
        return INITIAL_LINE_PAUSES[idx]
    return random.uniform(MIN_RANDOM_PAUSE, MAX_RANDOM_PAUSE)


def type_char(ch: str) -> None:
    if ch == "\t":
        pyautogui.press("tab")
    else:
        pyautogui.write(ch, interval=0)


def type_line(line: str, line_idx: int, total: int, end_time: float) -> None:
    leading = len(line) - len(line.lstrip(" "))
    for index, ch in enumerate(line):
        check(end_time)
        wait_for_vscode(end_time)

        # Indentation is typed quickly, like holding the space bar or pressing tab
        if index < leading:
            type_char(ch)
            time.sleep(random.uniform(0.02, 0.06))
            continue

        # Occasional typo that is noticed and fixed
        if ch.lower() in NEIGHBORS and random.random() < TYPO_CHANCE:
            wrong = random.choice(NEIGHBORS[ch.lower()])
            type_char(wrong)
            time.sleep(random.uniform(0.25, 0.7))
            pyautogui.press("backspace")
            time.sleep(random.uniform(0.1, 0.25))

        type_char(ch)

        delay = random.uniform(MIN_CHAR_DELAY, MAX_CHAR_DELAY)
        if ch in " .,:=()[]{}":
            delay += random.uniform(0.03, 0.14)
        if ch == " " and random.random() < 0.04:
            delay += random.uniform(0.3, 0.9)  # brief hesitation mid-line
        time.sleep(delay)

        if index % 4 == 0:
            show_status(end_time, f"Typing line {line_idx}/{total}")


def press_enter() -> None:
    pyautogui.press("enter")
    time.sleep(0.12)
    if CLEAN_AUTO_INDENT:
        # Select and delete whatever whitespace VS Code added on the new line
        pyautogui.hotkey("shift", "home")
        pyautogui.press("delete")


def run() -> None:
    folder = Path(__file__).resolve().parent
    source = folder / SOURCE_FILE
    output = folder / OUTPUT_FILE

    if not source.exists():
        print(f"Please create {SOURCE_FILE} first.")
        raise SystemExit(1)

    raw_text = source.read_text(encoding="utf-8")
    if not raw_text.strip():
        print(f"{SOURCE_FILE} is empty.")
        raise SystemExit(1)

    if any(ord(c) > 127 for c in raw_text):
        print("Warning: the file has non-ASCII characters. They cannot be typed and will be skipped.")

    lines = raw_text.splitlines(keepends=True)
    output.write_text("", encoding="utf-8")

    if OPEN_IN_VSCODE:
        print(f"Opening {OUTPUT_FILE} in VS Code...")
        subprocess.Popen(["code", str(output)], shell=True)

    print(f"Starting in {START_DELAY}s. Click inside the blank editor now. Hold Esc to cancel.")
    for s in range(START_DELAY, 0, -1):
        if esc_held():
            print("\nCancelled.")
            return
        print(f"\rStarting in {s:2d}s...   ", end="", flush=True)
        time.sleep(1)
    print()

    end_time = time.monotonic() + MAX_SESSION_HOURS * 3600
    total = len(lines)

    for line_idx, line in enumerate(lines, start=1):
        check(end_time)
        wait_for_vscode(end_time)

        has_newline = line.endswith("\n")
        content = line.rstrip("\r\n")

        # Occasional "reading what I just wrote" pause before a line
        if random.random() < 0.12:
            pause(random.uniform(1.5, 5.0), end_time, f"Reading before line {line_idx}/{total}")

        type_line(content, line_idx, total, end_time)

        if has_newline:
            wait_for_vscode(end_time)
            press_enter()

        if line_idx < total:
            pause(line_pause(line_idx), end_time, f"After line {line_idx}/{total}")

    print("\nAll lines typed.")

    if HOLD_UNTIL_END:
        while True:
            check(end_time)
            show_status(end_time, "Code finished (holding session)")
            time.sleep(1)


def main() -> None:
    try:
        run()
    except StopTyping as stop:
        print(f"\n{stop}")
    except pyautogui.FailSafeException:
        print("\nStopped (mouse moved to the screen corner).")
    except KeyboardInterrupt:
        print("\nStopped by user.")


if __name__ == "__main__":
    main()