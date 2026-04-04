/**
 * Spinner — loading indicator.
 */

interface Props {
  size?: "sm" | "md" | "lg";
}

const sizes = { sm: "w-4 h-4", md: "w-6 h-6", lg: "w-8 h-8" };

export function Spinner({ size = "md" }: Props) {
  return (
    <div
      className={`${sizes[size]} animate-spin rounded-full border-2 border-zinc-600 border-t-violet-500`}
    />
  );
}
