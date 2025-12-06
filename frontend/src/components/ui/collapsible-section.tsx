import { useState, useEffect, type ReactNode } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface CollapsibleSectionProps {
  readonly title: string;
  readonly children: ReactNode;
  readonly defaultExpanded?: boolean;
  readonly isExpanded?: boolean;
  readonly onToggle?: () => void;
  readonly actions?: ReactNode;
  readonly storageKey?: string;
}

export function CollapsibleSection({
  title,
  children,
  defaultExpanded = true,
  isExpanded: controlledIsExpanded,
  onToggle,
  actions,
  storageKey,
}: CollapsibleSectionProps): React.ReactElement {
  // Generate storage key from title if not provided
  const localStorageKey =
    storageKey ?? `section-${title.toLowerCase().replace(/\s+/g, "-")}-collapsed`;

  // Load initial state from localStorage if available
  const getInitialState = (): boolean => {
    if (typeof window === "undefined") {
      return defaultExpanded;
    }
    const stored = localStorage.getItem(localStorageKey);
    if (stored === null) {
      return defaultExpanded;
    }
    return stored === "true";
  };

  // Support both controlled and uncontrolled modes
  const [uncontrolledIsExpanded, setUncontrolledIsExpanded] = useState(getInitialState);

  // Use controlled state if provided, otherwise use uncontrolled state
  const isExpanded =
    controlledIsExpanded !== undefined ? controlledIsExpanded : uncontrolledIsExpanded;

  // Save to localStorage when state changes (uncontrolled mode only)
  useEffect(() => {
    if (controlledIsExpanded === undefined && typeof window !== "undefined") {
      localStorage.setItem(localStorageKey, String(uncontrolledIsExpanded));
    }
  }, [uncontrolledIsExpanded, controlledIsExpanded, localStorageKey]);

  const handleToggle = (): void => {
    if (onToggle) {
      // Controlled mode - call parent's toggle handler
      onToggle();
    } else {
      // Uncontrolled mode - manage state internally
      setUncontrolledIsExpanded(!uncontrolledIsExpanded);
    }
  };

  return (
    <Card className="overflow-visible">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle>{title}</CardTitle>
        <div className="flex items-center gap-2">
          {actions}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleToggle}
            aria-expanded={isExpanded}
            aria-label={isExpanded ? "Collapse section" : "Expand section"}
          >
            {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
        </div>
      </CardHeader>
      {isExpanded && <CardContent className="pb-6 overflow-visible">{children}</CardContent>}
    </Card>
  );
}
