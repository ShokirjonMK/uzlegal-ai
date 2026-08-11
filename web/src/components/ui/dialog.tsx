"use client";

import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";

/**
 * Modal oyna. Radix fokusni oyna ichida ushlab turadi, Esc bilan yopadi va
 * yopilganda fokusni chaqirgan tugmaga qaytaradi.
 */
export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export const DialogContent = React.forwardRef<
  React.ComponentRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & { title: string }
>(({ className, children, title, ...props }, ref) => (
  <DialogPrimitive.Portal>
    <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/45 backdrop-blur-[2px]" />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-1/2 top-1/2 z-50 w-[calc(100vw-32px)] max-w-[440px] -translate-x-1/2 -translate-y-1/2",
        "rounded-[var(--radius)] border border-border bg-card p-5 shadow-[var(--shadow-lift)]",
        "focus-visible:outline-none",
        className,
      )}
      {...props}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <DialogPrimitive.Title className="text-[16px] font-semibold m-0">
          {title}
        </DialogPrimitive.Title>
        <DialogPrimitive.Close
          aria-label="Yopish"
          className="text-muted-foreground hover:text-foreground cursor-pointer rounded-[var(--radius)] p-1 focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2"
        >
          <X className="size-4" />
        </DialogPrimitive.Close>
      </div>
      {children}
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
DialogContent.displayName = "DialogContent";

export function DialogDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <DialogPrimitive.Description
      className={cn("text-[14px] text-muted-foreground m-0 mb-3", className)}
      {...props}
    />
  );
}

export function DialogFooter({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("flex flex-wrap items-center gap-2 mt-4", className)} {...props} />
  );
}
