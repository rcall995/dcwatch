/**
 * Format a trade amount range into a human-readable string.
 * Examples: "$1K - $15K", "$100K - $250K", "$1M - $5M"
 */
export function formatAmount(low: number, high: number): string {
  const fmt = (n: number): string => {
    if (n >= 1_000_000) {
      const val = n / 1_000_000;
      return `$${val % 1 === 0 ? val.toFixed(0) : val.toFixed(1)}M`;
    }
    if (n >= 1_000) {
      const val = n / 1_000;
      return `$${val % 1 === 0 ? val.toFixed(0) : val.toFixed(1)}K`;
    }
    return `$${n.toLocaleString()}`;
  };

  if (low === high) {
    return fmt(low);
  }

  return `${fmt(low)} - ${fmt(high)}`;
}

/**
 * Format a return percentage with sign and color hint.
 * Returns an object with the formatted string and a color class name.
 */
export function formatReturn(pct: number): { text: string; colorClass: string } {
  const sign = pct >= 0 ? "+" : "";
  const text = `${sign}${pct.toFixed(1)}%`;
  const colorClass = pct >= 0 ? "text-green" : "text-red";

  return { text, colorClass };
}

/**
 * Format a date string (YYYY-MM-DD) into a readable format.
 * Example: "2025-01-15" -> "Jan 15, 2025"
 */
export function formatDate(dateStr: string): string {
  if (!dateStr) return "N/A";

  try {
    const date = new Date(dateStr + "T00:00:00");
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

/**
 * Get the theme color for a political party.
 */
export function partyColor(party: string): string {
  switch (party.toUpperCase()) {
    case "D":
    case "DEMOCRAT":
      return "var(--party-d)";
    case "R":
    case "REPUBLICAN":
      return "var(--party-r)";
    case "I":
    case "INDEPENDENT":
      return "var(--party-i)";
    default:
      return "var(--text-muted)";
  }
}

/**
 * Get the full party label from an abbreviation.
 */
export function partyLabel(party: string): string {
  switch (party.toUpperCase()) {
    case "D":
      return "Democrat";
    case "R":
      return "Republican";
    case "I":
      return "Independent";
    default:
      return party;
  }
}

/**
 * Get a human-readable label for a transaction type.
 */
export function txTypeLabel(type: string): string {
  switch (type) {
    case "purchase":
      return "Buy";
    case "sale_full":
      return "Sell (Full)";
    case "sale_partial":
      return "Sell (Partial)";
    case "exchange":
      return "Exchange";
    default:
      return type;
  }
}

/**
 * Get the color for a transaction type.
 * Purchases are green (bullish), sales are red (bearish).
 */
export function txTypeColor(type: string): string {
  switch (type) {
    case "purchase":
      return "var(--green)";
    case "sale_full":
    case "sale_partial":
      return "var(--red)";
    case "exchange":
      return "var(--accent)";
    default:
      return "var(--text-muted)";
  }
}
