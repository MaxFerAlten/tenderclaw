/** KeyboardShortcutsHelp — modal showing all keyboard shortcuts. */

import { X } from "lucide-react";
import { DEFAULT_BINDINGS } from "../../keybindings/defaultBindings";

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export function KeyboardShortcutsHelp({ isOpen, onClose }: Props) {
  if (!isOpen) return null;

  const groupedBindings = DEFAULT_BINDINGS.reduce((acc, binding) => {
    const category = binding.context;
    if (!acc[category]) acc[category] = [];
    acc[category].push(binding);
    return acc;
  }, {} as Record<string, typeof DEFAULT_BINDINGS>);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative w-full max-w-2xl max-h-[80vh] bg-zinc-900 rounded-xl border border-zinc-700 shadow-2xl flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-700">
          <h2 className="text-lg font-bold">Keyboard Shortcuts</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-zinc-800">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {Object.entries(groupedBindings).map(([category, bindings]) => (
            <div key={category}>
              <h3 className="text-sm font-semibold text-zinc-400 mb-2 uppercase tracking-wide">
                {category}
              </h3>
              <div className="space-y-1">
                {bindings.map((binding) => (
                  <div key={binding.action} className="flex items-center justify-between py-1">
                    <span className="text-sm text-zinc-300">{binding.description}</span>
                    <kbd className="px-2 py-1 bg-zinc-800 rounded text-xs font-mono text-zinc-400">
                      {binding.keys}
                    </kbd>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}