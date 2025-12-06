import { useEffect, useState } from "react";
import { ThemeProviderContext, type Theme } from "@/context/theme-context";

interface ThemeProviderProps {
  readonly children: React.ReactNode;
  readonly defaultTheme?: Theme;
  readonly storageKey?: string;
}

export function ThemeProvider({
  children,
  defaultTheme = "system",
  storageKey = "ui-theme",
}: ThemeProviderProps): React.ReactElement {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      const storedTheme = localStorage.getItem(storageKey);
      if (storedTheme === "light" || storedTheme === "dark" || storedTheme === "system") {
        return storedTheme;
      }
    } catch {
      // localStorage access failed or corrupted data
    }
    return defaultTheme;
  });

  useEffect(() => {
    const root = window.document.documentElement;

    const applyTheme = (resolvedTheme: "light" | "dark"): void => {
      root.classList.remove("light", "dark");
      root.classList.add(resolvedTheme);
    };

    if (theme === "system") {
      const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
      const resolvedTheme = mediaQuery.matches ? "dark" : "light";
      applyTheme(resolvedTheme);

      const handleChange = (event: MediaQueryListEvent): void => {
        applyTheme(event.matches ? "dark" : "light");
      };

      mediaQuery.addEventListener("change", handleChange);
      return () => {
        mediaQuery.removeEventListener("change", handleChange);
      };
    }

    applyTheme(theme);
    return undefined;
  }, [theme]);

  const value = {
    theme,
    setTheme: (newTheme: Theme) => {
      localStorage.setItem(storageKey, newTheme);
      setTheme(newTheme);
    },
  };

  return <ThemeProviderContext.Provider value={value}>{children}</ThemeProviderContext.Provider>;
}
