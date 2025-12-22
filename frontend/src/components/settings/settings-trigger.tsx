import { useState } from "react";
import { Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SettingsModal } from "./settings-modal";

export function SettingsTrigger(): React.ReactElement {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => {
          setOpen(true);
        }}
        aria-label="Open settings"
      >
        <Settings className="h-[1.2rem] w-[1.2rem]" />
      </Button>
      <SettingsModal open={open} onOpenChange={setOpen} />
    </>
  );
}
