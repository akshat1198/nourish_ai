// Client-side serving-size scaling for a recipe's display ingredient list.
//
// Quantities come in two shapes: seed/archanas carry a numeric `qty` + `unit`;
// themealdb carries `qty: null` with the raw measure in `unit` ("1 cup",
// "800g"). We scale both, and leave amount-less lines ("to taste", "For frying")
// exactly as written.

export interface ScaleLineInput {
  qty: number | null;
  unit: string | null;
}

export interface ScaledMeasure {
  text: string;
  scaled: boolean;
}

export function scaleFactor(base: number, target: number): number {
  return base > 0 ? target / base : 1;
}

const NAMED_FRACTIONS: [number, string][] = [
  [0.25, "¼"],
  [1 / 3, "⅓"],
  [0.5, "½"],
  [2 / 3, "⅔"],
  [0.75, "¾"],
];
const FRACTION_TOL = 0.02;

// Render a number the way a recipe would: whole numbers bare, the common
// kitchen fractions as glyphs (mixed like "1 ½"), everything else as a trimmed
// decimal.
export function formatQty(n: number): string {
  if (!Number.isFinite(n) || n < 0) return "";
  const whole = Math.floor(n);
  const frac = n - whole;

  if (frac < FRACTION_TOL) return String(whole);
  if (frac > 1 - FRACTION_TOL) return String(whole + 1);

  for (const [value, glyph] of NAMED_FRACTIONS) {
    if (Math.abs(frac - value) < FRACTION_TOL) {
      return whole > 0 ? `${whole} ${glyph}` : glyph;
    }
  }
  return String(Math.round(n * 100) / 100);
}

// Pull a leading amount off a themealdb-style measure so it can be scaled:
// "1 cup" -> {value: 1, rest: " cup"}, "800g" -> {value: 800, rest: "g"},
// "1 1/2 tbsp" -> {value: 1.5, rest: " tbsp"}. Amount not at the start
// ("Juice of 1") returns null so the line is left untouched.
function parseLeadingAmount(s: string): { value: number; rest: string } | null {
  const m = s.match(/^(\d+\s+\d+\/\d+|\d+\/\d+|\d+(?:\.\d+)?)/);
  if (!m) return null;

  const token = m[1];
  let value: number;
  if (token.includes("/")) {
    const parts = token.trim().split(/\s+/);
    if (parts.length === 2) {
      const [num, den] = parts[1].split("/").map(Number);
      value = Number(parts[0]) + num / den;
    } else {
      const [num, den] = token.split("/").map(Number);
      value = num / den;
    }
  } else {
    value = Number(token);
  }
  if (!Number.isFinite(value)) return null;
  return { value, rest: s.slice(m[0].length) };
}

export function scaleLine(line: ScaleLineInput, factor: number): ScaledMeasure {
  const unit = line.unit ?? "";

  if (line.qty != null) {
    return { text: `${formatQty(line.qty * factor)} ${unit}`.trim(), scaled: true };
  }

  const parsed = parseLeadingAmount(unit);
  if (parsed) {
    return { text: `${formatQty(parsed.value * factor)}${parsed.rest}`, scaled: true };
  }

  // No amount to scale (e.g. "to taste", "For frying") — leave it verbatim.
  return { text: unit, scaled: false };
}
