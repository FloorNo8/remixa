#!/usr/bin/env python3
"""
Commit → Linear join (observability).

For each new commit on `main` whose message contains an `FN8-N` reference, post a comment
on that Linear issue linking the commit. Idempotent: skips a commit it has already joined
(detected by the short SHA already appearing in the issue's comments). Run by the
`linear-commit-join` GitHub Action on push to main, so squash-merges + direct pushes are
both covered — closing the gap where the per-commit→Linear join "stayed silent".

Env:
  LINEAR_API_KEY   Linear personal API key (Authorization header, used verbatim)
  REPO             owner/name (default FloorNo8/remixa)
  COMMITS_BEFORE   github.event.before (the SHA before the push; zeros on a new branch)
  COMMITS_AFTER    github.sha (tip of the push)
"""
import os
import re
import subprocess
import sys

import requests

API = "https://api.linear.app/graphql"
KEY = os.environ.get("LINEAR_API_KEY")
REPO = os.environ.get("REPO", "FloorNo8/remixa")
BEFORE = os.environ.get("COMMITS_BEFORE", "")
AFTER = os.environ.get("COMMITS_AFTER", "HEAD")

ISSUE_Q = """
query($id: String!) {
  issue(id: $id) { id identifier comments(first: 100) { nodes { body } } }
}
"""
COMMENT_M = """
mutation($issueId: String!, $body: String!) {
  commentCreate(input: { issueId: $issueId, body: $body }) { success }
}
"""


def gql(query, variables):
    resp = requests.post(
        API,
        json={"query": query, "variables": variables},
        headers={"Authorization": KEY, "Content-Type": "application/json"},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]


def new_commits():
    """(sha, subject) for the commits introduced by this push (no merges)."""
    if not BEFORE or set(BEFORE) == {"0"}:  # new branch / unknown base → last 20
        rng = ["-20"]
    else:
        rng = [f"{BEFORE}..{AFTER}"]
    out = subprocess.run(
        ["git", "log", "--no-merges", "--pretty=%H%x1f%s", *rng],
        capture_output=True, text=True,
    ).stdout
    rows = []
    for line in out.splitlines():
        if "\x1f" in line:
            sha, subject = line.split("\x1f", 1)
            rows.append((sha, subject))
    return rows


def main():
    if not KEY:
        print("LINEAR_API_KEY not set — skipping", file=sys.stderr)
        return 0
    joined = 0
    for sha, subject in new_commits():
        for ident in sorted(set(re.findall(r"FN8-\d+", subject))):
            try:
                issue = gql(ISSUE_Q, {"id": ident}).get("issue")
                if not issue:
                    print(f"skip {ident}: issue not found")
                    continue
                short = sha[:9]
                already = any(short in (c["body"] or "") for c in issue["comments"]["nodes"])
                if already:
                    print(f"skip {short}→{ident}: already joined")
                    continue
                url = f"https://github.com/{REPO}/commit/{sha}"
                body = f"🔗 commit `{short}` on `main`: {subject}\n{url}"
                gql(COMMENT_M, {"issueId": issue["id"], "body": body})
                print(f"joined {short} → {ident}")
                joined += 1
            except Exception as exc:  # never fail the build over a join
                print(f"error {sha[:9]} {ident}: {exc}", file=sys.stderr)
    print(f"done: {joined} commit→issue join(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
