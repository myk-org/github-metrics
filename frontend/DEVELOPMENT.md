# Frontend Development Guide

## Overview

The GitHub Metrics frontend is a modern React application built with:

- **React 19** - Latest React features including hooks and concurrent rendering
- **TypeScript 5.9** - Strict type checking for reliability
- **Vite 7** - Fast build tool with hot module replacement
- **Bun** - Fast JavaScript runtime and package manager
- **shadcn/ui** - High-quality, accessible component library built on Radix UI
- **Tailwind CSS v4** - Utility-first CSS framework
- **React Query** - Server state management with caching
- **React Router v7** - Client-side routing

## Project Structure

```text
frontend/
├── src/
│   ├── components/
│   │   ├── ui/              # shadcn components (DO NOT MODIFY)
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── table.tsx
│   │   │   ├── dialog.tsx
│   │   │   ├── multi-select.tsx
│   │   │   ├── pagination-controls.tsx
│   │   │   ├── download-buttons.tsx
│   │   │   └── ... (25 total components)
│   │   ├── layout/          # App layout components (header, sidebar)
│   │   ├── dashboard/       # Dashboard-specific components
│   │   ├── shared/          # Reusable composed components
│   │   ├── user-prs/        # User PRs modal component
│   │   └── pr-story/        # PR Story timeline components
│   ├── hooks/
│   │   ├── use-api.ts       # React Query hooks for API calls
│   │   ├── use-filters.ts   # Access global filter context
│   │   ├── use-theme.ts     # Dark/light theme management
│   │   ├── use-mobile.ts    # Mobile breakpoint detection
│   │   └── use-sidebar.ts   # Sidebar state management
│   ├── pages/               # Route page components
│   │   ├── overview.tsx
│   │   ├── webhooks.tsx
│   │   ├── repositories.tsx
│   │   ├── contributors.tsx
│   │   ├── pull-requests.tsx
│   │   ├── turnaround.tsx
│   │   ├── trends.tsx
│   │   └── team-dynamics.tsx
│   ├── types/               # TypeScript type definitions
│   │   ├── api.ts           # Common API types (TimeRange, PaginatedResponse)
│   │   ├── metrics.ts       # Metrics data types
│   │   ├── webhooks.ts      # Webhook event types
│   │   ├── contributors.ts  # Contributor metrics types
│   │   ├── repositories.ts  # Repository metrics types
│   │   ├── user-prs.ts      # User PRs types
│   │   ├── team-dynamics.ts # Team dynamics types
│   │   ├── pr-story.ts      # PR Story timeline types
│   │   └── index.ts         # Re-exports
│   ├── contexts/            # React Context providers
│   │   ├── filter-context-definition.tsx  # Filter context types
│   │   └── filter-context.tsx            # Filter state provider
│   ├── lib/
│   │   └── utils.ts         # Utility functions (cn, formatters)
│   ├── App.tsx              # Root component
│   ├── main.tsx             # Application entry point
│   └── index.css            # Global styles + Tailwind configuration
├── public/                  # Static assets
├── package.json             # Dependencies and scripts
├── vite.config.ts           # Vite configuration
├── tsconfig.json            # TypeScript root config
├── tsconfig.app.json        # TypeScript app config
├── components.json          # shadcn configuration
└── eslint.config.js         # ESLint configuration
```

## Getting Started

### Prerequisites

- **Bun** - Install from [bun.sh](https://bun.sh)
- **Backend server** - Must be running on port 8765

### Installation

```bash
cd frontend
bun install
```

### Development

```bash
# Start frontend dev server (port 3003)
bun run dev

# Or use the project script
./dev/run-frontend.sh

# Start both frontend and backend together
./dev/run-all.sh
```

### Build and Preview

```bash
# Production build
bun run build

# Preview production build
bun run preview

# Lint code
bun run lint
```

### Container Testing

Test the full stack in a containerized environment:

```bash
# Build and run frontend + backend in containers
./dev/dev-container.sh

# This script:
# - Builds Docker images for backend and frontend
# - Starts PostgreSQL, backend, and frontend containers
# - Exposes frontend on port 3003
# - Includes hot reload for development
```

Use this for testing production-like deployments before committing.

### Development URLs

- **Frontend:** `http://localhost:3003`
- **Backend:** `http://localhost:8765`
- **API Proxy:** `/api/*` forwards to backend automatically

## shadcn/ui Components

### CRITICAL RULE: Use shadcn for ALL UI Elements

### Never create custom HTML elements for UI components

```tsx
// ❌ WRONG - Custom HTML button
<button className="px-4 py-2 bg-blue-500 text-white rounded">Click me</button>;

// ✅ CORRECT - shadcn Button component
import { Button } from "@/components/ui/button";

<Button variant="default" size="default">
  Click me
</Button>;
```

### Installed Components

The following shadcn components are available in `src/components/ui/`:

**Layout & Structure:**

- `card` - Content containers with header/footer
- `separator` - Visual dividers
- `tabs` - Tabbed interfaces
- `collapsible` - Expandable/collapsible sections
- `sidebar` - Application sidebar navigation
- `sheet` - Slide-out panels

**Forms & Inputs:**

- `button` - Buttons with variants (default, destructive, outline, ghost)
- `input` - Text input fields
- `label` - Form field labels
- `select` - Dropdown selects
- `multi-select` - Multi-select dropdown with search
- `calendar` - Date picker calendar
- `command` - Command menu/palette

**Feedback & Display:**

- `dialog` - Modal dialogs
- `popover` - Popup overlays
- `tooltip` - Hover tooltips
- `badge` - Status badges
- `skeleton` - Loading placeholders

**Data Display:**

- `table` - Data tables
- `pagination-controls` - Table pagination (custom)
- `download-buttons` - CSV/JSON download buttons (custom)

**Interactive:**

- `dropdown-menu` - Context menus
- `collapsible-section` - Collapsible content sections (custom)

### Installing New Components

```bash
# Install a new shadcn component
bunx shadcn@latest add <component-name>

# Examples
bunx shadcn@latest add alert
bunx shadcn@latest add checkbox
bunx shadcn@latest add slider
```

**Available components:** See [ui.shadcn.com](https://ui.shadcn.com/docs/components)

### Component Composition Pattern

Compose shadcn primitives into feature components:

```tsx
// src/components/dashboard/metric-card.tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

interface MetricCardProps {
  readonly title: string;
  readonly value: number | string;
  readonly trend?: "up" | "down" | "neutral";
  readonly isLoading?: boolean;
}

export function MetricCard({ title, value, trend, isLoading }: MetricCardProps): JSX.Element {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-4 w-24" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-8 w-16" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <span className="text-2xl font-bold">{value}</span>
          {trend && (
            <Badge variant={trend === "up" ? "default" : "destructive"}>
              {trend === "up" ? "↑" : "↓"}
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
```

### Custom vs. shadcn Components

**Custom components** (in `ui/` with `-` in filename):

- `multi-select.tsx` - Enhanced multi-select with search
- `pagination-controls.tsx` - Pagination with page size selector
- `download-buttons.tsx` - Data export buttons
- `collapsible-section.tsx` - Section with collapse toggle
- `scroll-area.tsx` - Scrollable area with custom scrollbars
- `checkbox.tsx` - Checkbox input component

**When to create custom components:**

- Composing multiple shadcn primitives into a reusable pattern
- Adding domain-specific logic to UI components
- Creating project-specific variations

**Always extend shadcn, never replace:**

```tsx
// ✅ CORRECT - Extend shadcn with custom logic
import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";

export function DownloadButton({ data, filename }: Props): JSX.Element {
  const handleDownload = () => {
    // Custom download logic
  };

  return (
    <Button onClick={handleDownload} variant="outline" size="sm">
      <Download className="mr-2 h-4 w-4" />
      Download CSV
    </Button>
  );
}
```

## Global Filter Context

### Filter State Management

The application uses React Context to manage global filter state across all pages. Filters are applied consistently to all API calls and persist during navigation.

**Filter Context Location:** `src/contexts/`

- `filter-context-definition.tsx` - Type definitions for filter state
- `filter-context.tsx` - Provider implementation with state management

### Filter State

```typescript
interface FilterState {
  readonly timeRange: TimeRange;
  readonly quickRange: string;
  readonly repositories: readonly string[];
  readonly users: readonly string[];
  readonly excludeUsers: readonly string[];
}
```

### Using Filters in Components

**Access filters with the `useFilters` hook:**

```tsx
import { useFilters } from "@/hooks/use-filters";

export function MyComponent(): JSX.Element {
  const { filters, setTimeRange, setRepositories, setUsers } = useFilters();

  // Filters automatically applied to API calls
  const { data } = useSummary(filters.timeRange, {
    repositories: filters.repositories,
    users: filters.users,
  });

  return (
    <div>
      <p>Viewing data for {filters.repositories.length} repositories</p>
      <p>Time range: {filters.quickRange}</p>
    </div>
  );
}
```

### Filter Functions

```typescript
// Update time range
setTimeRange(
  { start_time: "2024-01-01T00:00:00Z", end_time: "2024-12-31T23:59:59Z" },
  "Custom Range"
);

// Update repository filter
setRepositories(["repo1", "repo2"]);

// Update user filter
setUsers(["user1", "user2"]);

// Update excluded users
setExcludeUsers(["bot-user"]);

// Reset all filters to defaults
resetFilters();
```

### Filter Persistence

Filters persist during navigation between pages. When a user switches from Overview to Contributors, the same repository and time range filters apply automatically.

**Example flow:**

1. User selects "Last 30 days" on Overview page
2. User navigates to Contributors page
3. Contributors page automatically shows data for "Last 30 days"
4. User changes repository filter to ["repo1"]
5. Both Overview and Contributors now show data for "repo1" only

## Data Fetching with React Query

### API Hooks Location

All API hooks are centralized in `src/hooks/use-api.ts`.

### Available Hooks

```typescript
// Metrics summary
useSummary(timeRange?, filters?)

// Webhook events
useWebhooks(params?)

// Repository metrics
useRepositories(timeRange?, filters?)

// Contributor metrics (paginated)
useContributors(timeRange?, filters?, page, pageSize)

// Trends data
useTrends(timeRange?, bucket)

// Turnaround metrics
useTurnaround(timeRange?, filters?)

// User PRs (paginated)
useUserPRs(params?)

// Team dynamics (paginated)
useTeamDynamics(timeRange?, filters?, page, pageSize)

// PR Story timeline
usePRStory(params?)
```

### Common Patterns

#### Basic Usage

```tsx
import { useSummary } from "@/hooks/use-api";

export function SummaryCards(): JSX.Element {
  const { data, isLoading, error } = useSummary();

  if (isLoading) {
    return <Skeleton />;
  }

  if (error) {
    return <div>Error: {error.message}</div>;
  }

  return (
    <div className="grid gap-4 md:grid-cols-3">
      <MetricCard title="Total PRs" value={data.total_prs} />
      <MetricCard title="Open PRs" value={data.open_prs} />
      <MetricCard title="Merged PRs" value={data.merged_prs} />
    </div>
  );
}
```

**With Time Range and Filters:**

```tsx
import { useSummary } from "@/hooks/use-api";
import type { TimeRange } from "@/types/api";

interface Props {
  readonly timeRange?: TimeRange;
  readonly repositories?: readonly string[];
  readonly users?: readonly string[];
}

export function FilteredSummary({ timeRange, repositories, users }: Props): JSX.Element {
  const { data, isLoading } = useSummary(timeRange, { repositories, users });

  // ...
}
```

**Pagination:**

```tsx
import { useContributors } from "@/hooks/use-api";
import { useState } from "react";

export function ContributorsTable(): JSX.Element {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const { data, isLoading } = useContributors(undefined, {}, page, pageSize);

  return (
    <>
      <Table>{/* Table content */}</Table>
      <PaginationControls
        currentPage={page}
        totalPages={data?.pagination.total_pages ?? 1}
        onPageChange={setPage}
      />
    </>
  );
}
```

### Adding New API Endpoints

**Step 1: Define Types** (`src/types/your-feature.ts`)

```typescript
// src/types/user-activity.ts
export interface UserActivity {
  readonly username: string;
  readonly total_commits: number;
  readonly total_reviews: number;
  readonly last_active: string;
}

export interface UserActivityResponse {
  readonly activities: readonly UserActivity[];
  readonly total: number;
}
```

**Step 2: Add Query Key** (`src/hooks/use-api.ts`)

```typescript
export const queryKeys = {
  // ... existing keys
  userActivity: (timeRange?: TimeRange, username?: string) =>
    ["metrics", "user-activity", timeRange, username] as const,
};
```

**Step 3: Create Hook** (`src/hooks/use-api.ts`)

```typescript
export function useUserActivity(timeRange?: TimeRange, username?: string) {
  return useQuery<UserActivityResponse>({
    queryKey: queryKeys.userActivity(timeRange, username),
    queryFn: () =>
      fetchApi<UserActivityResponse>("/user-activity", {
        ...timeRange,
        username,
      }),
  });
}
```

#### Step 4: Use in Component

```tsx
import { useUserActivity } from "@/hooks/use-api";

export function UserActivityPage(): JSX.Element {
  const { data, isLoading } = useUserActivity();

  // Use data
}
```

## Type Safety

### Strict TypeScript Configuration

The project uses **strict TypeScript** with additional safety rules:

```json
{
  "strict": true,
  "noImplicitAny": true,
  "strictNullChecks": true,
  "noUnusedLocals": true,
  "noUnusedParameters": true,
  "noImplicitReturns": true,
  "exactOptionalPropertyTypes": true
}
```

### MANDATORY Type Rules

**❌ NO `any` types**

```typescript
// ❌ WRONG
function processData(data: any) {}

// ✅ CORRECT - Use proper types
function processData(data: MetricsSummary) {}

// ✅ CORRECT - Use unknown if truly dynamic
function processData(data: unknown) {
  if (isMetricsSummary(data)) {
    // Type guard
  }
}
```

### NO type assertions without justification

```typescript
// ❌ WRONG - Unsafe assertion
const user = response as User;

// ✅ CORRECT - Validate first
if (isValidUser(response)) {
  const user: User = response;
}
```

### All props must be typed

```typescript
// ❌ WRONG - No type
export function Component(props) {}

// ✅ CORRECT - Typed props
interface ComponentProps {
  readonly title: string;
  readonly count: number;
  readonly onSelect?: (id: string) => void;
}

export function Component({ title, count, onSelect }: ComponentProps): JSX.Element {
  // ...
}
```

### All API responses must have interfaces

```typescript
// src/types/metrics.ts
export interface MetricsSummary {
  readonly total_prs: number;
  readonly open_prs: number;
  readonly merged_prs: number;
  readonly avg_time_to_merge_hours: number | null;
}
```

**✅ Use `readonly` for props and API responses**

```typescript
// ✅ Props should be readonly
interface Props {
  readonly items: readonly string[]; // Immutable array
  readonly config: Readonly<Config>; // Immutable object
}

// ✅ API responses are immutable
export interface PaginatedResponse<T> {
  readonly data: readonly T[];
  readonly pagination: Readonly<PaginationMeta>;
}
```

### Type Definitions Location

**Organize types by domain:**

```text
src/types/
├── api.ts               # Common: TimeRange, PaginatedResponse
├── metrics.ts           # Metrics data structures
├── webhooks.ts          # Webhook events
├── contributors.ts      # Contributor metrics
├── repositories.ts      # Repository metrics
├── user-prs.ts          # User PR data
├── team-dynamics.ts     # Team dynamics data
├── pr-story.ts          # PR Story timeline event types
└── index.ts             # Re-exports
```

**Import pattern:**

```typescript
// ✅ Import from specific type file
import type { MetricsSummary } from "@/types/metrics";
import type { TimeRange } from "@/types/api";

// ✅ Or from index
import type { MetricsSummary, TimeRange } from "@/types";
```

## Styling with Tailwind CSS v4

### Tailwind Import Syntax

Tailwind CSS v4 uses modern CSS imports:

```css
/* src/index.css */
@import "tailwindcss";
```

### Theme Variables

All colors use CSS custom properties defined in `src/index.css`:

**Light Theme:**

```css
:root {
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
  --primary: 222.2 47.4% 11.2%;
  --primary-foreground: 210 40% 98%;
  --secondary: 210 40% 96.1%;
  --destructive: 0 84.2% 60.2%;
  --border: 214.3 31.8% 91.4%;
  --radius: 0.5rem;
  /* ... more variables */
}
```

**Dark Theme:**

```css
.dark {
  --background: 222.2 84% 4.9%;
  --foreground: 210 40% 98%;
  --primary: 210 40% 98%;
  --primary-foreground: 222.2 47.4% 11.2%;
  /* ... overrides */
}
```

### Using Theme Colors

```tsx
// Use Tailwind color utilities (automatically use CSS variables)
<div className="bg-background text-foreground border-border">
  <h1 className="text-primary">Title</h1>
  <p className="text-muted-foreground">Description</p>
  <Button variant="destructive">Delete</Button>
</div>
```

### Custom Utility Classes

Add custom utilities in `src/index.css`:

```css
@layer utilities {
  .scrollbar-hide {
    -ms-overflow-style: none;
    scrollbar-width: none;
  }

  .scrollbar-hide::-webkit-scrollbar {
    display: none;
  }
}
```

### Responsive Design

Use Tailwind responsive prefixes:

```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  {/* 1 column on mobile, 2 on tablet, 3 on desktop */}
</div>
```

**Breakpoints:**

- `sm:` - 640px
- `md:` - 768px
- `lg:` - 1024px
- `xl:` - 1280px
- `2xl:` - 1536px

### Dark Mode

Toggle theme with the `dark` class on `<html>`:

```tsx
// Toggle dark mode
function toggleDarkMode() {
  document.documentElement.classList.toggle("dark");
}
```

## Adding New Pages

### Step-by-Step Guide

#### Step 1: Create Page Component

Create `src/pages/my-feature.tsx`:

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useMyFeature } from "@/hooks/use-api";

export function MyFeaturePage(): JSX.Element {
  const { data, isLoading } = useMyFeature();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">My Feature</h1>
        <p className="text-muted-foreground">Description of this feature</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Feature Data</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? <div>Loading...</div> : <div>{/* Display data */}</div>}
        </CardContent>
      </Card>
    </div>
  );
}
```

#### Step 2: Add Route

Update `src/App.tsx`:

```tsx
import { MyFeaturePage } from "@/pages/my-feature";

// Inside Routes
<Route path="/my-feature" element={<MyFeaturePage />} />;
```

#### Step 3: Add to Navigation

Update sidebar navigation in `src/components/layout/app-sidebar.tsx`:

```tsx
import { MyIcon } from "lucide-react";

const menuItems = [
  // ... existing items
  {
    title: "My Feature",
    url: "/my-feature",
    icon: MyIcon,
  },
];
```

#### Step 4: Add API Hook (if needed)

Follow [Adding New API Endpoints](#adding-new-api-endpoints).

## Best Practices

### Do's ✅

#### Use shadcn components for all UI

```tsx
import { Button, Card, Table } from "@/components/ui/*";
```

#### Type everything strictly

```tsx
interface Props {
  readonly value: string;
  readonly onChange: (value: string) => void;
}
```

#### Use React Query for data fetching

```tsx
const { data, isLoading, error } = useMyData();
```

#### Compose components from primitives

```tsx
export function MetricCard({ title, value }: Props): JSX.Element {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>{value}</CardContent>
    </Card>
  );
}
```

#### Handle loading and error states

```tsx
if (isLoading) return <Skeleton />;
if (error) return <ErrorMessage error={error} />;
return <DataDisplay data={data} />;
```

#### Use Tailwind utilities

```tsx
<div className="flex items-center gap-4 p-6" />
```

#### Keep components focused

```tsx
// One responsibility per component
export function UserAvatar({ user }: Props) {}
export function UserProfile({ user }: Props) {}
```

### Don'ts ❌

#### Create custom UI elements

```tsx
// WRONG
<div className="custom-button" onClick={...}>Click</div>

// RIGHT
import { Button } from '@/components/ui/button';
<Button onClick={...}>Click</Button>
```

#### Use `any` type

```tsx
// WRONG
function handle(data: any) {}

// RIGHT
function handle(data: UserData) {}
```

#### Skip typing props

```tsx
// WRONG
export function Component(props) {}

// RIGHT
interface Props {
  readonly title: string;
}
export function Component({ title }: Props): JSX.Element {}
```

#### Inline fetch calls

```tsx
// WRONG
useEffect(() => {
  fetch('/api/data').then(...)
}, []);

// RIGHT
const { data } = useMyData();
```

#### Modify shadcn components

```tsx
// WRONG - Editing src/components/ui/button.tsx

// RIGHT - Create a composed component
export function MyButton(props: Props) {
  return <Button {...customProps} />;
}
```

#### Use global state unnecessarily

```tsx
// WRONG - Global state for server data
const [users, setUsers] = useState([]);

// RIGHT - React Query manages server state
const { data: users } = useUsers();
```

#### Hardcode colors

```tsx
// WRONG
<div className="bg-blue-500">

// RIGHT - Use theme variables
<div className="bg-primary">
```

## Common Patterns

### Loading States

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export function DataComponent(): JSX.Element {
  const { data, isLoading } = useData();

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-20 w-full" />
        </CardContent>
      </Card>
    );
  }

  return <DataDisplay data={data} />;
}
```

### Error Handling

```tsx
export function DataComponent(): JSX.Element {
  const { data, error } = useData();

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-destructive">Error</CardTitle>
        </CardHeader>
        <CardContent>
          <p>{error.message}</p>
        </CardContent>
      </Card>
    );
  }

  return <DataDisplay data={data} />;
}
```

### Pagination

```tsx
import { PaginationControls } from "@/components/ui/pagination-controls";
import { useState } from "react";

export function PaginatedTable(): JSX.Element {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  const { data } = useData(page, pageSize);

  return (
    <>
      <Table>{/* Table content */}</Table>
      <PaginationControls
        currentPage={page}
        pageSize={pageSize}
        totalPages={data?.pagination.total_pages ?? 1}
        totalItems={data?.pagination.total_items ?? 0}
        onPageChange={setPage}
        onPageSizeChange={setPageSize}
      />
    </>
  );
}
```

### Data Export

```tsx
import { DownloadButtons } from "@/components/ui/download-buttons";

export function DataTable(): JSX.Element {
  const { data } = useData();

  return (
    <>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold">Data</h2>
        <DownloadButtons data={data?.items ?? []} filename="data" />
      </div>
      <Table>{/* Table content */}</Table>
    </>
  );
}
```

### Filters

```tsx
import { MultiSelect } from "@/components/ui/multi-select";
import { useState } from "react";

export function FilteredData(): JSX.Element {
  const [selectedRepos, setSelectedRepos] = useState<readonly string[]>([]);
  const [selectedUsers, setSelectedUsers] = useState<readonly string[]>([]);

  const { data: repos } = useRepositories();
  const { data: filteredData } = useData({
    repositories: selectedRepos,
    users: selectedUsers,
  });

  return (
    <>
      <div className="flex gap-4 mb-6">
        <MultiSelect
          placeholder="Filter by repository"
          options={repos?.map((r) => ({ label: r.name, value: r.name })) ?? []}
          selected={selectedRepos}
          onChange={setSelectedRepos}
        />
        <MultiSelect
          placeholder="Filter by user"
          options={users?.map((u) => ({ label: u, value: u })) ?? []}
          selected={selectedUsers}
          onChange={setSelectedUsers}
        />
      </div>
      <DataDisplay data={filteredData} />
    </>
  );
}
```

## Advanced Components

### User PRs Modal

The User PRs Modal is a two-panel modal dialog that displays a user's pull requests alongside a detailed PR Story timeline.

**Location:** `src/components/user-prs/user-prs-modal.tsx`

**Features:**

- **Two-panel layout:** Left panel shows PR list, right panel shows PR Story timeline
- **Role-based filtering:** View PRs where user was creator, reviewer, approver, or LGTM provider
- **Search and sorting:** Search PRs by title/number, sort by date/state
- **State filtering:** Filter by open, merged, or closed PRs
- **Pagination:** Navigate through large PR lists with page controls
- **Real-time selection:** Click any PR to see its timeline in the right panel

**Usage:**

```tsx
import { UserPRsModal } from "@/components/user-prs/user-prs-modal";

export function ContributorsTable(): JSX.Element {
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const handleUserClick = (username: string, category: string) => {
    setSelectedUser(username);
    setSelectedCategory(category);
    setModalOpen(true);
  };

  return (
    <>
      <button onClick={() => handleUserClick("alice", "pr_creators")}>View Alice's PRs</button>

      <UserPRsModal
        open={modalOpen}
        onOpenChange={setModalOpen}
        username={selectedUser}
        category={selectedCategory}
      />
    </>
  );
}
```

**Modal Props:**

```typescript
interface UserPRsModalProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly username: string | null;
  readonly category: string | null; // "pr_creators" | "pr_reviewers" | "pr_approvers" | "pr_lgtm"
}
```

### PR Story Timeline

The PR Story Timeline visualizes the complete lifecycle of a pull request as a chronological timeline.

**Location:** `src/components/pr-story/pr-story-timeline.tsx`

**Event Types Supported:**

- **PR Events:** Opened, merged, closed, reopened
- **Commits:** Code pushes to the PR branch
- **Reviews:** Review submitted, approved, changes requested
- **Comments:** Issue comments, review comments
- **Check Runs:** CI/CD status checks (pending, success, failure)
- **Labels:** Labels added or removed
- **Milestones:** Milestone associations

**Features:**

- **Event grouping:** Collapsible groups for commits and check runs
- **Color-coded icons:** Visual indicators for event types (green for success, red for failures)
- **Relative timestamps:** Shows "2 hours ago" with absolute time on hover
- **Detailed metadata:** Commit SHAs, check run status, review decisions
- **Expandable details:** Click to expand grouped events like multiple commits

**Usage:**

```tsx
import { PRStoryTimeline } from "@/components/pr-story/pr-story-timeline";
import { usePRStory } from "@/hooks/use-api";

export function PRDetailView({ prNumber }: { readonly prNumber: number }): JSX.Element {
  const { data: story, isLoading } = usePRStory({ pr_number: prNumber });

  if (isLoading) {
    return <Skeleton className="h-96" />;
  }

  return (
    <div>
      <h2>PR #{prNumber} Timeline</h2>
      <PRStoryTimeline events={story?.events ?? []} />
    </div>
  );
}
```

**Event Filtering:**

The timeline supports filtering by event type:

```tsx
import { EventTypeFilter, PRStoryTimeline } from "@/components/pr-story";

export function FilteredTimeline(): JSX.Element {
  const [filter, setFilter] = useState<EventTypeFilter>("all");
  const { data: story } = usePRStory({ pr_number: 123 });

  // Filter events by type
  const filteredEvents =
    filter === "all"
      ? (story?.events ?? [])
      : (story?.events.filter((e) => e.event_type === filter) ?? []);

  return (
    <>
      <select value={filter} onChange={(e) => setFilter(e.target.value as EventTypeFilter)}>
        <option value="all">All Events</option>
        <option value="pr_opened">PR Events</option>
        <option value="commit">Commits</option>
        <option value="review">Reviews</option>
        <option value="check_run">Check Runs</option>
      </select>
      <PRStoryTimeline events={filteredEvents} />
    </>
  );
}
```

**Event Structure:**

```typescript
interface PRStoryEvent {
  readonly event_type: PREventType;
  readonly created_at: string;
  readonly actor: string | null;
  readonly details: Record<string, unknown>;
}

type PREventType =
  | "pr_opened"
  | "pr_merged"
  | "pr_closed"
  | "pr_reopened"
  | "commit"
  | "review_submitted"
  | "review_approved"
  | "review_changes_requested"
  | "comment"
  | "review_comment"
  | "label_added"
  | "label_removed"
  | "milestone_added"
  | "check_run";
```

## Code Quality

### Linting

The project uses **ESLint** with strict TypeScript rules:

```bash
# Run linter
bun run lint

# Auto-fix issues (limited)
bunx eslint . --fix
```

**ESLint configuration:**

- `@typescript-eslint/strict-type-checked` - Strict TypeScript rules
- `eslint-plugin-react-hooks` - React Hooks rules
- `eslint-plugin-react-refresh` - Fast Refresh rules

### Pre-commit Hooks

> **Note:** The repository uses Python-side `pre-commit` tooling at the root level for unified hook management. Husky + lint-staged are _optional_ if you prefer frontend-only pre-commit hooks during development.

**Optional: Frontend-only Husky setup**

To add frontend-only pre-commit hooks (independent of the repository's Python pre-commit):

1. Install Husky: `bun add -d husky`
2. Install lint-staged: `bun add -d lint-staged`
3. Initialize Husky: `bunx husky init`
4. Add lint-staged configuration to `package.json`:

```json
{
  "lint-staged": {
    "*.{ts,tsx}": ["eslint --fix", "prettier --write"]
  }
}
```

**With pre-commit hooks, files are automatically:**

1. Linted with ESLint
2. Formatted with Prettier
3. Type-checked by TypeScript

### CRITICAL: No Linter Suppressions

#### NEVER suppress linter warnings

```tsx
// ❌ WRONG
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const data: any = response;

// ✅ CORRECT - Fix the code
const data: ResponseData = response;
```

#### If you believe a rule is wrong

1. **STOP** - Do NOT add suppression
2. **ASK** for explicit approval
3. **DOCUMENT** in commit message

### Type Checking

```bash
# Type check without emitting files
bun run build

# Or use tsc directly
bunx tsc --noEmit
```

## Debugging

### Browser DevTools

**React DevTools:**

- Install React DevTools extension
- Inspect component props and state
- Profile component renders

**Network Tab:**

- Monitor API calls to `/api/metrics/*`
- Check request/response payloads
- Verify query parameters

**Console:**

- React Query DevTools (enable in development)
- Log errors and warnings

### Common Issues

#### Issue: API calls fail with 404

```text
Solution: Ensure backend is running on port 8765
Check: http://localhost:8765/api/metrics/summary
```

#### Issue: Types don't match API response

```text
Solution: Update type definitions in src/types/
Verify: Check actual API response in Network tab
```

#### Issue: Component not re-rendering on data change

```text
Solution: Ensure React Query cache is working
Check: Query key dependencies in useQuery
```

#### Issue: Tailwind classes not working

```text
Solution: Restart dev server (Vite HMR issue)
Check: Class names are correct (no typos)
```

## Testing

### Unit Tests (Bun Test Runner)

The project uses **Bun's built-in test runner** with a Vitest-compatible API:

```bash
# Run tests
bun test

# Watch mode
bun test --watch

# Coverage
bun test --coverage
```

**Test file pattern:** `*.test.tsx` or `*.test.ts`

**Example:**

```tsx
// src/components/metric-card.test.tsx
import { render, screen } from "@testing-library/react";
import { MetricCard } from "./metric-card";

describe("MetricCard", () => {
  it("renders title and value", () => {
    render(<MetricCard title="Total PRs" value={42} />);
    expect(screen.getByText("Total PRs")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });
});
```

### Component Testing

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
);

it("fetches and displays data", async () => {
  render(<DataComponent />, { wrapper });
  expect(await screen.findByText("Data loaded")).toBeInTheDocument();
});
```

## Resources

### Documentation

- **React 19:** [react.dev](https://react.dev)
- **TypeScript:** [typescriptlang.org](https://www.typescriptlang.org)
- **shadcn/ui:** [ui.shadcn.com](https://ui.shadcn.com)
- **Tailwind CSS v4:** [tailwindcss.com](https://tailwindcss.com)
- **React Query:** [tanstack.com/query](https://tanstack.com/query)
- **Radix UI:** [radix-ui.com](https://www.radix-ui.com)
- **Vite:** [vitejs.dev](https://vitejs.dev)

### VS Code Extensions

Recommended extensions for development:

- **ESLint** - Linting
- **Prettier** - Code formatting
- **Tailwind CSS IntelliSense** - Tailwind class autocomplete
- **React DevTools** - Component debugging

### Path Aliases

The project uses `@/` for clean imports:

```tsx
// Instead of: import { Button } from '../../../components/ui/button'
import { Button } from "@/components/ui/button";

// Configured in:
// - tsconfig.json: "paths": { "@/*": ["./src/*"] }
// - vite.config.ts: alias: { "@": "./src" }
```

## Contributing

### Workflow

1. **Create feature branch:** `feature/my-feature`
2. **Make changes**
3. **Test locally:** `bun run dev`
4. **Lint code:** `bun run lint`
5. **Type check:** `bun run build`
6. **Commit** (pre-commit hooks run automatically)
7. **Create PR**

### Code Review Checklist

- [ ] All components use shadcn/ui primitives
- [ ] All props and functions are typed
- [ ] No `any` types
- [ ] Loading and error states handled
- [ ] Tailwind used for styling (no inline styles)
- [ ] No linter suppressions
- [ ] API hooks follow existing patterns
- [ ] Types defined in `src/types/`
- [ ] Responsive design tested

---

## Quick Reference

### File Templates

**Page Component:**

```tsx
// src/pages/my-page.tsx
export function MyPage(): JSX.Element {
  const { data, isLoading } = useMyData();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Page Title</h1>
        <p className="text-muted-foreground">Description</p>
      </div>
      {/* Content */}
    </div>
  );
}
```

**Composed Component:**

```tsx
// src/components/dashboard/my-component.tsx
import { Card } from "@/components/ui/card";

interface Props {
  readonly title: string;
}

export function MyComponent({ title }: Props): JSX.Element {
  return <Card>{title}</Card>;
}
```

**API Hook:**

```typescript
// src/hooks/use-api.ts
export function useMyData(params?: MyParams) {
  return useQuery<MyResponse>({
    queryKey: queryKeys.myData(params),
    queryFn: () => fetchApi<MyResponse>("/my-endpoint", params),
  });
}
```

**Type Definition:**

```typescript
// src/types/my-types.ts
export interface MyData {
  readonly id: string;
  readonly name: string;
  readonly count: number;
}

export interface MyResponse {
  readonly data: readonly MyData[];
  readonly total: number;
}
```

### Common Commands

```bash
# Development
bun run dev                # Start dev server
./dev/run-all.sh          # Start frontend + backend

# Build
bun run build             # Production build
bun run preview           # Preview build

# Quality
bun run lint              # Run linter
bunx tsc --noEmit         # Type check

# Dependencies
bun install               # Install deps
bun add <package>         # Add dependency
bun add -d <package>      # Add dev dependency
bunx shadcn@latest add <component>  # Add shadcn component
```
