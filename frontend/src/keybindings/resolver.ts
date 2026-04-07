/** Resolve keyboard events to actions using registered bindings. */

import type { ParsedBinding, KeybindingContextName, Chord } from "./types";
import { parseBinding, matchesKeystroke } from "./parser";
import { DEFAULT_BINDINGS } from "./defaultBindings";

export class KeybindingResolver {
  private bindings: Map<string, ParsedBinding[]> = new Map();
  private pendingChord: Chord | null = null;
  private pendingTimeout: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    this.loadBindings(DEFAULT_BINDINGS);
  }

  loadBindings(bindings: Array<{ action: string; keys: string; context: KeybindingContextName }>) {
    this.bindings.clear();
    for (const binding of bindings) {
      const parsed = parseBinding(binding.keys);
      const key = `${binding.context}:${binding.action}`;
      const pb: ParsedBinding = { chord: parsed, action: binding.action, context: binding.context };
      if (!this.bindings.has(key)) {
        this.bindings.set(key, []);
      }
      this.bindings.get(key)!.push(pb);
    }
  }

  resolve(event: KeyboardEvent, context: KeybindingContextName): string | null {
    // Check for chord completion
    if (this.pendingChord) {
      // Match pending chord
      // If complete, execute; otherwise continue waiting
    }

    // Find matching binding for context
    for (const [_key, pbs] of this.bindings) {
      for (const pb of pbs) {
        if (pb.context !== context && pb.context !== "Global") continue;
        if (pb.chord.length === 1 && matchesKeystroke(event, pb.chord[0])) {
          this.pendingChord = null;
          return pb.action;
        }
      }
    }

    return null;
  }

  cancelPendingChord() {
    this.pendingChord = null;
    if (this.pendingTimeout) {
      clearTimeout(this.pendingTimeout);
      this.pendingTimeout = null;
    }
  }

  getBindingsForContext(context: KeybindingContextName): ParsedBinding[] {
    const result: ParsedBinding[] = [];
    for (const [_key, pbs] of this.bindings) {
      for (const pb of pbs) {
        if (pb.context === context || pb.context === "Global") {
          result.push(pb);
        }
      }
    }
    return result;
  }
}

export const keybindingResolver = new KeybindingResolver();
