import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind classnames conditionally (shadcn/ui convention). */
export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
