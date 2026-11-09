# DNS monitoring

Code: `backend/apps/dns_monitor/`. Tests: `backend/tests/test_dns_monitoring.py`, `test_checks.py`.

## What a scan does

`services.execute_scan(scan)` runs `checks.run_checks(domain, resolver, dkim_selectors, hosts)`, which returns five check results in `CHECK_ORDER`: `spf`, `dkim`, `dmarc`, `mx`, `dns`. The `dns` result's record inventory is moved out into `DnsScan.records`, the scan is saved, and `record_changes(scan)` compares it with the previous completed scan.

Hosts tracked by default are the apex and `www`. Customers add up to 20 more subdomains in **Domain → Settings → Tracked host names** (`Domain.dns_watch_names`).

## Resolvers

| Class | Used by | Notes |
| --- | --- | --- |
| `LiveResolver` | Production | Asks 1.1.1.1, 8.8.8.8 and 9.9.9.9. Caps each scan at 140 queries so a hostile SPF tree cannot run away. |
| `FakeResolver` | Tests and the demo workspace | Answers from a Python dict zone. Supports `TTL` and `AUTH` overrides per name. |

Both implement `txt`, `mx`, `a`, `records(name, rtype)` (returns `{"ttl", "values"}` or `None` for NXDOMAIN) and `authoritative(domain)`.

`probe_authoritative` sends a non-recursive SOA query straight to each name server's public IP (UDP, then TCP on truncation) and records whether it answered authoritatively and with which serial.

## Checks and findings

### SPF (`checks/spf.py`)
| Code | Severity | Meaning |
| --- | --- | --- |
| `spf_missing` | critical | No `v=spf1` record. |
| `spf_multiple` | critical | More than one SPF record (RFC 7208 permerror). |
| `spf_syntax` | critical | Unknown mechanism, bad qualifier, invalid ip4/ip6 address or CIDR. |
| `spf_too_many_lookups` | critical | More than 10 DNS-querying terms across the include tree. |
| `spf_near_limit` | warning | 9 or 10 lookups. |
| `spf_plus_all` | critical | `+all` lets anyone send. |
| `spf_loop`, `spf_include_missing` | critical/warning | Include loops or includes without SPF. |
| `spf_duplicate` | warning | The same term appears twice. |
| `spf_neutral_all`, `spf_no_all`, `spf_softfail` | warning/info | Weak or missing terminator. |

### DMARC, DKIM, MX
Policy validation (`p`, `sp`, `pct`, `rua`), multiple records, DKIM key discovery over common plus custom selectors with key size, MX presence, null MX and host resolution. See the finding codes in each module.

### DNS infrastructure (`checks/infra.py`)
| Code | Severity | Meaning |
| --- | --- | --- |
| `dns_ns_missing` | critical | No NS records. |
| `dns_ns_single` | warning | Only one name server: a single outage takes the domain offline. |
| `dns_ns_lame`, `dns_ns_unreachable` | warning | A listed name server does not answer authoritatively, or not at all. |
| `dns_soa_serial_mismatch` | warning | Name servers serve different zone versions (failed zone transfer). |
| `dns_soa_missing` | critical | No SOA. |
| `dns_soa_values` | info | Refresh, retry, expire or minimum outside RFC 1912 ranges. |
| `dns_cname_apex` | critical | CNAME at the zone apex. |
| `dns_dangling_cname` | critical | A tracked CNAME points to a name that does not exist (subdomain takeover risk). |
| `dns_apex_no_address` | info | The bare domain has no A/AAAA record. |
| `dns_ttl_low`, `dns_ttl_high` | info | NS/MX TTL under 5 minutes, or any TTL over a day. |

## Record inventory and change detection

The inventory is keyed `"<name> <TYPE>"` with sorted values and the TTL. Apex types: A, AAAA, MX, NS, TXT, SOA, CAA. Tracked hosts: CNAME, otherwise A/AAAA. Also `_dmarc` TXT and each DKIM selector found.

`changes.diff_records(old, new)` yields `added`, `removed`, `changed` and `ttl` rows stored as `DnsChange`. Rules:
- The first scan is a baseline and records nothing.
- A scan whose `dns` check errored is not compared, so a resolver outage never looks like every record being deleted.
- An SOA that differs only by serial is ignored; the serial moves on every edit and would duplicate the real change.

## Propagation

`propagation.check_propagation(name, rtype)` asks the zone's authoritative servers and four public resolvers (Cloudflare, Google, Quad9, OpenDNS) in parallel. The expected answer is the authoritative consensus (public majority if no authoritative answer). Each server is `match`, `different`, `missing` or `error`. Available per record in **Domain → DNS records** and for any name in the **Domain checker**.

## UI

- **Domain → Health**: five check cards including DNS with name server status.
- **Domain → DNS records**: name servers, record table with TTL and last change, per-record propagation, change history with old/new diff. Deep link: `/domains/<id>?tab=records`.
- **Overview → Recent DNS changes** across the workspace.
- **Domain checker**: `DNS health` option and a propagation tool.
