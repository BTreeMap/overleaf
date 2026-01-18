# Workflow Helper Scripts

This directory hosts Python helpers invoked by GitHub Actions workflows. Keeping
logic here avoids embedding multi-line scripts in workflow YAML, making workflows
easier to validate and reuse.

## `check_platform_support.py`

Checks whether a Docker manifest list includes a specific platform.

**Interface**

- `--platform`: Target platform in `os/arch` format (for example, `linux/amd64`).
- `--inspect-json`: Path to the JSON file produced by
  `docker buildx imagetools inspect --format '{{json .}}'`.

The script prints `true` or `false` to stdout for consumption by shell steps.

## `mirror_images.py`

Provides CLI commands used by mirroring workflows to discover upstream tags,
mirror images, and update `latest` tags.

## Design Decisions

- Workflow logic that requires Python parsing lives in this folder so that
  workflow YAML remains declarative, easier to lint, and less prone to syntax
  errors.
