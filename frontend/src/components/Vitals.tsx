export type VitalTone = "pass" | "warn" | "fail";
export type Vital = { check: string; status: string; detail: string; tone: VitalTone };

const TONE = {
  pass: { dot: "bg-[#3fbf86]", text: "text-[#7fdcb0]", label: "Pass" },
  warn: { dot: "bg-[#f2b544]", text: "text-[#f6cd7c]", label: "Warning" },
  fail: { dot: "bg-[#ff6b5e]", text: "text-[#ff9b92]", label: "Action needed" },
};

/** The product's signature element: a monitor-style readout of one domain. */
export function VitalsPanel({ domain, vitals, checkedAt }: { domain: string; vitals: Vital[]; checkedAt: string }) {
  return (
    <figure className="rounded-xl border border-white/10 bg-navy-950/60 p-5 shadow-2xl shadow-navy-950/40 backdrop-blur">
      <figcaption className="flex items-baseline justify-between gap-4 border-b border-white/10 pb-3">
        <span className="font-display text-[17px] font-semibold text-white">{domain}</span>
        <span className="text-xs text-navy-100/60">{checkedAt}</span>
      </figcaption>
      <svg viewBox="0 0 400 48" className="mt-3 h-10 w-full" aria-hidden="true">
        <path className="vitals-line" d="M0 26h120l14-18 18 34 16-24 10 8h84l12-12 14 22 10-10h102"
          fill="none" stroke="#F47920" strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      <dl className="mt-3 divide-y divide-white/10">
        {vitals.map((v) => (
          <div key={v.check} className="grid grid-cols-[4.5rem_1fr] items-baseline gap-x-3 py-2.5 sm:grid-cols-[5rem_8.5rem_1fr]">
            <dt className="font-display text-sm font-semibold text-white">{v.check}</dt>
            <dd className={`flex items-center gap-2 text-sm font-medium ${TONE[v.tone].text}`}>
              <span className={`h-2 w-2 rounded-full ${TONE[v.tone].dot}`} aria-hidden="true" />
              {v.status}
            </dd>
            <dd className="col-span-2 text-[13px] text-navy-100/70 sm:col-span-1">{v.detail}</dd>
          </div>
        ))}
      </dl>
    </figure>
  );
}
