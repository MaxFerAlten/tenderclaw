/** Keybindings types for TenderClaw. */

export interface ParsedKeystroke {
  key: string;
  ctrl: boolean;
  alt: boolean;
  shift: boolean;
  meta: boolean;
  super: boolean;
}

export type Chord = ParsedKeystroke[];

export interface ParsedBinding {
  chord: Chord;
  action: string;
  context: KeybindingContextName;
}

export type KeybindingContextName =
  | "Global"
  | "Chat"
  | "Settings"
  | "HistorySearch"
  | "HistoryDetail"
  | "Canvas"
  | "AgentEditor"
  | "SkillsMenu"
  | "PromptInput";

export interface KeybindingAction {
  action: string;
  description: string;
  category: string;
}

export interface UserKeybinding {
  action: string;
  chord: Chord;
}
