import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Tailwind sinflarini birlashtiradi va qarama-qarshilarini yechadi:
 * `cn("px-2", cond && "px-4")` → `px-4`. shadcn/ui komponentlari shunga tayanadi.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
