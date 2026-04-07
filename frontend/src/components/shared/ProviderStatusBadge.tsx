/**
 * ProviderStatusBadge — colored dot indicating provider key/validation status.
 *
 * States:
 *   green  = key set + validated
 *   yellow = key set, not yet validated
 *   red    = validation failed / error
 *   gray   = no key configured
 */

interface ProviderStatusBadgeProps {
  keySet: boolean;
  validated: boolean;
  error?: string;
  /** Show a tooltip with the error message */
  showTooltip?: boolean;
}

export function ProviderStatusBadge({
  keySet,
  validated,
  error = "",
  showTooltip = true,
}: ProviderStatusBadgeProps) {
  let colorClass = "bg-zinc-600";
  let title = "No API key configured";

  if (keySet && validated) {
    colorClass = "bg-green-500";
    title = "Key validated ✓";
  } else if (keySet && error) {
    colorClass = "bg-red-500";
    title = `Validation failed: ${error}`;
  } else if (keySet) {
    colorClass = "bg-amber-400";
    title = "Key set — click Test to validate";
  }

  return (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full ${colorClass} shrink-0`}
      title={showTooltip ? title : undefined}
    />
  );
}
