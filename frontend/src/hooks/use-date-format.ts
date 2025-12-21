import { useContext } from "react";
import {
  DateFormatProviderContext,
  type DateFormatProviderState,
} from "@/context/date-format-context";

export function useDateFormat(): DateFormatProviderState {
  const context = useContext(DateFormatProviderContext);
  if (context === undefined) {
    throw new Error("useDateFormat must be used within a DateFormatProvider");
  }
  return context;
}
