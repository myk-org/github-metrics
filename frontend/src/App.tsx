import { BrowserRouter, Routes, Route } from "react-router-dom";
import { FilterProvider } from "@/contexts/filter-context";
import { Layout } from "@/components/layout";
import { OverviewPage, ContributorsPage, TeamDynamicsPage, PRLifecyclePage } from "@/pages";

function App(): React.ReactElement {
  return (
    <FilterProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/contributors" element={<ContributorsPage />} />
            <Route path="/team-dynamics" element={<TeamDynamicsPage />} />
            <Route path="/pr-lifecycle" element={<PRLifecyclePage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </FilterProvider>
  );
}

export default App;
