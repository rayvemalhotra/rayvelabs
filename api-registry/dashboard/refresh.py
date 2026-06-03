#!/usr/bin/env python3
"""
RayveLabs API Registry — daily dashboard refresh.

Fetches every CORS-blocked feed server-side, parses each into a small summary
JSON, and writes the result to data/ so the static dashboard page can load
them same-origin from rayvelabs.com.

Run by .github/workflows/api-registry-refresh.yml on a daily cron. Safe to
run locally; only writes to data/ and exits 0 even if individual feeds fail
(the partial output is committed so the dashboard keeps working).

Adding a feed: write a fetch_X() that returns a dict; add it to FEEDS.
"""
from __future__ import annotations
import csv
import datetime
import gzip
import io
import json
import os
import sys
import time
import urllib.request
import urllib.error
import zipfile
from pathlib import Path

UA = "RayveLabs-Registry-Refresh/1.0 (+https://rayvelabs.com/api-registry/)"
TIMEOUT = 30
HERE = Path(__file__).parent
DATA = HERE / "data"
DATA.mkdir(exist_ok=True)

# Portal full-feeds output — read by /portal/lookup, /portal/cve, etc.
PORTAL_DATA = HERE.parent.parent / "portal" / "data"
PORTAL_DATA.mkdir(parents=True, exist_ok=True)


def http_get(url: str, headers: dict[str, str] | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def write_portal(name: str, payload) -> None:
    """Write a full-feed file to portal/data/ for the lookup/cve pages."""
    p = PORTAL_DATA / name
    if isinstance(payload, (dict, list)):
        p.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    elif isinstance(payload, str):
        p.write_text(payload)
    elif isinstance(payload, bytes):
        p.write_bytes(payload)
    else:
        raise TypeError(f"unsupported payload type: {type(payload)}")


# ---------------------------------------------------------------------------
# Feed fetchers — each returns (status, summary_dict)
# ---------------------------------------------------------------------------

def fetch_cisa_kev() -> dict:
    """Latest CISA Known Exploited Vulnerabilities."""
    raw = http_get("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json")
    d = json.loads(raw)
    vulns = d.get("vulnerabilities", [])
    # Sort by date added, most recent first
    vulns.sort(key=lambda v: v.get("dateAdded", ""), reverse=True)
    # Full feed for portal CVE explorer — index by CVE
    write_portal("kev.json", {
        "catalog_version": d.get("catalogVersion"),
        "date_released": d.get("dateReleased"),
        "by_cve": {
            v.get("cveID"): {
                "vendor": v.get("vendorProject"),
                "product": v.get("product"),
                "name": v.get("vulnerabilityName"),
                "date_added": v.get("dateAdded"),
                "due_date": v.get("dueDate"),
                "short_desc": v.get("shortDescription"),
                "required_action": v.get("requiredAction"),
                "ransomware": v.get("knownRansomwareCampaignUse") == "Known",
                "cwes": v.get("cwes", []),
            }
            for v in vulns
        }
    })
    recent = []
    for v in vulns[:12]:
        recent.append({
            "cve": v.get("cveID"),
            "vendor": v.get("vendorProject"),
            "product": v.get("product"),
            "name": v.get("vulnerabilityName"),
            "date_added": v.get("dateAdded"),
            "due_date": v.get("dueDate"),
            "ransomware": v.get("knownRansomwareCampaignUse") == "Known",
        })
    return {
        "total": len(vulns),
        "catalog_version": d.get("catalogVersion"),
        "date_released": d.get("dateReleased"),
        "recent": recent,
    }


def fetch_epss_top() -> dict:
    """Top 25 by EPSS score (today's snapshot)."""
    raw = http_get("https://epss.cyentia.com/epss_scores-current.csv.gz")
    text = gzip.decompress(raw).decode("utf-8", errors="replace")
    lines = text.splitlines()
    # First line is metadata (#model_version, score_date, ...). Second is header.
    header_idx = next(i for i, ln in enumerate(lines) if ln.startswith("cve"))
    reader = csv.DictReader(lines[header_idx:])
    rows = [(r["cve"], float(r["epss"]), float(r["percentile"])) for r in reader]
    # Full feed for portal CVE explorer — every CVE keyed by ID
    write_portal("epss.json", {
        "by_cve": {c: {"epss": round(e, 5), "percentile": round(p, 5)} for c, e, p in rows}
    })
    rows.sort(key=lambda x: x[1], reverse=True)
    top = [{"cve": c, "epss": round(e, 5), "percentile": round(p, 5)} for c, e, p in rows[:25]]
    # Metadata line
    meta_line = next((ln for ln in lines[:2] if ln.startswith("#")), "")
    return {
        "total_cves_scored": len(rows),
        "model_metadata": meta_line.lstrip("#").strip(),
        "top": top,
    }


def fetch_mitre_technique_of_day() -> dict:
    """Deterministic 'technique of the day' from MITRE ATT&CK Enterprise STIX.
    Also writes a trimmed full technique catalogue to portal/data/attack.json."""
    raw = http_get("https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json")
    stix = json.loads(raw)
    objs = stix.get("objects", [])
    techs_all = [o for o in objs
                 if o.get("type") == "attack-pattern"
                 and not o.get("revoked")
                 and not o.get("x_mitre_deprecated")]
    techs = [t for t in techs_all if not t.get("x_mitre_is_subtechnique")]

    def attack_id_of(obj):
        return next((r.get("external_id") for r in obj.get("external_references", [])
                     if r.get("source_name") == "mitre-attack"), None)

    # Trim every technique into a small record for portal queries
    portal_techs = {}
    for t in techs_all:
        aid = attack_id_of(t)
        if not aid:
            continue
        portal_techs[aid] = {
            "name": t.get("name"),
            "description": (t.get("description") or "").split("\n\n")[0][:600],
            "tactics": [p["phase_name"] for p in t.get("kill_chain_phases", [])],
            "platforms": t.get("x_mitre_platforms", []),
            "is_subtechnique": t.get("x_mitre_is_subtechnique", False),
            "url": f"https://attack.mitre.org/techniques/{aid.replace('.', '/')}",
        }
    write_portal("attack.json", {"by_id": portal_techs, "total": len(portal_techs)})

    # Pick deterministically based on day-of-year
    day = datetime.datetime.utcnow().timetuple().tm_yday
    pick = techs[day % len(techs)]
    attack_id = attack_id_of(pick)
    return {
        "total_techniques": len(techs),
        "technique": {
            "id": attack_id,
            "name": pick.get("name"),
            "description": (pick.get("description") or "").split("\n\n")[0][:800],
            "tactics": [p["phase_name"] for p in pick.get("kill_chain_phases", [])],
            "platforms": pick.get("x_mitre_platforms", []),
            "url": f"https://attack.mitre.org/techniques/{attack_id.replace('.', '/')}" if attack_id else None,
        },
    }


def fetch_urlhaus_recent() -> dict:
    """Most recent malicious URLs from URLhaus."""
    raw = http_get("https://urlhaus.abuse.ch/downloads/csv_recent/")
    # File is plain CSV (not zip) at this endpoint
    text = raw.decode("utf-8", errors="replace")
    # Skip comments
    rows = []
    reader = csv.reader([ln for ln in text.splitlines() if ln and not ln.startswith("#")])
    for r in reader:
        if len(r) >= 8:
            rows.append({
                "id": r[0],
                "date_added": r[1],
                "url": r[2],
                "url_status": r[3],
                "threat": r[5],
                "tags": r[6],
                "host": r[7] if len(r) > 7 else None,
            })
    # Portal: index by host for fast IP/domain lookup
    by_host: dict[str, list] = {}
    for r in rows:
        h = (r.get("host") or "").strip()
        if not h:
            continue
        by_host.setdefault(h, []).append({
            "url": r["url"], "threat": r["threat"], "status": r["url_status"],
            "date_added": r["date_added"], "tags": r["tags"],
        })
    write_portal("urlhaus.json", {"by_host": by_host, "total": len(rows)})
    return {
        "total_recent": len(rows),
        "recent": rows[:15],
    }


def fetch_threatfox() -> dict:
    """abuse.ch ThreatFox IoC feed — IPs, domains, hashes, URLs with attribution."""
    raw = http_get("https://threatfox.abuse.ch/export/csv/recent/")
    text = raw.decode("utf-8", errors="replace")
    # Strip leading """ wrapped values
    rows = []
    reader = csv.reader([ln for ln in text.splitlines() if ln and not ln.startswith("#")],
                        quotechar='"')
    for r in reader:
        if len(r) >= 8:
            rows.append({
                "first_seen": r[1].strip(' "'),
                "ioc": r[2].strip(' "'),
                "ioc_type": r[3].strip(' "'),
                "threat_type": r[4].strip(' "'),
                "malware": r[5].strip(' "'),
                "malware_alias": r[6].strip(' "'),
                "malware_printable": r[7].strip(' "'),
                "confidence": r[10].strip(' "') if len(r) > 10 else None,
            })
    # Index by IoC value
    by_ioc = {}
    for r in rows:
        by_ioc[r["ioc"]] = {
            "type": r["ioc_type"],
            "threat": r["threat_type"],
            "malware": r["malware_printable"] or r["malware"],
            "first_seen": r["first_seen"],
            "confidence": r["confidence"],
        }
    write_portal("threatfox.json", {"by_ioc": by_ioc, "total": len(rows)})
    return {
        "total": len(rows),
        "recent": rows[:12],
    }


def fetch_feodo() -> dict:
    """Feodo Tracker active C2 IP list."""
    raw = http_get("https://feodotracker.abuse.ch/downloads/ipblocklist.csv")
    text = raw.decode("utf-8", errors="replace")
    rows = []
    reader = csv.reader([ln for ln in text.splitlines() if ln and not ln.startswith("#")])
    for r in reader:
        if len(r) >= 5:
            rows.append({
                "first_seen": r[0],
                "ip": r[1],
                "port": r[2],
                "last_online": r[3],
                "malware": r[4],
            })
    # Family counts
    family_counts: dict[str, int] = {}
    for r in rows:
        family_counts[r["malware"]] = family_counts.get(r["malware"], 0) + 1
    top_families = sorted(family_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    # Portal: index by IP for IoC lookup
    by_ip = {r["ip"]: {"port": r["port"], "malware": r["malware"], "first_seen": r["first_seen"], "last_online": r["last_online"]} for r in rows}
    write_portal("feodo.json", {"by_ip": by_ip, "total": len(rows)})
    return {
        "total_c2_active": len(rows),
        "by_family": [{"family": f, "count": c} for f, c in top_families],
        "recent": rows[:10],
    }


def fetch_tor_exits() -> dict:
    """Current Tor exit relay count + a few sample IPs."""
    raw = http_get("https://check.torproject.org/torbulkexitlist")
    ips = [ln.strip() for ln in raw.decode("utf-8", errors="replace").splitlines() if ln.strip()]
    # Portal: full set for IP lookup
    write_portal("tor-exits.json", {"ips": ips, "total": len(ips)})
    return {
        "total_exits": len(ips),
        "sample": ips[:10],
    }


def fetch_dshield_top() -> dict:
    """Top attacker IPs across DShield (SANS ISC) honeypot mesh."""
    raw = http_get("https://isc.sans.edu/api/sources/attacks/100/?json")
    d = json.loads(raw)
    # API returns array of dicts
    entries = d if isinstance(d, list) else d.get("sources", [])
    top = []
    for e in entries:
        top.append({
            "ip": e.get("ip"),
            "attacks": int(e.get("attacks") or 0),
            "targets": int(e.get("targets") or 0),
            "first_seen": e.get("firstseen"),
            "last_seen": e.get("lastseen"),
        })
    # Portal: keep all 100 indexed by IP for lookup
    by_ip = {t["ip"]: t for t in top if t["ip"]}
    write_portal("dshield.json", {"by_ip": by_ip, "total": len(top)})
    return {"top": top[:15]}


def fetch_dataplane_ssh() -> dict:
    """DataPlane.org SSH brute-force sources (last hour)."""
    raw = http_get("https://dataplane.org/sshclient.txt")
    lines = [ln for ln in raw.decode("utf-8", errors="replace").splitlines() if ln and not ln.startswith("#")]
    # Format is tab-separated: ASN | ASname | IP | lastseen | category
    rows = []
    for ln in lines:
        parts = ln.split("|")
        if len(parts) >= 5:
            rows.append({
                "asn": parts[0].strip(),
                "as_name": parts[1].strip(),
                "ip": parts[2].strip(),
                "last_seen": parts[3].strip(),
                "category": parts[4].strip(),
            })
    # Portal: index by IP
    by_ip = {r["ip"]: {"asn": r["asn"], "as_name": r["as_name"], "last_seen": r["last_seen"], "category": r["category"]} for r in rows}
    write_portal("dataplane-ssh.json", {"by_ip": by_ip, "total": len(rows)})
    return {
        "total": len(rows),
        "recent": rows[:15],
    }


def fetch_spamhaus_drop() -> dict:
    """Spamhaus DROP — hijacked netblocks."""
    raw = http_get("https://www.spamhaus.org/drop/drop.txt")
    cidrs = []
    for ln in raw.decode("utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith(";"):
            continue
        # Format: "1.2.3.0/24 ; SBL12345"
        parts = ln.split(";")
        cidr = parts[0].strip()
        sbl = parts[1].strip() if len(parts) > 1 else ""
        cidrs.append({"cidr": cidr, "sbl": sbl})
    # Portal: full set for CIDR lookup
    write_portal("spamhaus-drop.json", {"cidrs": cidrs, "total": len(cidrs)})
    return {
        "total_cidrs": len(cidrs),
        "sample": cidrs[:10],
    }


def fetch_hibp_breaches() -> dict:
    """HIBP — verified breaches metadata."""
    raw = http_get(
        "https://haveibeenpwned.com/api/v3/breaches",
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    d = json.loads(raw)
    # Sort by breach date, newest first
    d.sort(key=lambda b: b.get("BreachDate", ""), reverse=True)
    total = len(d)
    total_records = sum(b.get("PwnCount", 0) for b in d)
    recent = []
    for b in d[:8]:
        recent.append({
            "name": b.get("Name"),
            "title": b.get("Title"),
            "domain": b.get("Domain"),
            "breach_date": b.get("BreachDate"),
            "added_date": b.get("AddedDate"),
            "pwn_count": b.get("PwnCount"),
            "data_classes": b.get("DataClasses", []),
            "verified": b.get("IsVerified"),
        })
    # Portal: index by lowercased domain for breach-by-domain lookup
    by_domain: dict[str, list] = {}
    for b in d:
        dom = (b.get("Domain") or "").strip().lower()
        if not dom:
            continue
        by_domain.setdefault(dom, []).append({
            "name": b.get("Name"),
            "title": b.get("Title"),
            "breach_date": b.get("BreachDate"),
            "pwn_count": b.get("PwnCount"),
            "data_classes": b.get("DataClasses", []),
            "verified": b.get("IsVerified"),
        })
    write_portal("hibp.json", {"by_domain": by_domain, "total_breaches": total, "total_records": total_records})
    return {
        "total_breaches": total,
        "total_records_exposed": total_records,
        "recent": recent,
    }


def fetch_sslbl() -> dict:
    """abuse.ch SSL Blacklist — malicious TLS cert fingerprints."""
    raw = http_get("https://sslbl.abuse.ch/blacklist/sslblacklist.csv")
    text = raw.decode("utf-8", errors="replace")
    rows = []
    reader = csv.reader([ln for ln in text.splitlines() if ln and not ln.startswith("#")])
    for r in reader:
        if len(r) >= 3:
            rows.append({
                "listing_date": r[0],
                "sha1": r[1],
                "listing_reason": r[2],
            })
    # Reason counts
    reason_counts: dict[str, int] = {}
    for r in rows:
        reason_counts[r["listing_reason"]] = reason_counts.get(r["listing_reason"], 0) + 1
    top_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    # Portal: index by SHA-1
    by_sha1 = {r["sha1"]: {"listing_date": r["listing_date"], "reason": r["listing_reason"]} for r in rows if r.get("sha1")}
    write_portal("sslbl.json", {"by_sha1": by_sha1, "total": len(rows)})
    return {
        "total_listings": len(rows),
        "by_reason": [{"reason": k, "count": v} for k, v in top_reasons],
        "recent": rows[:10],
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

FEEDS = {
    "kev":            fetch_cisa_kev,
    "epss-top":       fetch_epss_top,
    "attack-spotlight": fetch_mitre_technique_of_day,
    "urlhaus":        fetch_urlhaus_recent,
    "threatfox":      fetch_threatfox,
    "feodo":          fetch_feodo,
    "tor":            fetch_tor_exits,
    "dshield":        fetch_dshield_top,
    "dataplane-ssh":  fetch_dataplane_ssh,
    "spamhaus-drop":  fetch_spamhaus_drop,
    "hibp":           fetch_hibp_breaches,
    "sslbl":          fetch_sslbl,
}


def main() -> int:
    started = datetime.datetime.utcnow().replace(microsecond=0)
    status: dict[str, dict] = {}

    for key, fn in FEEDS.items():
        t0 = time.time()
        try:
            payload = fn()
            (DATA / f"{key}.json").write_text(json.dumps(payload, indent=2) + "\n")
            status[key] = {"ok": True, "elapsed_ms": int((time.time() - t0) * 1000)}
            print(f"  ok   {key:<18} {status[key]['elapsed_ms']:>6} ms")
        except Exception as e:  # noqa: BLE001
            status[key] = {"ok": False, "error": f"{type(e).__name__}: {e}", "elapsed_ms": int((time.time() - t0) * 1000)}
            print(f"  FAIL {key:<18} {status[key]['error']}", file=sys.stderr)

    finished = datetime.datetime.utcnow().replace(microsecond=0)
    meta = {
        "started_at": started.isoformat() + "Z",
        "finished_at": finished.isoformat() + "Z",
        "feeds": status,
        "feed_count": len(FEEDS),
        "ok_count": sum(1 for v in status.values() if v.get("ok")),
    }
    (DATA / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    print(f"\n{meta['ok_count']}/{meta['feed_count']} feeds refreshed in "
          f"{(finished - started).total_seconds():.1f}s")
    # Always exit 0 so CI commits whatever partial data we got — old data is
    # better than no data, and meta.json shows which feeds failed.
    return 0


if __name__ == "__main__":
    sys.exit(main())
