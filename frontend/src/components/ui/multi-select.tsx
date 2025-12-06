import { useState, useRef, useEffect, useMemo, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { ChevronDown } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";

interface MultiSelectProps {
  readonly id?: string;
  readonly placeholder?: string;
  readonly value: readonly string[];
  readonly onChange: (value: readonly string[]) => void;
  readonly suggestions?: readonly string[];
  readonly className?: string;
}

export function MultiSelect({
  id,
  placeholder = "Select items...",
  value,
  onChange,
  suggestions = [],
  className,
}: MultiSelectProps): React.ReactElement {
  const [inputValue, setInputValue] = useState("");
  const [showDropdown, setShowDropdown] = useState(false);
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0, width: 0 });
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Filter suggestions based on search input
  const filteredSuggestions = useMemo(() => {
    if (!inputValue.trim()) {
      return suggestions;
    }
    return suggestions.filter((suggestion) =>
      suggestion.toLowerCase().includes(inputValue.toLowerCase())
    );
  }, [suggestions, inputValue]);

  // Check if all filtered suggestions are selected
  const allSelected = useMemo(() => {
    return (
      filteredSuggestions.length > 0 &&
      filteredSuggestions.every((suggestion) => value.includes(suggestion))
    );
  }, [filteredSuggestions, value]);

  // Check if some (but not all) filtered suggestions are selected
  const someSelected = useMemo(() => {
    return filteredSuggestions.some((suggestion) => value.includes(suggestion)) && !allSelected;
  }, [filteredSuggestions, value, allSelected]);

  // Update dropdown position when it opens
  useEffect(() => {
    if (!showDropdown || !containerRef.current) {
      return;
    }

    const updatePosition = (): void => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      setDropdownPosition({
        top: rect.bottom + window.scrollY,
        left: rect.left + window.scrollX,
        width: rect.width,
      });
    };

    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);

    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [showDropdown]);

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent): void {
      const target = event.target as Node;
      if (
        containerRef.current &&
        !containerRef.current.contains(target) &&
        dropdownRef.current &&
        !dropdownRef.current.contains(target)
      ) {
        setShowDropdown(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const toggleValue = (toggleItem: string): void => {
    if (value.includes(toggleItem)) {
      onChange(value.filter((v) => v !== toggleItem));
    } else {
      onChange([...value, toggleItem]);
    }
  };

  const handleSelectAll = (): void => {
    if (allSelected) {
      // Deselect all filtered suggestions
      const newValue = value.filter((v) => !filteredSuggestions.includes(v));
      onChange(newValue);
    } else {
      // Select all filtered suggestions
      const newValue = [...new Set([...value, ...filteredSuggestions])];
      onChange(newValue);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === "Escape") {
      setShowDropdown(false);
      setInputValue("");
    }
  };

  const handleToggleDropdown = (): void => {
    const newState = !showDropdown;
    setShowDropdown(newState);
    if (newState) {
      // Focus search input when dropdown opens
      setTimeout(() => {
        inputRef.current?.focus();
      }, 0);
    } else {
      // Clear search when dropdown closes
      setInputValue("");
    }
  };

  const handleTriggerKeyDown = (e: KeyboardEvent<HTMLDivElement>): void => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handleToggleDropdown();
    }
  };

  return (
    <TooltipProvider>
      <div ref={containerRef} className="relative w-full" id={id}>
        {/* Selected items display with count and tooltip */}
        <Tooltip>
          <TooltipTrigger asChild>
            <div
              role="button"
              tabIndex={0}
              aria-haspopup="listbox"
              aria-expanded={showDropdown}
              className={`flex h-9 items-center justify-between px-3 border border-input rounded-md bg-background cursor-pointer text-sm ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 ${className ?? ""}`}
              onClick={handleToggleDropdown}
              onKeyDown={handleTriggerKeyDown}
            >
              {value.length === 0 ? (
                <span className="text-muted-foreground">{placeholder}</span>
              ) : (
                <span className="text-sm">{value.length} selected</span>
              )}
              <ChevronDown
                className={`h-4 w-4 text-muted-foreground transition-transform ${showDropdown ? "transform rotate-180" : ""}`}
              />
            </div>
          </TooltipTrigger>
          {value.length > 0 && (
            <TooltipContent side="bottom" className="max-w-xs">
              <div className="text-sm space-y-1">
                {value.map((item) => (
                  <div key={item}>{item}</div>
                ))}
              </div>
            </TooltipContent>
          )}
        </Tooltip>

        {/* Dropdown with checkboxes - rendered in portal */}
        {showDropdown &&
          createPortal(
            <div
              ref={dropdownRef}
              className="fixed z-[9999] mt-1 rounded-md border border-input bg-popover text-popover-foreground shadow-lg"
              style={{
                top: `${String(dropdownPosition.top)}px`,
                left: `${String(dropdownPosition.left)}px`,
                width: `${String(dropdownPosition.width)}px`,
                minWidth: "200px",
              }}
            >
              {/* Search input */}
              <div className="sticky top-0 bg-popover p-2 border-b border-border z-10">
                <Input
                  ref={inputRef}
                  type="text"
                  value={inputValue}
                  onChange={(e) => {
                    setInputValue(e.target.value);
                  }}
                  onKeyDown={handleKeyDown}
                  placeholder="Search..."
                  className="h-8"
                />
              </div>

              {filteredSuggestions.length > 0 && (
                <>
                  {/* Select All option */}
                  <div
                    role="option"
                    tabIndex={0}
                    aria-selected={allSelected}
                    className="flex items-center gap-2 px-3 py-2 hover:bg-accent cursor-pointer sticky top-[52px] bg-popover border-b border-border z-10"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleSelectAll();
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        e.stopPropagation();
                        handleSelectAll();
                      }
                    }}
                  >
                    <Checkbox
                      checked={allSelected}
                      onCheckedChange={handleSelectAll}
                      aria-label="Select all"
                      className={someSelected ? "data-[state=checked]:bg-primary/50" : ""}
                    />
                    <span className="text-sm font-medium">
                      {allSelected ? "Deselect All" : "Select All"}
                      {filteredSuggestions.length !== suggestions.length &&
                        ` (${String(filteredSuggestions.length)})`}
                    </span>
                  </div>

                  <Separator />

                  {/* Individual options */}
                  <div className="p-1 max-h-60 overflow-auto">
                    {filteredSuggestions.map((suggestion) => {
                      const isSelected = value.includes(suggestion);
                      return (
                        <div
                          key={suggestion}
                          role="option"
                          tabIndex={0}
                          aria-selected={isSelected}
                          className="flex items-center gap-2 px-2 py-2 hover:bg-accent rounded-sm cursor-pointer"
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleValue(suggestion);
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              e.stopPropagation();
                              toggleValue(suggestion);
                            }
                          }}
                        >
                          <Checkbox
                            checked={isSelected}
                            onCheckedChange={() => {
                              toggleValue(suggestion);
                            }}
                            aria-label={`Select ${suggestion}`}
                          />
                          <span className="text-sm flex-1">{suggestion}</span>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}

              {/* Empty state when no suggestions match search */}
              {filteredSuggestions.length === 0 && (
                <div className="p-4">
                  <p className="text-sm text-muted-foreground text-center">
                    {inputValue ? `No results for "${inputValue}"` : "No options available"}
                  </p>
                </div>
              )}
            </div>,
            document.body
          )}
      </div>
    </TooltipProvider>
  );
}
