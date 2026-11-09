from __future__ import annotations

from dataclasses import asdict, dataclass, field

CRITICAL, WARNING, INFO = "critical", "warning", "info"
PASS, WARN, FAIL, ERROR = "pass", "warn", "fail", "error"


@dataclass
class Finding:
    code: str
    severity: str  # critical | warning | info
    title: str
    detail: str
    fix: str = ""


@dataclass
class CheckResult:
    check: str
    summary: str = ""
    record: str | None = None
    findings: list[Finding] = field(default_factory=list)
    data: dict = field(default_factory=dict)
    error: bool = False

    @property
    def status(self) -> str:
        if self.error:
            return ERROR
        sev = {f.severity for f in self.findings}
        if CRITICAL in sev:
            return FAIL
        if WARNING in sev:
            return WARN
        return PASS

    def add(self, code, severity, title, detail, fix=""):
        self.findings.append(Finding(code, severity, title, detail, fix))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status
        d.pop("error")
        return d


def parse_tags(record: str) -> dict[str, str]:
    """Parse 'k=v; k2=v2' (DMARC/DKIM tag lists). Later duplicates are ignored."""
    tags: dict[str, str] = {}
    for part in record.split(";"):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip().lower()
        if k and k not in tags:
            tags[k] = v.strip()
    return tags
