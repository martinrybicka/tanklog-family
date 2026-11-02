// Komponenty vycházejí z přístupu shadcn/ui (MIT); dialog používá Radix pro správu focusu.
import { useRef } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { cva, type VariantProps } from "class-variance-authority";
import { clsx, type ClassValue } from "clsx";
import { X, AlertCircle, LoaderCircle, Fuel } from "lucide-react";
import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
} from "react";
import { twMerge } from "tailwind-merge";

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));
const buttonVariants = cva("button", {
  variants: {
    variant: {
      default: "button-primary",
      secondary: "button-secondary",
      ghost: "button-ghost",
      danger: "button-danger",
    },
  },
  defaultVariants: { variant: "default" },
});
export function Button({
  className,
  variant,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants>) {
  return (
    <button className={cn(buttonVariants({ variant }), className)} {...props} />
  );
}
export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cn("input", props.className)} />;
}
export function Field({
  label,
  id,
  error,
  children,
  hint,
}: {
  label: string;
  id: string;
  error?: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {children}
      {error && (
        <p id={`${id}-error`} className="field-error">
          {error}
        </p>
      )}
      {hint && <p className="field-hint">{hint}</p>}
    </div>
  );
}
export function ErrorMessage({ children }: { children?: ReactNode }) {
  return children ? (
    <div role="alert" className="alert alert-error">
      <AlertCircle size={18} />
      <span>{children}</span>
    </div>
  ) : null;
}
export function Loading() {
  return (
    <div role="status" className="loading">
      <LoaderCircle className="spin" size={22} /> Načítání…
    </div>
  );
}
export function Logo() {
  return (
    <span className="brand">
      <span className="brand-mark">
        <Fuel size={23} strokeWidth={2.1} />
      </span>
      <span>
        Tank<span className="brand-light">Log</span>
        <small>AUTOMOBILOVÝ DENÍK</small>
      </span>
    </span>
  );
}
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description: string;
  children: ReactNode;
}) {
  const returnFocus = useRef<HTMLElement | null>(null);
  return (
    <Dialog.Root open={open} onOpenChange={(value) => !value && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="modal-overlay" />
        <Dialog.Content
          className="modal"
          onOpenAutoFocus={() => {
            returnFocus.current =
              document.activeElement instanceof HTMLElement &&
              document.activeElement !== document.body &&
              !document.activeElement.closest('[role="dialog"]')
                ? document.activeElement
                : null;
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            // Po uvolnění Radix focus trapu může spouštěč po úspěšné akci již chybět.
            requestAnimationFrame(() => {
              if (document.querySelector('[role="dialog"]')) return;
              const target = returnFocus.current?.isConnected
                ? returnFocus.current
                : document.getElementById("main-content");
              target?.focus({ preventScroll: true });
            });
          }}
        >
          <Dialog.Title className="modal-title">{title}</Dialog.Title>
          <Dialog.Description className="muted">
            {description}
          </Dialog.Description>
          <Dialog.Close asChild>
            <Button
              variant="ghost"
              className="modal-close"
              aria-label="Zavřít dialog"
            >
              <X size={20} />
            </Button>
          </Dialog.Close>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
