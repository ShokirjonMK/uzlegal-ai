"use client";

import * as React from "react";
import * as LabelPrimitive from "@radix-ui/react-label";
import { cn } from "@/lib/cn";

const field =
  "w-full rounded-[var(--radius)] border border-input bg-[color-mix(in_srgb,var(--bg-raised)_92%,transparent)] " +
  "px-3 py-2.5 text-[15px] text-foreground placeholder:text-faint " +
  "focus-visible:outline-2 focus-visible:outline-ring focus-visible:-outline-offset-1 focus-visible:border-ring " +
  "disabled:opacity-50 disabled:cursor-not-allowed";

export const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, ...props }, ref) => (
    <input ref={ref} className={cn(field, className)} {...props} />
  ),
);
Input.displayName = "Input";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.ComponentProps<"textarea">
>(({ className, ...props }, ref) => (
  <textarea ref={ref} className={cn(field, "resize-y", className)} {...props} />
));
Textarea.displayName = "Textarea";

export const Select = React.forwardRef<HTMLSelectElement, React.ComponentProps<"select">>(
  ({ className, ...props }, ref) => (
    <select ref={ref} className={cn(field, className)} {...props} />
  ),
);
Select.displayName = "Select";

export const Label = React.forwardRef<
  React.ComponentRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>
>(({ className, ...props }, ref) => (
  <LabelPrimitive.Root
    ref={ref}
    className={cn(
      "block text-[13px] font-medium text-muted-foreground mb-1.5",
      className,
    )}
    {...props}
  />
));
Label.displayName = "Label";
