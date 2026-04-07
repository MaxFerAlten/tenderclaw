/** Vim operators implementation. */

import { VimState } from "./types";

export const OPERATORS: Record<string, (state: VimState, _motion?: string) => string> = {
  d: (state) => {
    const { line, position } = state;
    return line.slice(0, position) + line.slice(position + 1);
  },
  y: (state) => {
    return state.line;
  },
  c: (state) => {
    const { line, position } = state;
    return line.slice(0, position) + line.slice(position + 1);
  },
  x: (state) => {
    const { line, position } = state;
    return line.slice(0, position) + line.slice(position + 1);
  },
  p: (state) => {
    const reg = state.registers[""] || "";
    const { line, position } = state;
    return line.slice(0, position + 1) + reg + line.slice(position + 1);
  },
};

export function executeOperator(op: string, state: VimState, motion?: string): string {
  const fn = OPERATORS[op];
  if (fn) {
    return fn(state, motion);
  }
  return state.line;
}