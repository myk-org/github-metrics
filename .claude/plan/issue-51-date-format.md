# Issue #51: Date Format Selection (DD/MM vs MM/DD)

## Summary
Add user preference for date format display (DD/MM or MM/DD) with a settings modal accessible from the header.

## Files to Create (5)

| File | Purpose |
|------|---------|
| `frontend/src/context/date-format-context.ts` | Context type definitions |
| `frontend/src/components/date-format-provider.tsx` | Provider with localStorage persistence |
| `frontend/src/hooks/use-date-format.ts` | Hook to consume context |
| `frontend/src/components/settings/settings-modal.tsx` | Settings modal with date format selector |
| `frontend/src/components/settings/settings-trigger.tsx` | Header button to open settings |

## Files to Modify (8)

| File | Changes |
|------|---------|
| `frontend/src/utils/time-format.ts` | Add `formatDate()` and `formatDateTime()` with format parameter |
| `frontend/src/main.tsx` | Wrap app with `DateFormatProvider` |
| `frontend/src/components/layout/layout.tsx` | Add settings trigger button in header |
| `frontend/src/pages/overview.tsx` | Use new date formatting with hook |
| `frontend/src/pages/team-dynamics.tsx` | Use new date formatting with hook |
| `frontend/src/pages/trends.tsx` | Use new date formatting with hook |
| `frontend/src/components/user-prs/user-prs-modal.tsx` | Remove local formatDate, use centralized one |
| `frontend/src/components/pr-story/pr-story-timeline.tsx` | Use new date formatting |

## Implementation Order

### Phase 1: Core Infrastructure
1. Create `date-format-context.ts` - Define `DateFormat` type and context
2. Create `date-format-provider.tsx` - Provider with localStorage (key: `github-metrics-date-format`)
3. Create `use-date-format.ts` - Hook following `use-theme.ts` pattern

### Phase 2: Utility Functions
4. Update `time-format.ts`:
   - Add `formatDate(timestamp, dateFormat)` - date only
   - Add `formatDateTime(timestamp, dateFormat)` - date + time
   - Use `en-GB` locale for DD/MM, `en-US` for MM/DD

### Phase 3: Settings UI
5. Create `settings-modal.tsx`:
   - Use shadcn Dialog components
   - Include date format selector (Radio group or Select)
   - Include theme selector (move from header toggle)
   - Clean, organized settings layout

6. Create `settings-trigger.tsx`:
   - Settings icon button (Settings from lucide-react)
   - Opens settings modal

### Phase 4: Wire Up
7. Update `main.tsx` - Add DateFormatProvider
8. Update `layout.tsx` - Replace/add settings trigger in header

### Phase 5: Update Consumers
9. Update all date formatting locations to use hook + new utilities

## Key Patterns to Follow

**Context Pattern** (from `theme-context.ts`):
```typescript
export type DateFormat = "MM/DD" | "DD/MM";
export interface DateFormatProviderState {
  readonly dateFormat: DateFormat;
  readonly setDateFormat: (format: DateFormat) => void;
}
```

**Provider Pattern** (from `theme-provider.tsx`):
- Initialize from localStorage with try/catch
- Default to "MM/DD" (US format)
- Persist to localStorage on change

**Modal Pattern** (from existing modals):
- Use Dialog, DialogContent, DialogHeader, DialogTitle
- Controlled with open/onOpenChange props

## Date Format Logic
```typescript
const locale = dateFormat === "DD/MM" ? "en-GB" : "en-US";
// en-GB: "1 Jan 2024" (day first)
// en-US: "Jan 1, 2024" (month first)
```
