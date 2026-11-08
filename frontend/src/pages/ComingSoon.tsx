import { Card } from "../components/ui";

export default function ComingSoon({ title, when }: { title: string; when: string }) {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
      <Card><p className="text-sm text-slate-600">This section is being built and arrives in {when}.</p></Card>
    </div>
  );
}
