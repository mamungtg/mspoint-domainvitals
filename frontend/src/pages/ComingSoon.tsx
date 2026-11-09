import { ReactNode } from "react";
import { Card, EmptyState, PageHeader } from "../components/ui";

export default function ComingSoon({ title, description, what, icon }: { title: string; description: string; what: string[]; icon?: ReactNode }) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <Card>
        <EmptyState icon={icon} title="Arriving in a coming release"
          body={<span>This page will show:</span>}
          action={<ul className="space-y-2 text-left text-sm text-ink">{what.map((w) => (
            <li key={w} className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-orange-500" aria-hidden="true" />{w}</li>))}</ul>} />
      </Card>
    </>
  );
}
