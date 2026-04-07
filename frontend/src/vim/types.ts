/** Vim mode types. */

export enum VimMode {
  Normal = "normal",
  Insert = "insert",
  Visual = "visual",
  VisualLine = "visual-line",
  Command = "command",
}

export interface VimState {
  mode: VimMode;
  line: string;
  position: number;
  registers: Record<string, string>;
  lastAction: string | null;
  lastMotion: string | null;
  count: number;
  operatorPending: string | null;
}

export interface VimMotion {
  name: string;
  description: string;
  motion: (state: VimState) => number;
}

export interface VimOperator {
  name: string;
  description: string;
  execute: (state: VimState, motion?: VimMotion) => string;
}