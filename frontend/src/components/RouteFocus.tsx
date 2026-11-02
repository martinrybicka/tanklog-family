import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
export function RouteFocus() {
  const { pathname } = useLocation();
  const first = useRef(true);
  useEffect(() => {
    const shouldFocus = !first.current;
    first.current = false;
    const update = () => {
      const main = document.querySelector<HTMLElement>("main");
      const heading = main?.querySelector("h1");
      if (!main || !heading) return false;
      document.title = `${heading.textContent} · TankLog`;
      if (shouldFocus) {
        main.tabIndex = -1;
        main.focus({ preventScroll: true });
        window.scrollTo(0, 0);
      }
      return true;
    };
    if (update()) return;
    const observer = new MutationObserver(() => {
      if (update()) observer.disconnect();
    });
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [pathname]);
  return null;
}
