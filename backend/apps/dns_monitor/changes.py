"""Compare record inventories between scans."""

from __future__ import annotations


def _soa_without_serial(values: list[str]) -> list[str]:
    out = []
    for v in values:
        parts = v.split()
        out.append(" ".join(parts[:2] + parts[3:]) if len(parts) == 7 else v)
    return out


def diff_records(old: dict, new: dict) -> list[dict]:
    """Added, removed and changed record sets, plus TTL-only changes.

    An SOA whose only difference is the serial is skipped: the serial moves on
    every zone edit, so reporting it would duplicate the real change.
    """
    out = []
    for key in sorted(set(old) | set(new)):
        name, rtype = key.rsplit(" ", 1)
        a, b = old.get(key), new.get(key)
        base = {
            "name": name,
            "rtype": rtype,
            "old_values": a["values"] if a else [],
            "new_values": b["values"] if b else [],
            "old_ttl": a["ttl"] if a else None,
            "new_ttl": b["ttl"] if b else None,
        }
        if a is None:
            out.append({**base, "kind": "added"})
        elif b is None:
            out.append({**base, "kind": "removed"})
        elif rtype == "SOA" and _soa_without_serial(a["values"]) == _soa_without_serial(b["values"]):
            continue
        elif sorted(a["values"]) != sorted(b["values"]):
            out.append({**base, "kind": "changed"})
        elif a["ttl"] != b["ttl"]:
            out.append({**base, "kind": "ttl"})
    return out
