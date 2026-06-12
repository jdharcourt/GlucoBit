#!/usr/bin/env python3
"""
patch_review_bot.py — extract a reviewer's comments from the public Patch
review dashboard (https://reviews.joinpatch.org/dashboard).

Give it a reviewer name and it fetches that reviewer's public dashboard page,
parses every review they submitted, and prints (or saves) the applicant,
county, recommendation, comment text and date.

Usage:
    python3 patch_review_bot.py "Sanat Thukral"
    python3 patch_review_bot.py Lucy            # fuzzy match against leaderboard
    python3 patch_review_bot.py --list          # list all reviewers
    python3 patch_review_bot.py "Ava" --json out.json
    python3 patch_review_bot.py "Ava" --csv out.csv

Only depends on the standard library.
"""

import argparse
import csv
import json
import re
import sys
import urllib.parse
import urllib.request

BASE = "https://reviews.joinpatch.org"
DASHBOARD = f"{BASE}/dashboard"
UA = "Mozilla/5.0 (patch-review-bot)"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def decode_rsc(html: str) -> str:
    """Reassemble the Next.js RSC stream from the self.__next_f.push() chunks.

    Each chunk looks like  self.__next_f.push([1,"<json-escaped text>"])  so we
    JSON-decode the string literal to recover real quotes/newlines, then join.
    """
    pieces = []
    for m in re.finditer(r'self\.__next_f\.push\(\[\d+,\s*("(?:\\.|[^"\\])*")\s*\]\)', html):
        try:
            pieces.append(json.loads(m.group(1)))
        except json.JSONDecodeError:
            pass
    return "".join(pieces)


def get_reviewers() -> list[str]:
    """Return the list of reviewer names from the leaderboard."""
    text = decode_rsc(fetch(DASHBOARD))
    names = re.findall(r'"href":"/dashboard/([^"]+)"', text)
    seen, out = set(), []
    for n in names:
        name = urllib.parse.unquote(n)
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def resolve_name(query: str, reviewers: list[str]) -> str | None:
    """Exact (case-insensitive) match first, then unique substring match."""
    for r in reviewers:
        if r.lower() == query.lower():
            return r
    hits = [r for r in reviewers if query.lower() in r.lower()]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        print(f"Ambiguous name '{query}', matches: {', '.join(hits)}", file=sys.stderr)
    return None


# One review row in the RSC payload is a "tr" whose cells, in order, are:
#   applicant (link) | county | recommendation | comment | date
ROW_RE = re.compile(
    r'"href":"/review/[^"]+","className":"[^"]*violet[^"]*","children":"(?P<applicant>(?:\\.|[^"\\])*)"'
    r'.*?text-muted-foreground","children":"(?P<county>(?:\\.|[^"\\])*)"'
    r'.*?font-medium","children":"(?P<rec>(?:\\.|[^"\\])*)"'
    r'.*?line-clamp-2","children":"(?P<comment>(?:\\.|[^"\\])*)"'
    r'.*?whitespace-nowrap","children":"(?P<date>(?:\\.|[^"\\])*)"',
    re.DOTALL,
)


def unescape(s: str) -> str:
    try:
        return json.loads(f'"{s}"')
    except json.JSONDecodeError:
        return s.encode().decode("unicode_escape", "replace")


def get_reviews(reviewer: str) -> list[dict]:
    url = f"{DASHBOARD}/{urllib.parse.quote(reviewer)}"
    text = decode_rsc(fetch(url))
    rows = []
    for m in ROW_RE.finditer(text):
        rows.append({
            "applicant": unescape(m.group("applicant")).strip(),
            "county": unescape(m.group("county")).strip(),
            "recommendation": unescape(m.group("rec")).strip(),
            "comment": unescape(m.group("comment")).strip(),
            "date": unescape(m.group("date")).strip(),
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract a reviewer's comments from the Patch dashboard.")
    ap.add_argument("name", nargs="?", help="reviewer name (exact or substring)")
    ap.add_argument("--list", action="store_true", help="list all reviewers and exit")
    ap.add_argument("--json", metavar="FILE", help="write results to a JSON file")
    ap.add_argument("--csv", metavar="FILE", help="write results to a CSV file")
    args = ap.parse_args()

    reviewers = get_reviewers()

    if args.list or not args.name:
        print("Reviewers:")
        for r in reviewers:
            print(f"  - {r}")
        return 0

    name = resolve_name(args.name, reviewers)
    if not name:
        print(f"No reviewer matched '{args.name}'. Use --list to see all names.", file=sys.stderr)
        return 1

    reviews = get_reviews(name)
    print(f"{name}: {len(reviews)} reviews\n")
    for i, r in enumerate(reviews, 1):
        print(f"[{i}] {r['applicant']} ({r['county']}) — {r['recommendation']}  {r['date']}")
        print(f"    {r['comment'] or '(no comment)'}\n")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"reviewer": name, "reviews": reviews}, f, indent=2, ensure_ascii=False)
        print(f"Wrote {len(reviews)} reviews to {args.json}")
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["applicant", "county", "recommendation", "comment", "date"])
            w.writeheader()
            w.writerows(reviews)
        print(f"Wrote {len(reviews)} reviews to {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
