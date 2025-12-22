import { useState } from "react";
import { DateFormatProviderContext, type DateFormat } from "@/context/date-format-context";

interface DateFormatProviderProps {
  readonly children: React.ReactNode;
  readonly defaultFormat?: DateFormat;
  readonly storageKey?: string;
}

export function DateFormatProvider({
  children,
  defaultFormat = "MM/DD",
  storageKey = "github-metrics-date-format",
}: DateFormatProviderProps): React.ReactElement {
  const [dateFormat, setDateFormat] = useState<DateFormat>(() => {
    try {
      const storedFormat = localStorage.getItem(storageKey);
      if (storedFormat === "MM/DD" || storedFormat === "DD/MM") {
        return storedFormat;
      }
    } catch {
      // localStorage access failed or corrupted data
    }
    return defaultFormat;
  });

  const value = {
    dateFormat,
    setDateFormat: (newFormat: DateFormat) => {
      try {
        localStorage.setItem(storageKey, newFormat);
      } catch {
        // localStorage write failed, continue with state update
      }
      setDateFormat(newFormat);
    },
  };

  return (
    <DateFormatProviderContext.Provider value={value}>
      {children}
    </DateFormatProviderContext.Provider>
  );
}
