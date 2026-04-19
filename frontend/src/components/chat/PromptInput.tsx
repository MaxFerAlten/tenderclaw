/**
 * PromptInput — message input with submit button and keyboard shortcuts.
 */

import { useState, useRef, useCallback, useEffect } from "react";
import { Image as ImageIcon, Square, X, Zap } from "lucide-react";
import type { ChatAttachment, PowerLevel } from "../../api/types";
import { useSessionStore } from "../../stores/sessionStore";
import { ws } from "../../api/ws";
import { VoiceButton } from "../voice/VoiceButton";
import { useVoiceMode } from "../voice/useVoiceMode";

interface Props {
  onSend: (content: string, attachments: ChatAttachment[], powerLevel: PowerLevel) => void;
}

const MAX_IMAGES = 4;
const MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024;
const POWER_LEVEL_OPTIONS: Array<{ value: PowerLevel; label: string }> = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "extra_high", label: "Extra high" },
  { value: "max", label: "Max" },
];

export function PromptInput({ onSend }: Props) {
  const [value, setValue] = useState("");
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [pasteError, setPasteError] = useState("");
  const [powerLevel, setPowerLevel] = useState<PowerLevel>("medium");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const status = useSessionStore((s) => s.status);
  const sessionId = useSessionStore((s) => s.sessionId);
  const wsStatus = useSessionStore((s) => s.wsStatus);
  const isBusy = status === "busy";
  const canSend = Boolean(sessionId) && wsStatus === "connected" && !isBusy;
  const hasDraft = value.trim().length > 0 || attachments.length > 0;
  const powerLevelIndex = Math.max(
    0,
    POWER_LEVEL_OPTIONS.findIndex((option) => option.value === powerLevel),
  );
  const selectedPower = POWER_LEVEL_OPTIONS[powerLevelIndex];

  const { isListening, isSupported, toggleListening } = useVoiceMode({
    onTranscript: (t) => {
      if (t.final) {
        setValue((prev) => prev + " " + t.final);
      }
    },
  });

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim();
    if (!hasDraft || !canSend) return;
    onSend(trimmed, attachments, powerLevel);
    setValue("");
    setAttachments([]);
    setPasteError("");
    textareaRef.current?.focus();
  }, [attachments, hasDraft, value, canSend, onSend, powerLevel]);

  const handleStop = useCallback(() => {
    ws.sendAbort();
  }, []);

  const handlePaste = useCallback(async (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const imageFiles = getClipboardImageFiles(e.clipboardData);
    if (imageFiles.length === 0) return;

    e.preventDefault();
    setPasteError("");

    const pastedText = e.clipboardData.getData("text/plain");
    if (pastedText) {
      setValue((prev) => `${prev}${pastedText}`);
    }

    const availableSlots = MAX_IMAGES - attachments.length;
    if (availableSlots <= 0) {
      setPasteError(`You can attach up to ${MAX_IMAGES} images.`);
      return;
    }

    const accepted = imageFiles.slice(0, availableSlots);
    const oversized = accepted.find((file) => file.size > MAX_IMAGE_SIZE_BYTES);
    if (oversized) {
      setPasteError(`${oversized.name || "Image"} is larger than 5 MB.`);
      return;
    }

    try {
      const next = await Promise.all(
        accepted.map(async (file, index) => ({
          type: file.type || "image/png",
          url: await readFileAsDataUrl(file),
          name: file.name || `pasted-image-${attachments.length + index + 1}.png`,
          size_bytes: file.size,
        })),
      );
      setAttachments((prev) => [...prev, ...next]);
      if (imageFiles.length > availableSlots) {
        setPasteError(`Only ${availableSlots} more image${availableSlots === 1 ? "" : "s"} can be attached.`);
      }
    } catch (err) {
      setPasteError(err instanceof Error ? err.message : "Failed to read pasted image.");
    }
  }, [attachments.length]);

  const removeAttachment = useCallback((index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
    setPasteError("");
  }, []);

  const adjustTextareaHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const newHeight = Math.min(el.scrollHeight, 200);
    el.style.height = `${newHeight}px`;
  }, []);

  const handleInput = useCallback(() => {
    setValue((prev) => prev);
    adjustTextareaHeight();
  }, [adjustTextareaHeight]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  useEffect(() => {
    adjustTextareaHeight();
  }, [value, adjustTextareaHeight]);

  return (
    <div className="border-t border-zinc-800 bg-zinc-950 p-4">
      <div className="flex items-end gap-3 max-w-3xl mx-auto">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder={
            isBusy
              ? "Working..."
              : wsStatus === "connected"
                ? "Type a message... (Enter to send, Shift+Enter for newline)"
                : "Connecting..."
          }
          disabled={!canSend}
          rows={1}
          className="flex-1 resize-none rounded-xl bg-zinc-900 border border-zinc-700 px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 disabled:opacity-50 overflow-x-auto whitespace-pre-wrap break-all"
          style={{ minHeight: "44px", maxHeight: "200px" }}
          onInput={handleInput}
        />
        <VoiceButton
          isListening={isListening}
          isSupported={isSupported}
          onClick={toggleListening}
          size="md"
        />
        {isBusy ? (
          <button
            onClick={handleStop}
            className="rounded-xl bg-red-600 hover:bg-red-500 px-5 py-3 text-sm font-medium text-white transition-colors flex items-center gap-2"
          >
            <Square className="w-4 h-4" />
            Stop
          </button>
        ) : (
          <div className="flex flex-col items-end gap-2">
            <button
              onClick={handleSubmit}
              disabled={!hasDraft || !canSend}
              className="rounded-xl bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-800 disabled:text-zinc-600 px-5 py-3 text-sm font-medium text-white transition-colors"
            >
              Send
            </button>
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <Zap className="w-3.5 h-3.5" />
              <input
                aria-label="Power level"
                type="range"
                min="0"
                max={POWER_LEVEL_OPTIONS.length - 1}
                value={powerLevelIndex}
                onChange={(e) => {
                  const option = POWER_LEVEL_OPTIONS[Number(e.target.value)];
                  setPowerLevel(option.value);
                }}
                className="w-28 h-1.5 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-violet-500"
              />
              <span className="w-20 text-right">{selectedPower.label}</span>
            </div>
          </div>
        )}
      </div>
      {(attachments.length > 0 || pasteError) && (
        <div className="max-w-3xl mx-auto mt-3">
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {attachments.map((attachment, index) => (
                <div
                  key={`${attachment.name ?? "image"}-${index}`}
                  className="relative h-20 w-20 overflow-hidden rounded-lg border border-zinc-700 bg-zinc-900"
                >
                  <img
                    src={attachment.url}
                    alt={attachment.name ?? "Pasted image"}
                    className="h-full w-full object-cover"
                  />
                  <button
                    type="button"
                    onClick={() => removeAttachment(index)}
                    className="absolute right-1 top-1 flex h-6 w-6 items-center justify-center rounded-md bg-black/70 text-zinc-200 hover:bg-red-600"
                    title="Remove image"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                  <div className="absolute bottom-0 left-0 right-0 flex items-center gap-1 bg-black/70 px-1.5 py-1 text-[10px] text-zinc-200">
                    <ImageIcon className="h-3 w-3 shrink-0" />
                    <span className="truncate">{formatBytes(attachment.size_bytes ?? 0)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
          {pasteError && <div className="mt-2 text-xs text-red-400">{pasteError}</div>}
        </div>
      )}
    </div>
  );
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
      } else {
        reject(new Error("Unsupported image data."));
      }
    };
    reader.onerror = () => reject(new Error("Failed to read pasted image."));
    reader.readAsDataURL(file);
  });
}

function getClipboardImageFiles(clipboardData: DataTransfer): File[] {
  const files = Array.from(clipboardData.files).filter((file) => file.type.startsWith("image/"));
  if (files.length > 0) return files;

  return Array.from(clipboardData.items)
    .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
    .map((item) => item.getAsFile())
    .filter((file): file is File => file !== null);
}

function formatBytes(bytes: number): string {
  if (!bytes) return "image";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
