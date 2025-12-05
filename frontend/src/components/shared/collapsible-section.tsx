import { type ReactNode } from "react";
import { CollapsibleSection as UICollapsibleSection } from "@/components/ui/collapsible-section";

interface CollapsibleSectionProps {
  readonly title: string;
  readonly children: ReactNode;
  readonly defaultOpen?: boolean;
  readonly isExpanded?: boolean;
  readonly onToggle?: () => void;
  readonly actions?: ReactNode;
  readonly storageKey?: string;
}

export function CollapsibleSection({
  title,
  children,
  defaultOpen = true,
  isExpanded,
  onToggle,
  actions,
  storageKey,
}: CollapsibleSectionProps): React.ReactElement {
  return (
    <UICollapsibleSection
      title={title}
      defaultExpanded={defaultOpen}
      {...(isExpanded !== undefined && { isExpanded })}
      {...(onToggle !== undefined && { onToggle })}
      {...(actions !== undefined && { actions })}
      {...(storageKey !== undefined && { storageKey })}
    >
      {children}
    </UICollapsibleSection>
  );
}
