/** Path helpers for the Terminal surface. */

export function terminalPath(signalId?: string | null): string {
  const id = signalId?.trim();
  if (!id) return "/terminal";
  return `/terminal?signal=${encodeURIComponent(id)}`;
}
