/** Keybinding context provider for React. */

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import type { KeybindingContextName } from "./types";
import { keybindingResolver } from "./resolver";
import { DEFAULT_BINDINGS } from "./defaultBindings";

interface KeybindingContextValue {
  context: KeybindingContextName;
  setContext: (context: KeybindingContextName) => void;
  registerAction: (action: string, handler: () => void) => () => void;
  showHelp: boolean;
  setShowHelp: (show: boolean) => void;
}

const KeybindingContext = createContext<KeybindingContextValue | null>(null);

export function KeybindingProvider({ children }: { children: ReactNode }) {
  const [context, setContext] = useState<KeybindingContextName>("Chat");
  const [handlers, setHandlers] = useState<Map<string, () => void>>(new Map());
  const [showHelp, setShowHelp] = useState(false);

  useEffect(() => {
    keybindingResolver.loadBindings(DEFAULT_BINDINGS);
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) {
        if (!(e.ctrlKey || e.metaKey)) return;
      }

      const action = keybindingResolver.resolve(e, context);
      if (action) {
        const handler = handlers.get(action);
        if (handler) {
          e.preventDefault();
          handler();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [context, handlers]);

  const registerAction = useCallback((action: string, handler: () => void) => {
    setHandlers((prev) => new Map(prev).set(action, handler));
    return () => {
      setHandlers((prev) => {
        const next = new Map(prev);
        next.delete(action);
        return next;
      });
    };
  }, []);

  return (
    <KeybindingContext.Provider
      value={{ context, setContext, registerAction, showHelp, setShowHelp }}
    >
      {children}
    </KeybindingContext.Provider>
  );
}

export function useKeybindingContext() {
  const ctx = useContext(KeybindingContext);
  if (!ctx) throw new Error("useKeybindingContext must be used within KeybindingProvider");
  return ctx;
}
