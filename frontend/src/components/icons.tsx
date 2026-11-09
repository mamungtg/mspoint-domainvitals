// Small stroke icons (24px grid, currentColor).
const base = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8,
  strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };

export const IconHome = () => <svg {...base}><path d="M3 11.5 12 4l9 7.5" /><path d="M5.5 10v9.5h13V10" /></svg>;
export const IconGlobe = () => <svg {...base}><circle cx="12" cy="12" r="8.5" /><path d="M3.5 12h17M12 3.5c2.5 2.6 3.7 5.4 3.7 8.5s-1.2 5.9-3.7 8.5c-2.5-2.6-3.7-5.4-3.7-8.5s1.2-5.9 3.7-8.5Z" /></svg>;
export const IconBell = () => <svg {...base}><path d="M6 16.5V11a6 6 0 1 1 12 0v5.5l1.5 2h-15Z" /><path d="M10 20.5a2 2 0 0 0 4 0" /></svg>;
export const IconUsers = () => <svg {...base}><circle cx="9" cy="8.5" r="3.5" /><path d="M2.5 19.5c.8-3.3 3.3-5 6.5-5s5.7 1.7 6.5 5" /><path d="M16 5.2a3.3 3.3 0 0 1 0 6.6M18 14.8c1.8.6 3 2.2 3.5 4.7" /></svg>;
export const IconSettings = () => <svg {...base}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" /></svg>;
export const IconLogout = () => <svg {...base}><path d="M15 4h3.5A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5H15" /><path d="M10 16.5 14.5 12 10 7.5M14.5 12H4" /></svg>;
export const IconMenu = () => <svg {...base}><path d="M4 7h16M4 12h16M4 17h16" /></svg>;
export const IconClose = () => <svg {...base}><path d="M6 6l12 12M18 6 6 18" /></svg>;
export const IconFile = () => <svg {...base}><path d="M6 3.5h8l4 4v13H6Z" /><path d="M14 3.5v4h4M9 12.5h6M9 16h6" /></svg>;
export const IconLock = () => <svg {...base}><rect x="5" y="10.5" width="14" height="10" rx="1.5" /><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" /></svg>;
export const IconSearch = () => <svg {...base}><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4.5 4.5" /></svg>;
export const IconCard = () => <svg {...base}><rect x="3" y="5.5" width="18" height="13" rx="1.5" /><path d="M3 10h18M7 15h3" /></svg>;
export const IconSun = () => <svg {...base}><circle cx="12" cy="12" r="4" /><path d="M12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4" /></svg>;
export const IconMoon = () => <svg {...base}><path d="M19.5 14.5A8 8 0 0 1 9.5 4.5a8 8 0 1 0 10 10Z" /></svg>;
export const IconChevron = () => <svg {...base}><path d="m9 6 6 6-6 6" /></svg>;
export const IconPlus = () => <svg {...base}><path d="M12 5v14M5 12h14" /></svg>;
export const IconRefresh = () => <svg {...base}><path d="M20 11a8 8 0 1 0-2.3 5.7" /><path d="M20 4.5V11h-6.5" /></svg>;
