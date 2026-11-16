import { useState } from "react";
import { api, Domain, errorText } from "../lib/api";
import { Alert, Button, Card, Modal } from "./ui";

/** Confirmation dialog for deleting a domain and everything recorded about it. */
export function RemoveDomainDialog({ domain, onClose, onRemoved }: { domain: Pick<Domain, "id" | "name" | "is_verified">; onClose: () => void; onRemoved: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function remove() {
    setBusy(true); setError("");
    try { await api(`/domains/${domain.id}/`, { method: "DELETE" }); onRemoved(); }
    catch (e) { setError(errorText(e)); setBusy(false); }
  }
  return (
    <Modal open onClose={onClose} title={`Remove ${domain.name}?`}
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button variant="danger" busy={busy} onClick={remove}>Remove domain</Button></>}>
      <div className="space-y-3 text-sm text-ink">
        <p>
          {domain.is_verified
            ? "Monitoring stops and its scan history, DNS change log, certificates and alerts are deleted. This cannot be undone."
            : "The domain was never verified, so nothing has been collected for it yet."}
        </p>
        <p className="text-muted">You can add it again later; it will need to be verified again.</p>
        {error && <Alert>{error}</Alert>}
      </div>
    </Modal>
  );
}

export function RemoveDomainCard({ domain, onRemoved }: { domain: Domain; onRemoved: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <Card title="Remove domain">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">Stops monitoring and deletes everything recorded for this domain.</p>
        <Button variant="danger" onClick={() => setOpen(true)} aria-label={`Remove ${domain.name}`}>Remove domain</Button>
      </div>
      {open && <RemoveDomainDialog domain={domain} onClose={() => setOpen(false)} onRemoved={onRemoved} />}
    </Card>
  );
}
