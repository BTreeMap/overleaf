#!/usr/bin/env python3
"""
Docker image mirroring utilities.

This module provides functions for discovering Docker image versions from
upstream registries and determining which versions need to be mirrored.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


def get_dockerhub_tags(image: str) -> list[str]:
    """Fetch all semver tags from Docker Hub for a given image.
    
    Args:
        image: Docker Hub image name (e.g., 'sharelatex/sharelatex')
        
    Returns:
        List of semver version tags sorted by version number
    """
    page = 1
    all_tags: list[str] = []
    semver_pattern = re.compile(r'^[0-9]+\.[0-9]+\.[0-9]+$')
    
    while True:
        url = f"https://hub.docker.com/v2/repositories/{image}/tags?page={page}&page_size=100"
        try:
            with urlopen(url, timeout=30) as response:
                data = json.loads(response.read().decode())
        except (URLError, HTTPError, json.JSONDecodeError):
            break
            
        results = data.get('results', [])
        if not results:
            break
            
        for tag_info in results:
            tag = tag_info.get('name', '')
            if semver_pattern.match(tag):
                all_tags.append(tag)
                
        if data.get('next') is None:
            break
            
        page += 1
    
    return sorted(set(all_tags), key=lambda v: [int(x) for x in v.split('.')])


def check_ghcr_tag_exists(image: str, tag: str) -> bool:
    """Check if a tag exists in GHCR."""
    result = subprocess.run(
        ['docker', 'buildx', 'imagetools', 'inspect', f'ghcr.io/{image}:{tag}'],
        capture_output=True,
        timeout=60
    )
    return result.returncode == 0


def filter_versions_binary_search(
    versions: list[str], 
    variant: str, 
    image: str,
    force_full_sync: bool = False
) -> list[str]:
    """Filter versions using binary search to find those needing mirroring."""
    if not versions:
        return []
        
    if force_full_sync:
        return versions
    
    count = len(versions)
    left, right = 0, count - 1
    first_missing = count
    
    while left <= right:
        mid = (left + right) // 2
        tag = f"{variant}-{versions[mid]}"
        
        if check_ghcr_tag_exists(image, tag):
            left = mid + 1
        else:
            first_missing = mid
            right = mid - 1
    
    seen: set[str] = set()
    result: list[str] = []
    
    for i in range(first_missing, count):
        version = versions[i]
        if version not in seen:
            result.append(version)
            seen.add(version)
    
    check_start = max(0, first_missing - 5)
    for i in range(check_start, first_missing):
        version = versions[i]
        tag = f"{variant}-{version}"
        if version not in seen and not check_ghcr_tag_exists(image, tag):
            result.append(version)
            seen.add(version)
    
    return sorted(result, key=lambda v: [int(x) for x in v.split('.')])


def discover_versions(
    variant_filter: str = 'all',
    force_full_sync: bool = False,
    image: str = 'btreemap/overleaf'
) -> dict[str, list[str]]:
    """Discover versions to mirror for each variant."""
    variants = {
        'official': 'sharelatex/sharelatex',
        'full': 'tuetenk0pp/sharelatex-full',
        'cep': 'overleafcep/sharelatex'
    }
    
    result: dict[str, list[str]] = {}
    
    for variant, source_image in variants.items():
        if variant_filter not in ('all', variant):
            result[variant] = []
            continue
            
        print(f"Fetching tags from {source_image}...", file=sys.stderr)
        all_versions = get_dockerhub_tags(source_image)
        
        filtered = filter_versions_binary_search(
            all_versions, variant, image, force_full_sync
        )
        result[variant] = filtered
        print(f"{variant.capitalize()} versions to mirror: {len(filtered)}", file=sys.stderr)
    
    return result


def mirror_image(
    source: str,
    dest: str,
    version: str,
    variant: str,
    placeholder: str
) -> bool:
    """Mirror a Docker image with schema1 fallback to placeholder.
    
    Args:
        source: Source Docker Hub image (e.g., 'sharelatex/sharelatex')
        dest: Destination GHCR image (e.g., 'ghcr.io/btreemap/overleaf')
        version: Version to mirror (e.g., '5.0.1')
        variant: Tag variant prefix (e.g., 'official', 'full', 'cep')
        placeholder: Placeholder image for schema1 manifests
        
    Returns:
        True if successful, False otherwise
    """
    parts = version.split('.')
    major = parts[0]
    major_minor = f"{parts[0]}.{parts[1]}"
    
    source_tag = f"docker.io/{source}:{version}"
    tags = [
        f"{dest}:{variant}-{version}",
        f"{dest}:{variant}-{major_minor}",
        f"{dest}:{variant}-{major}",
    ]
    
    print(f"Mirroring {source_tag} to {dest}...")
    
    # Build command with all tags
    cmd = ['docker', 'buildx', 'imagetools', 'create']
    for tag in tags:
        cmd.extend(['-t', tag])
    cmd.append(source_tag)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        # Check for schema1 manifest error
        if 'schema1' in result.stderr.lower() or 'schema1' in result.stdout.lower():
            print(f"Schema1 manifest detected for {version}, using placeholder image")
            
            # Use placeholder image instead
            cmd = ['docker', 'buildx', 'imagetools', 'create']
            for tag in tags:
                cmd.extend(['-t', tag])
            cmd.append(placeholder)
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Error: {result.stderr}", file=sys.stderr)
                return False
            print(f"Successfully created placeholder for {variant}:{version}")
            return True
        else:
            print(f"Error: {result.stderr}", file=sys.stderr)
            return False
    
    print(f"Successfully mirrored {variant}:{version}")
    return True


def find_latest_ghcr_tag(image: str, variant: str, token: str) -> str | None:
    """Find the latest version tag for a variant in GHCR."""
    try:
        req = Request(
            f"https://ghcr.io/v2/{image}/tags/list",
            headers={'Authorization': f'Bearer {token}'}
        )
        with urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            tags = data.get('tags', [])
    except (URLError, HTTPError, json.JSONDecodeError):
        return None
    
    if not tags:
        return None
    
    semver_pattern = re.compile(rf'^{variant}-([0-9]+\.[0-9]+\.[0-9]+)$')
    versions = []
    for tag in tags:
        match = semver_pattern.match(tag)
        if match:
            versions.append(match.group(1))
    
    if not versions:
        return None
    
    return sorted(versions, key=lambda v: [int(x) for x in v.split('.')])[-1]


def update_latest_tags(image: str, token: str) -> None:
    """Update floating latest tags for all variants."""
    dest = f"ghcr.io/{image}"
    
    for variant in ['official', 'full', 'cep']:
        latest = find_latest_ghcr_tag(image, variant, token)
        if latest:
            print(f"Updating {variant}-latest to point to {variant}-{latest}")
            result = subprocess.run(
                [
                    'docker', 'buildx', 'imagetools', 'create',
                    '-t', f"{dest}:{variant}-latest",
                    '-t', f"{dest}:{variant}",
                    f"{dest}:{variant}-{latest}"
                ],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"Warning: Could not update {variant}-latest: {result.stderr}")
        else:
            print(f"No versions found for {variant}")
    
    print("Latest tags updated successfully!")


def get_latest_upstream_version(source_image: str = 'sharelatex/sharelatex') -> str | None:
    """Get the latest version from upstream Docker registry."""
    tags = get_dockerhub_tags(source_image)
    return tags[-1] if tags else None


def cmd_discover(args: argparse.Namespace) -> None:
    """Handle discover subcommand."""
    versions = discover_versions(
        variant_filter=args.variant,
        force_full_sync=args.force_full_sync,
        image=args.image
    )
    
    if args.output_format == 'json':
        print(json.dumps(versions))
    else:  # github format
        github_output = os.environ.get('GITHUB_OUTPUT', '')
        if github_output:
            with open(github_output, 'a') as f:
                for variant, ver_list in versions.items():
                    f.write(f"{variant}_versions={json.dumps(ver_list)}\n")
        for variant, ver_list in versions.items():
            print(f"{variant.capitalize()}: {json.dumps(ver_list)}")


def cmd_mirror(args: argparse.Namespace) -> None:
    """Handle mirror subcommand."""
    success = mirror_image(
        source=args.source,
        dest=args.dest,
        version=args.version,
        variant=args.variant,
        placeholder=args.placeholder
    )
    if not success:
        sys.exit(1)


def cmd_update_latest(args: argparse.Namespace) -> None:
    """Handle update-latest subcommand."""
    token = os.environ.get('GH_TOKEN', '')
    update_latest_tags(args.image, token)


def cmd_latest(args: argparse.Namespace) -> None:
    """Handle latest subcommand."""
    version = get_latest_upstream_version(args.source)
    if version:
        print(version)
    else:
        sys.exit(1)


def main() -> None:
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(description='Docker image mirroring utilities')
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # discover subcommand
    discover_parser = subparsers.add_parser('discover', help='Discover versions to mirror')
    discover_parser.add_argument('--variant', default='all', 
                                 choices=['all', 'official', 'full', 'cep'])
    discover_parser.add_argument('--force-full-sync', action='store_true')
    discover_parser.add_argument('--image', default='btreemap/overleaf')
    discover_parser.add_argument('--output-format', default='json', choices=['json', 'github'])
    discover_parser.set_defaults(func=cmd_discover)
    
    # mirror subcommand
    mirror_parser = subparsers.add_parser('mirror', help='Mirror a single image version')
    mirror_parser.add_argument('--source', required=True, help='Source Docker Hub image')
    mirror_parser.add_argument('--dest', required=True, help='Destination GHCR image')
    mirror_parser.add_argument('--version', required=True, help='Version to mirror')
    mirror_parser.add_argument('--variant', required=True, help='Tag variant prefix')
    mirror_parser.add_argument('--placeholder', required=True, help='Placeholder image for schema1')
    mirror_parser.set_defaults(func=cmd_mirror)
    
    # update-latest subcommand
    update_latest_parser = subparsers.add_parser('update-latest', help='Update floating latest tags')
    update_latest_parser.add_argument('--image', default='btreemap/overleaf')
    update_latest_parser.set_defaults(func=cmd_update_latest)
    
    # latest subcommand
    latest_parser = subparsers.add_parser('latest', help='Get latest upstream version')
    latest_parser.add_argument('--source', default='sharelatex/sharelatex')
    latest_parser.set_defaults(func=cmd_latest)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
