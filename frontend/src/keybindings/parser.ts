/** Parse keyboard shortcut strings into structured keystrokes. */

import type { ParsedKeystroke, Chord } from "./types";

const MODIFIER_KEYS = ["ctrl", "alt", "shift", "meta", "super", "cmd", "command", "control", "option"];
const KEY_ALIASES: Record<string, string> = {
  "cmd": "super",
  "command": "super",
  "control": "ctrl",
  "option": "alt",
  "esc": "escape",
  "cr": "enter",
  "lf": "enter",
  "space": " ",
  "spc": " ",
};

export function parseKeystroke(input: string): ParsedKeystroke {
  const parts = input.toLowerCase().split(/[\s\+]+/).filter(Boolean);
  const keystroke: ParsedKeystroke = {
    key: "",
    ctrl: false,
    alt: false,
    shift: false,
    meta: false,
    super: false,
  };

  for (const part of parts) {
    const normalized = KEY_ALIASES[part] || part;
    if (MODIFIER_KEYS.includes(normalized)) {
      switch (normalized) {
        case "ctrl": keystroke.ctrl = true; break;
        case "alt": keystroke.alt = true; break;
        case "shift": keystroke.shift = true; break;
        case "meta": keystroke.meta = true; break;
        case "super": keystroke.super = true; break;
      }
    } else {
      keystroke.key = normalized;
    }
  }

  return keystroke;
}

export function parseBinding(input: string): Chord {
  return input.split(/\s+/).map(parseKeystroke);
}

const isMac = typeof navigator !== "undefined" && /Mac|iPod|iPhone|iPad/.test(navigator.platform ?? navigator.userAgent);

export function keystrokeToString(keystroke: ParsedKeystroke): string {
  const parts: string[] = [];
  if (keystroke.ctrl) parts.push("Ctrl");
  if (keystroke.alt) parts.push("Alt");
  if (keystroke.shift) parts.push("Shift");
  if (keystroke.meta || keystroke.super) parts.push(isMac ? "Cmd" : "Super");
  parts.push(keystroke.key.toUpperCase());
  return parts.join("+");
}

export function matchesKeystroke(event: KeyboardEvent, keystroke: ParsedKeystroke): boolean {
  const key = event.key.toLowerCase();
  const expectedKey = keystroke.key.toLowerCase();
  
  if (key !== expectedKey) return false;
  if (keystroke.ctrl !== (event.ctrlKey || event.metaKey && !isMac)) return false;
  if (keystroke.alt !== event.altKey) return false;
  if (keystroke.shift !== event.shiftKey) return false;
  
  return true;
}
