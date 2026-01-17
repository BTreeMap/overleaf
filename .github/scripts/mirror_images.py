#!/usr/bin/env python3
"""
Docker image mirroring utilities.

This module provides functions for discovering Docker image versions from
upstream registries and determining which versions need to be mirrored.
"""

import json
import re
import subprocess
import sys
from typing import Optional
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
    """Check if a tag exists in GHCR.
    
    Args:
        image: GHCR image name (e.g., 'btreemap/overleaf')
        tag: Tag to check
        
    Returns:
        True if tag exists, False otherwise
    """
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
    """Filter versions using binary search to find those needing mirroring.
    
    Uses binary search optimization assuming older versions are more likely
    to be already mirrored and newer versions need mirroring.
    
    Args:
        versions: List of version strings sorted by semver
        variant: Variant prefix (e.g., 'official', 'full', 'cep')
        image: GHCR image name
        force_full_sync: If True, return all versions
        
    Returns:
        List of versions that need to be mirrored
    """
    if not versions:
        return []
        
    if force_full_sync:
        return versions
    
    count = len(versions)
    left, right = 0, count - 1
    first_missing = count
    
    # Binary search to find first missing version
    while left <= right:
        mid = (left + right) // 2
        tag = f"{variant}-{versions[mid]}"
        
        if check_ghcr_tag_exists(image, tag):
            left = mid + 1
        else:
            first_missing = mid
            right = mid - 1
    
    # Collect versions from first_missing onwards
    seen: set[str] = set()
    result: list[str] = []
    
    for i in range(first_missing, count):
        version = versions[i]
        if version not in seen:
            result.append(version)
            seen.add(version)
    
    # Check a few versions before the boundary for gaps
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
    """Discover versions to mirror for each variant.
    
    Args:
        variant_filter: Which variant to discover ('all', 'official', 'full', 'cep')
        force_full_sync: If True, return all versions regardless of existing mirrors
        image: GHCR image name
        
    Returns:
        Dictionary mapping variant names to lists of versions to mirror
    """
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


def get_latest_upstream_version(source_image: str = 'sharelatex/sharelatex') -> Optional[str]:
    """Get the latest version from upstream Docker registry.
    
    Args:
        source_image: Docker Hub image name
        
    Returns:
        Latest semver version string or None if not found
    """
    tags = get_dockerhub_tags(source_image)
    return tags[-1] if tags else None


def main():
    """Main entry point for CLI usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Docker image mirroring utilities')
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # discover subcommand
    discover_parser = subparsers.add_parser('discover', help='Discover versions to mirror')
    discover_parser.add_argument('--variant', default='all', 
                                 choices=['all', 'official', 'full', 'cep'])
    discover_parser.add_argument('--force-full-sync', action='store_true')
    discover_parser.add_argument('--image', default='btreemap/overleaf')
    discover_parser.add_argument('--output-format', default='json', choices=['json', 'github'])
    
    # latest subcommand
    latest_parser = subparsers.add_parser('latest', help='Get latest upstream version')
    latest_parser.add_argument('--source', default='sharelatex/sharelatex')
    
    args = parser.parse_args()
    
    if args.command == 'discover':
        versions = discover_versions(
            variant_filter=args.variant,
            force_full_sync=args.force_full_sync,
            image=args.image
        )
        
        if args.output_format == 'json':
            print(json.dumps(versions))
        else:  # github format
            for variant, ver_list in versions.items():
                print(f"{variant}_versions={json.dumps(ver_list)}")
                
    elif args.command == 'latest':
        version = get_latest_upstream_version(args.source)
        if version:
            print(version)
        else:
            sys.exit(1)


if __name__ == '__main__':
    main()
