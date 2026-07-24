/** Colorea deltas de precio (+/−) en texto del Research Chat. */

import { Fragment, createElement, isValidElement, type ReactNode } from "react";

/**
 * Captura cambios firmados típicos de Market Data:
 * +1.24%, -3.1%, −1,12%, +$0.50, -$1.2
 * Exige % o $ para no colorear fechas/rangos (2024-07-24, 51-52).
 * No pinta precios absolutos sin signo ($51.92).
 */
const SIGNED_PRICE_RE =
  /(?<![\d.,])([+\u2212\-])(\$?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)(%)|(?<![\d.,])([+\u2212\-])(\$\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)/g;

function signedClass(sign: string): string {
  return sign === "+" ? "text-emerald-400" : "text-red-400";
}

export function colorizeSignedPriceString(text: string): ReactNode {
  if (!text || !/[+\u2212\-]/.test(text)) return text;

  const nodes: ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  const re = new RegExp(SIGNED_PRICE_RE.source, "g");

  while ((match = re.exec(text)) !== null) {
    const full = match[0];
    // Branch A: ±amount%  |  Branch B: ±$amount
    const sign = match[1] ?? match[4] ?? "";
    const amount = match[2] ?? match[5] ?? "";
    const unit = match[3] ?? "";
    if (!sign || !amount) continue;
    if (match.index > last) {
      nodes.push(text.slice(last, match.index));
    }
    nodes.push(
      createElement(
        "span",
        {
          key: `signed-${match.index}`,
          className: `font-mono ${signedClass(sign)}`,
        },
        `${sign}${amount}${unit}`,
      ),
    );
    last = match.index + full.length;
  }

  if (nodes.length === 0) return text;
  if (last < text.length) nodes.push(text.slice(last));
  return createElement(Fragment, null, ...nodes);
}

export function colorizeSignedPrices(children: ReactNode): ReactNode {
  if (typeof children === "string") {
    return colorizeSignedPriceString(children);
  }
  if (typeof children === "number") {
    return colorizeSignedPriceString(String(children));
  }
  if (Array.isArray(children)) {
    return children.map((child, index) =>
      createElement(Fragment, { key: index }, colorizeSignedPrices(child)),
    );
  }
  if (isValidElement<{ children?: ReactNode }>(children)) {
    // Dejá links/buttons intactos; solo coloreá hojas de texto vía wrappers.
    return children;
  }
  return children;
}
