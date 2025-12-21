import { createContext } from "react";

export type DateFormat = "MM/DD" | "DD/MM";

export interface DateFormatProviderState {
  readonly dateFormat: DateFormat;
  readonly setDateFormat: (format: DateFormat) => void;
}

export const DateFormatProviderContext = createContext<DateFormatProviderState | undefined>(
  undefined
);
