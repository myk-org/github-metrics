import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { GitPullRequest } from "lucide-react";

export function PullRequestsPage(): React.ReactElement {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Pull Requests</h2>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <GitPullRequest className="h-5 w-5" />
            Recent Pull Requests
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center text-muted-foreground py-8">
            Pull request list with PR story modal coming soon...
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
