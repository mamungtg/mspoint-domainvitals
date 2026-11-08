import { Link } from "react-router-dom";
import { Card } from "../components/ui";
import { isManager } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useWorkspace } from "../lib/workspace";

const COMING = [
  { title: "Add your first domain", body: "Verify ownership with a DNS TXT record, then DomainVitals checks SPF, DKIM, DMARC, MX and SSL/TLS.", soon: "Sprint 2" },
  { title: "DMARC reports", body: "Point your rua address to DomainVitals and see who sends mail as your domain.", soon: "Sprint 4" },
  { title: "Alerts", body: "Get notified about DNS changes, failing authentication and expiring certificates.", soon: "Sprint 5" },
];

export default function Dashboard() {
  const { user } = useAuth();
  const { current } = useWorkspace();
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Welcome{user?.full_name ? `, ${user.full_name}` : ""}</h1>
        <p className="text-sm text-slate-600">Workspace: {current?.name}</p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {COMING.map((c) => (
          <Card key={c.title} title={c.title}>
            <p className="text-sm text-slate-600">{c.body}</p>
            <p className="mt-3 text-xs font-medium text-slate-500">Coming in {c.soon}</p>
          </Card>
        ))}
      </div>
      {isManager(current?.role) && (
        <Card title="Your team">
          <p className="text-sm text-slate-600">Invite colleagues to share this workspace.</p>
          <Link to="/settings/members" className="mt-3 inline-block text-sm font-medium text-sky-700">Manage members →</Link>
        </Card>
      )}
    </div>
  );
}
