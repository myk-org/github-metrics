import React from "react";
import { useDateFormat } from "@/hooks/use-date-format";
import { useTheme } from "@/hooks/use-theme";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import type { DateFormat } from "@/context/date-format-context";
import type { Theme } from "@/context/theme-context";
import type { SettingsModalProps } from "@/types/settings";

const THEMES: ReadonlyArray<{ readonly value: Theme; readonly label: string }> = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
];

const DATE_FORMATS: ReadonlyArray<{
  readonly value: DateFormat;
  readonly label: string;
  readonly description: string;
}> = [
  { value: "MM/DD", label: "MM/DD", description: "US" },
  { value: "DD/MM", label: "DD/MM", description: "International" },
];

export function SettingsModal({ open, onOpenChange }: SettingsModalProps): React.ReactElement {
  const { theme, setTheme } = useTheme();
  const { dateFormat, setDateFormat } = useDateFormat();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Appearance Section */}
          <div className="space-y-3">
            <div>
              <h3 className="text-sm font-medium">Appearance</h3>
              <p className="text-muted-foreground text-xs">
                Customize the appearance of the application
              </p>
            </div>
            <div className="space-y-2">
              <Label>Theme</Label>
              <div className="flex gap-2" role="group" aria-label="Theme selection">
                {THEMES.map(({ value, label }) => (
                  <Button
                    key={value}
                    variant={theme === value ? "default" : "outline"}
                    size="sm"
                    onClick={() => {
                      setTheme(value);
                    }}
                    aria-pressed={theme === value}
                    className="flex-1"
                  >
                    {label}
                  </Button>
                ))}
              </div>
            </div>
          </div>

          {/* Date & Time Section */}
          <div className="space-y-3">
            <div>
              <h3 className="text-sm font-medium">Date & Time</h3>
              <p className="text-muted-foreground text-xs">
                Configure date and time display preferences
              </p>
            </div>
            <div className="space-y-2">
              <Label>Date Format</Label>
              <div className="flex gap-2" role="group" aria-label="Date format selection">
                {DATE_FORMATS.map(({ value, label, description }) => (
                  <Button
                    key={value}
                    variant={dateFormat === value ? "default" : "outline"}
                    size="sm"
                    onClick={() => {
                      setDateFormat(value);
                    }}
                    aria-pressed={dateFormat === value}
                    className="flex-1"
                  >
                    <span className="flex flex-col items-center gap-0.5">
                      <span className="text-xs font-medium">{label}</span>
                      <span className="text-[10px] opacity-70">{description}</span>
                    </span>
                  </Button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
