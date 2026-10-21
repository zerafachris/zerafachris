"""Generate a compact "Most Used Languages" SVG card for the profile README.

Sums language bytes across the user's own (non-fork) repositories via the
GitHub GraphQL API and writes a github_dark-styled card, so the README no longer
depends on an external stats service.

Usage: GITHUB_TOKEN=... python scripts/top_langs.py <username> <output.svg>
"""

import json
import os
import sys
import urllib.request
from collections import defaultdict
from html import escape

LANGS_COUNT = 8
EXCLUDE = set()  # language names to hide from the card, e.g. {"HTML", "CSS"}

QUERY = """
query($login: String!, $cursor: String) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch_languages(login, token):
    sizes, colors, cursor = defaultdict(int), {}, None
    while True:
        body = json.dumps({"query": QUERY, "variables": {"login": login, "cursor": cursor}}).encode()
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=body,
            headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            payload = json.load(resp)
        if "errors" in payload:
            sys.exit(f"GraphQL error: {payload['errors']}")
        repos = payload["data"]["user"]["repositories"]
        for repo in repos["nodes"]:
            for edge in repo["languages"]["edges"]:
                name = edge["node"]["name"]
                sizes[name] += edge["size"]
                colors[name] = edge["node"]["color"] or "#858585"
        if not repos["pageInfo"]["hasNextPage"]:
            return sizes, colors
        cursor = repos["pageInfo"]["endCursor"]


def render(sizes, colors):
    top = sorted(((n, s) for n, s in sizes.items() if n not in EXCLUDE), key=lambda x: -x[1])[:LANGS_COUNT]
    total = sum(s for _, s in top)
    width, bar_w, x0 = 300, 250, 25
    rows = (len(top) + 1) // 2
    height = 90 + rows * 25

    bar, offset = [], 0.0
    for name, size in top:
        w = bar_w * size / total
        bar.append(f'<rect x="{offset:.2f}" y="0" width="{w:.2f}" height="8" fill="{colors[name]}"/>')
        offset += w

    labels = []
    for i, (name, size) in enumerate(top):
        x = 0 if i % 2 == 0 else 150
        y = (i // 2) * 25
        labels.append(
            f'<g transform="translate({x}, {y})">'
            f'<circle cx="5" cy="6" r="5" fill="{colors[name]}"/>'
            f'<text x="15" y="10" class="lang">{escape(name)} {100 * size / total:.2f}%</text></g>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">
  <title id="title">Most Used Languages</title>
  <style>
    .header {{ font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif; fill: #58a6ff; }}
    .lang {{ font: 400 11px 'Segoe UI', Ubuntu, Sans-Serif; fill: #c3d1d9; }}
  </style>
  <rect x="0.5" y="0.5" rx="4.5" width="{width - 1}" height="{height - 1}" fill="#0d1117" stroke="#e4e2e2" stroke-opacity="0"/>
  <text x="{x0}" y="35" class="header">Most Used Languages</text>
  <defs><clipPath id="bar"><rect x="0" y="0" width="{bar_w}" height="8" rx="5"/></clipPath></defs>
  <g transform="translate({x0}, 55)" clip-path="url(#bar)">{''.join(bar)}</g>
  <g transform="translate({x0}, 80)">{''.join(labels)}</g>
</svg>
"""


if __name__ == "__main__":
    login, out = sys.argv[1], sys.argv[2]
    sizes, colors = fetch_languages(login, os.environ["GITHUB_TOKEN"])
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as f:
        f.write(render(sizes, colors))
    print(f"Wrote {out} ({len(sizes)} languages found)")
