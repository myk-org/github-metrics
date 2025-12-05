import { createContext } from "react";

export type Theme = "dark" | "light" | "system";

export interface ThemeProviderState {
  readonly theme: Theme;
  readonly setTheme: (theme: Theme) => void;
}

export const ThemeProviderContext = createContext<ThemeProviderState | undefined>(undefined);
