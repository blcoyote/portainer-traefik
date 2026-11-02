"""Sync the GitHub webhook ranges in traefik/dynamic.yml with https://api.github.com/meta.

Rewrites the lines between '# BEGIN github-hooks' and '# END github-hooks'.
Set META_FILE to read the meta JSON from a file instead of the API (for testing).
"""
import json
import os
import re
import sys
import urllib.request

PATH = "traefik/dynamic.yml"
BLOCK = re.compile(r"(?P<indent>[ \t]*)# BEGIN github-hooks\n(?P<body>.*?)(?P=indent)# END github-hooks\n", re.S)


def fetch_hooks():
    if os.environ.get("META_FILE"):
        with open(os.environ["META_FILE"]) as f:
            meta = json.load(f)
    else:
        req = urllib.request.Request("https://api.github.com/meta", headers={"Accept": "application/vnd.github+json"})
        token = os.environ.get("GH_TOKEN")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=30) as r:
            meta = json.load(r)
    hooks = meta.get("hooks")
    if not hooks:
        sys.exit("api.github.com/meta returned no 'hooks' list; refusing to update")
    return hooks


def main():
    with open(PATH) as f:
        text = f.read()
    m = BLOCK.search(text)
    if not m:
        sys.exit(f"github-hooks markers not found in {PATH}")
    indent = m.group("indent")
    current = re.findall(r"^\s*-\s*(\S+)", m.group("body"), re.M)
    hooks = fetch_hooks()

    if set(current) == set(hooks):
        print("GitHub webhook ranges are up to date:", ", ".join(current))
        return

    added = sorted(set(hooks) - set(current))
    removed = sorted(set(current) - set(hooks))
    print("Added:", ", ".join(added) or "-")
    print("Removed:", ", ".join(removed) or "-")
    body = "".join(f"{indent}- {h}\n" for h in hooks)
    new = f"{indent}# BEGIN github-hooks\n{body}{indent}# END github-hooks\n"
    with open(PATH, "w") as f:
        f.write(text[: m.start()] + new + text[m.end():])

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(f"Added: {', '.join(added) or '-'}\n\nRemoved: {', '.join(removed) or '-'}\n")


if __name__ == "__main__":
    main()
