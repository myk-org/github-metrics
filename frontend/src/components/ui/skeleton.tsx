import { cn } from "@/lib/utils";

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  readonly delay?: number;
}

function Skeleton({ className, delay = 0, ...props }: SkeletonProps) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-muted", className)}
      style={{ animationDelay: `${delay.toString()}ms` }}
      {...props}
    />
  );
}

export { Skeleton };
