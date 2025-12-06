import { useContext } from "react";
import { FilterContext, type FilterContextType } from "@/contexts/filter-context-definition";

export function useFilters(): FilterContextType {
  const context = useContext(FilterContext);
  if (!context) {
    throw new Error("useFilters must be used within a FilterProvider");
  }
  return context;
}
