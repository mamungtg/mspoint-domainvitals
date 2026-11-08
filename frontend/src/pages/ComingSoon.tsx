import { Card, PageHeader } from "../components/ui";

export default function ComingSoon({ title, description, when }: { title: string; description: string; when: string }) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <Card>
        <p className="text-muted">This part of DomainVitals is being built and arrives in {when}.</p>
      </Card>
    </>
  );
}
