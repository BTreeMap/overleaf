#!/usr/bin/env python3
"""Generate the CI Dockerfile for the full-TeX-Live edge image.

The edge image ("Build Overleaf Image" workflow) is built from the tip of
upstream overleaf/overleaf's main branch. Upstream's own server-ce/Dockerfile
is the authoritative recipe for turning that source tree into a working
image; this script derives the CI Dockerfile from it by injecting the
scheme-full TeX Live installation step.

Why derive instead of hand-maintaining a copy? The previous approach kept a
frozen, hand-written copy of the upstream Dockerfile inside the workflow.
When upstream migrated from npm (package-lock.json, patches/) to Yarn 4
(yarn.lock, .yarn/, .yarnrc.yml), the frozen copy still referenced paths
that no longer exist in the upstream tree, and every daily edge build
failed at the "failed to calculate checksum ... /patches: not found" step
for weeks. Deriving from upstream's current Dockerfile keeps the install
flow (package manager, corepack bootstrap, PnP env, cache mounts) in sync
automatically.

The script fails loudly if the injection anchor disappears from the
upstream Dockerfile, so future upstream restructures surface as an explicit
error instead of a silently broken build.
"""

import argparse
import sys

# Anchor: the first line of the site-maintenance section in upstream's
# server-ce/Dockerfile. The TeX Live block is injected immediately before it.
ANCHOR = 'ENV SITE_MAINTENANCE_FILE='

TEXLIVE_BLOCK = """\
# ============================================
# FULL TEX LIVE INSTALLATION (AIR-GAPPED)
# ============================================
# Install scheme-full for complete LaTeX package availability
# This ensures the image works offline without needing to download packages
RUN tlmgr install scheme-full \\
&&  tlmgr path add \\
# Clean up tlmgr caches to reduce image size
&&  rm -rf /usr/local/texlive/*/tlpkg/backups/* \\
&&  rm -rf /tmp/*

"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Dockerfile.ci from upstream's server-ce/Dockerfile."
    )
    parser.add_argument(
        "--upstream-dir",
        default="upstream",
        help="Directory holding the upstream overleaf/overleaf checkout.",
    )
    parser.add_argument(
        "--output",
        default="upstream/Dockerfile.ci",
        help="Where to write the generated Dockerfile.",
    )
    args = parser.parse_args()

    src_path = f"{args.upstream_dir}/server-ce/Dockerfile"
    try:
        with open(src_path) as f:
            upstream_dockerfile = f.read()
    except FileNotFoundError:
        print(f"::error::upstream Dockerfile not found at {src_path}", file=sys.stderr)
        return 1

    if ANCHOR not in upstream_dockerfile:
        print(
            "::error::injection anchor "
            f"'{ANCHOR}' not found in {src_path}; "
            "upstream server-ce/Dockerfile has been restructured and the "
            "generator needs updating",
            file=sys.stderr,
        )
        return 1

    generated = upstream_dockerfile.replace(ANCHOR, TEXLIVE_BLOCK + ANCHOR, 1)

    with open(args.output, "w") as f:
        f.write(generated)

    print(f"Generated {args.output} from {src_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
