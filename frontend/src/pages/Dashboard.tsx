import { Link } from "react-router-dom";
import { Card, cls, linkCls, PageHeader } from "../components/ui";
import { isManager } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useWorkspace } from "../lib/workspace";

type Step = { title: string; body: string; done: boolean; action?: { to: string; label: string }; later?: string };

export default function Dashboard() {
  const { user } = useAuth();
  const { current } = useWorkspace();
  const manager = isManager(current?.role);

  const steps: Step[] = [
    { title: "Confirm your email address", body: "Needed before you can invite teammates or receive alerts.", done: !!user?.email_verified },
    { title: "Add your first domain", body: "Enter a domain you manage, such as a client's main website domain.", done: false, later: "Available in the next release" },
    { title: "Prove you control it", body: "Publish one TXT record so DomainVitals only scans domains you are allowed to check.", done: false, later: "Available in the next release" },
    ...(manager ? [{ title: "Invite your team", body: "Give colleagues access with the right role.", done: false,
      action: { to: "/settings/members", label: "Invite teammates" } }] : []),
  ];
  const doneCount = steps.filter((s) => s.done).length;

  return (
    <>
      <PageHeader
        title={user?.full_name ? `Welcome, ${user.full_name.split(" ")[0]}` : "Welcome"}
        description={`Here is where ${current?.name ?? "your workspace"} stands.`}
      />
      <Card title="Get set up" description={`${doneCount} of ${steps.length} steps done`} padded={false}>
        <ol className="divide-y divide-line">
          {steps.map((s, i) => (
            <li key={s.title} className="flex gap-4 px-5 py-4">
              <span className={cls("mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[13px] font-semibold",
                s.done ? "bg-pass text-white" : "border border-line bg-white text-navy-900")} aria-hidden="true">
                {s.done ? "✓" : i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <p className={cls("font-medium", s.done ? "text-muted line-through decoration-muted/50" : "text-navy-900")}>
                  {s.title}<span className="sr-only">{s.done ? " (done)" : ""}</span>
                </p>
                <p className="mt-0.5 text-sm text-muted">{s.body}</p>
                {!s.done && s.action && <Link to={s.action.to} className={cls(linkCls, "mt-2 inline-block text-sm")}>{s.action.label}</Link>}
                {!s.done && s.later && <p className="mt-2 text-xs font-medium text-orange-700">{s.later}</p>}
              </div>
            </li>
          ))}
        </ol>
      </Card>
    </>
  );
}
