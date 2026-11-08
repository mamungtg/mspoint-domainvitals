export function timezones(): string[] {
  try {
    const list = (Intl as unknown as { supportedValuesOf?: (k: string) => string[] }).supportedValuesOf?.("timeZone");
    if (list && list.length) return list.includes("UTC") ? list : ["UTC", ...list];
  } catch { /* older browsers */ }
  return ["UTC", "Asia/Dhaka", "Europe/London", "Europe/Berlin", "America/New_York", "America/Chicago", "America/Los_Angeles"];
}

export function browserTimezone(): string {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"; } catch { return "UTC"; }
}
