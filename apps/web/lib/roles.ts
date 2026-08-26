import type { User } from "@/types";

export const ROLE_SUPERADMIN = "superadmin";
export const ROLE_SELLER = "seller";
// Pre-dates the role system; those accounts were the agency owner.
const ROLE_LEGACY_ADMIN = "admin";

/**
 * Whether the user has full agency visibility.
 *
 * This drives what the UI *shows*. It is not a security boundary: every
 * endpoint enforces the same rule server-side, so hiding a link never has to
 * be relied on to keep data safe.
 */
export function isSuperadmin(user: Pick<User, "role"> | null | undefined): boolean {
  return user?.role === ROLE_SUPERADMIN || user?.role === ROLE_LEGACY_ADMIN;
}

const MXN = new Intl.NumberFormat("es-MX", {
  style: "currency",
  currency: "MXN",
  maximumFractionDigits: 2,
});

export function formatMxn(amount: number | string): string {
  const value = typeof amount === "string" ? Number(amount) : amount;
  return MXN.format(Number.isFinite(value) ? value : 0);
}

const TOKENS = new Intl.NumberFormat("es-MX");

export function formatTokens(tokens: number): string {
  return TOKENS.format(tokens || 0);
}
