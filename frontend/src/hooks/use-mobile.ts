import * as React from "react";

const MOBILE_BREAKPOINT = 768;
const RESIZE_DEBOUNCE_MS = 150;

function debounce<T extends (...args: unknown[]) => void>(
  func: T,
  wait: number
): T & { cancel: () => void } {
  let timeout: ReturnType<typeof setTimeout> | null = null;

  const debounced = ((...args: unknown[]) => {
    if (timeout) {
      clearTimeout(timeout);
    }
    timeout = setTimeout(() => {
      func(...args);
    }, wait);
  }) as T & { cancel: () => void };

  debounced.cancel = () => {
    if (timeout) {
      clearTimeout(timeout);
      timeout = null;
    }
  };

  return debounced;
}

export function useIsMobile() {
  const [isMobile, setIsMobile] = React.useState<boolean | undefined>(undefined);

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${(MOBILE_BREAKPOINT - 1).toString()}px)`);
    const onChange = debounce(() => {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    }, RESIZE_DEBOUNCE_MS);

    mql.addEventListener("change", onChange);
    setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);

    return () => {
      mql.removeEventListener("change", onChange);
      onChange.cancel();
    };
  }, []);

  return !!isMobile;
}
