"use client";

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

/*
 * Fokus konturi loyiha naqshi bo'yicha: 2px `--accent` (`ring` tokeni orqali).
 * `outline-none` hech qayerda yozilmaydi — klaviatura bilan yuruvchi
 * foydalanuvchi uchun bu yagona ko'rsatkich.
 */
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius)] text-[15px] font-medium transition-colors cursor-pointer " +
    "focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2 " +
    "disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground border border-transparent hover:brightness-110",
        ghost: "bg-transparent text-muted-foreground border border-border-strong hover:bg-secondary hover:text-foreground",
        plain: "bg-transparent text-muted-foreground border border-transparent hover:bg-secondary hover:text-foreground",
        destructive: "bg-destructive text-destructive-foreground border border-transparent hover:brightness-110",
        soft: "bg-accent text-accent-foreground border border-transparent hover:brightness-105",
      },
      size: {
        default: "px-4 py-[9px]",
        sm: "px-3 py-1.5 text-[13.5px]",
        icon: "size-9 p-0",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** `true` bo'lsa uslub bolasiga o'tkaziladi (masalan `<Link>` ga). */
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { buttonVariants };
