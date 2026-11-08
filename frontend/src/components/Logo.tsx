/** MSPoint shield with a pulse line - the DomainVitals mark. */
export function LogoMark({ size = 32, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className={className}>
      <path d="M16 2.5 4.5 7v8.2c0 7.1 4.9 12.4 11.5 14.3 6.6-1.9 11.5-7.2 11.5-14.3V7L16 2.5Z" fill="#0F1F3D" stroke="#F47920" strokeWidth="1.6" />
      <path d="M8.5 16.5h4l2-4.5 3 8 2-3.5h4" fill="none" stroke="#F47920" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Logo({ inverse = false, size = 32 }: { inverse?: boolean; size?: number }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <LogoMark size={size} />
      <span className="leading-tight">
        <span className={`block font-display text-[17px] font-semibold ${inverse ? "text-white" : "text-navy-900"}`}>DomainVitals</span>
        <span className={`block text-xs ${inverse ? "text-navy-100/70" : "text-muted"}`}>by MSPoint</span>
      </span>
    </span>
  );
}
