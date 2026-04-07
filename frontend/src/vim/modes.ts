/** Vim mode transitions. */

import { VimMode } from "./types";

export const MODE_TRANSITIONS: Record<VimMode, Record<string, VimMode>> = {
  [VimMode.Normal]: {
    i: VimMode.Insert,
    a: VimMode.Insert,
    A: VimMode.Insert,
    I: VimMode.Insert,
    o: VimMode.Insert,
    O: VimMode.Insert,
    v: VimMode.Visual,
    V: VimMode.VisualLine,
    ":": VimMode.Command,
    "/": VimMode.Command,
  },
  [VimMode.Insert]: {
    escape: VimMode.Normal,
    ctrl_c: VimMode.Normal,
    ctrl_bracket: VimMode.Normal,
  },
  [VimMode.Visual]: {
    escape: VimMode.Normal,
    v: VimMode.Normal,
    V: VimMode.VisualLine,
  },
  [VimMode.VisualLine]: {
    escape: VimMode.Normal,
    v: VimMode.Normal,
    V: VimMode.Normal,
  },
  [VimMode.Command]: {
    enter: VimMode.Normal,
    escape: VimMode.Normal,
  },
};

export function getNextMode(current: VimMode, key: string): VimMode {
  const transitions = MODE_TRANSITIONS[current];
  return transitions[key] ?? current;
}