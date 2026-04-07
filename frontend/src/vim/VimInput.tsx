/** VimInput — text input with Vim keybindings. */

import { useState, useEffect, useCallback, useRef } from "react";
import { VimMode, VimState } from "./types";
import { getNextMode } from "./modes";
import { executeMotion } from "./motions";

interface VimInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit?: () => void;
  placeholder?: string;
  className?: string;
}

export function VimInput({ value, onChange, onSubmit, placeholder, className = "" }: VimInputProps) {
  const [mode, setMode] = useState<VimMode>(VimMode.Insert);
  const [position, setPosition] = useState(0);
  const [buffer, setBuffer] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  
  const state: VimState = {
    mode,
    line: value,
    position,
    registers: {},
    lastAction: null,
    lastMotion: null,
    count: 1,
    operatorPending: null,
  };

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    const key = e.key.toLowerCase();
    const ctrlKey = e.ctrlKey || e.metaKey;
    
    if (mode === VimMode.Command) {
      if (key === "escape" || key === "enter" && buffer === "") {
        setMode(VimMode.Normal);
        setBuffer("");
        e.preventDefault();
        return;
      }
      if (key === "enter") {
        if (buffer === "wq" || buffer === "x") {
          onSubmit?.();
        }
        setMode(VimMode.Normal);
        setBuffer("");
        e.preventDefault();
        return;
      }
      setBuffer((b) => b + key);
      e.preventDefault();
      return;
    }

    if (mode === VimMode.Insert) {
      if (ctrlKey && key === "c") {
        setMode(VimMode.Normal);
        e.preventDefault();
        return;
      }
      if (key === "escape") {
        setMode(VimMode.Normal);
        setPosition(value.length);
        e.preventDefault();
        return;
      }
      return;
    }

    if (mode === VimMode.Normal || mode === VimMode.Visual) {
      if (key === "escape") {
        setMode(VimMode.Normal);
        setPosition(0);
        e.preventDefault();
        return;
      }

      const motionKeys = ["h", "l", "w", "b", "e", "0", "^", "$", "arrowleft", "arrowright", "arrowup", "arrowdown"];
      if (motionKeys.includes(key)) {
        const newPos = executeMotion(key, { ...state, line: value });
        setPosition(newPos);
        e.preventDefault();
        return;
      }

      const operatorKeys = ["d", "y", "c", "x", "p"];
      if (operatorKeys.includes(key)) {
        setMode(VimMode.Normal);
        e.preventDefault();
        return;
      }

      if (key === "i" || key === "a" || key === "I" || key === "A" || key === "o" || key === "O") {
        const newMode = getNextMode(mode, key);
        setMode(newMode);
        if (key === "a") setPosition(Math.min(position + 1, value.length));
        if (key === "A") setPosition(value.length);
        if (key === "o") {
          onChange(value + "\n");
          setPosition(value.length + 1);
        }
        if (key === "O") {
          onChange("\n" + value);
          setPosition(0);
        }
        e.preventDefault();
        return;
      }

      if (key === "v") {
        setMode(VimMode.Visual);
        e.preventDefault();
        return;
      }

      if (key === ":") {
        setMode(VimMode.Command);
        setBuffer("");
        e.preventDefault();
        return;
      }

      if (key === "/") {
        setMode(VimMode.Command);
        setBuffer("");
        e.preventDefault();
        return;
      }

      if (key === "enter" && mode === VimMode.Normal) {
        onSubmit?.();
        e.preventDefault();
        return;
      }
    }
  }, [mode, value, position, buffer, onChange, onSubmit]);

  useEffect(() => {
    setPosition(Math.min(position, value.length));
  }, [value.length]);

  return (
    <div className={`relative ${className}`}>
      <div className="absolute left-3 top-1/2 -translate-y-1/2 text-xs font-mono text-zinc-500">
        {mode === VimMode.Insert && "-- INSERT --"}
        {mode === VimMode.Normal && ""}
        {mode === VimMode.Visual && "-- VISUAL --"}
        {mode === VimMode.Command && `:${buffer}`}
      </div>
      
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        className="w-full pl-24 pr-4 py-3 bg-zinc-900 border border-zinc-700 rounded-lg text-zinc-200 focus:outline-none focus:border-blue-500"
      />
    </div>
  );
}