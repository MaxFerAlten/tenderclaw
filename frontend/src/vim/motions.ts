/** Vim motions implementation. */

import { VimState } from "./types";

export function wordEnd(text: string, pos: number): number {
  const len = text.length;
  while (pos < len && !/\s/.test(text[pos])) pos++;
  while (pos < len && /\s/.test(text[pos])) pos++;
  return Math.min(pos, len);
}

export function wordStart(text: string, pos: number): number {
  while (pos > 0 && /\s/.test(text[pos - 1])) pos--;
  while (pos > 0 && !/\s/.test(text[pos - 1])) pos--;
  return pos;
}

export function lineStart(_text: string, _pos: number): number {
  return 0;
}

export function lineEnd(state: VimState): number {
  const newline = state.line.indexOf("\n");
  if (newline === -1) return state.line.length;
  return newline;
}

export function charForward(state: VimState): number {
  return Math.min(state.position + 1, state.line.length);
}

export function charBackward(state: VimState): number {
  return Math.max(state.position - 1, 0);
}

export const MOTIONS: Record<string, (state: VimState) => number> = {
  h: charBackward,
  arrowleft: charBackward,
  l: charForward,
  arrowright: charForward,
  w: (s) => wordEnd(s.line, s.position),
  b: (s) => wordStart(s.line, s.position),
  e: (s) => {
    const end = wordEnd(s.line, s.position);
    return end > 0 ? end - 1 : 0;
  },
  "0": () => 0,
  "^": (s) => {
    const match = s.line.match(/^(\s*)/);
    return match?.[1].length ?? 0;
  },
  $: lineEnd,
  gg: () => 0,
  G: (s) => s.line.length,
};

export function executeMotion(motion: string, state: VimState): number {
  const fn = MOTIONS[motion];
  if (fn) {
    return fn(state);
  }
  return state.position;
}