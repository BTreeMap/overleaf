# Overleaf Docker Image Builder

This repository provides automated CI/CD pipelines to build and publish Docker images for [Overleaf Community Edition](https://github.com/overleaf/overleaf).

> **Note:** This repository does **not** contain any upstream Overleaf source code. All builds dynamically checkout the upstream [overleaf/overleaf](https://github.com/overleaf/overleaf) repository at build time.

## Published Images

Images are published to GitHub Container Registry (GHCR):

- **`ghcr.io/btreemap/overleaf-base`** - Base image with dependencies and TeX Live
- **`ghcr.io/btreemap/overleaf`** - Full Overleaf runtime with TeX Live scheme-full

## Image Tags

### Stable (Recommended for Production)

The **stable** images track upstream [GitHub releases](https://github.com/overleaf/overleaf/releases):

| Tag | Description |
|-----|-------------|
| `:latest` | Latest stable release (points to stable, not edge) |
| `:X.Y.Z` | Specific version (e.g., `:5.1.2`) |
| `:X.Y` | Minor version (e.g., `:5.1`) |
| `:X` | Major version (e.g., `:5`) |
| `:stable-vX.Y.Z` | Explicit stable tag (e.g., `:stable-v5.1.2`) |
| `:stable-sha-<SHA>` | Immutable tag by upstream commit SHA |
| `:YYYY-MM-DD` | Date of build |
| `:YYYY-MM-DD.HH-MM-SS` | Datetime of build |

### Edge (Development/Testing)

The **edge** images track the upstream `main` branch:

| Tag | Description |
|-----|-------------|
| `:edge` | Latest edge build from main |
| `:edge-sha-<SHA>` | Immutable tag by upstream commit SHA |
| `:edge-YYYY-MM-DD` | Date of edge build |
| `:edge-YYYY-MM-DD.HH-MM-SS` | Datetime of edge build |

### Base Image

| Tag | Description |
|-----|-------------|
| `:edge` | Latest base image |
| `:edge-sha-<SHA>` | Immutable tag by upstream commit SHA |
| `:edge-YYYY-MM-DD` | Date of base build |

## Features

### Multi-Architecture Support

All images are built for:
- `linux/amd64`
- `linux/arm64`

### Full TeX Live (Air-Gapped Ready)

The `ghcr.io/btreemap/overleaf` runtime images include **TeX Live scheme-full** pre-installed. This means:

- **Complete LaTeX package availability** - No need to install packages at runtime
- **Air-gapped operation** - Works fully offline without network access to CTAN mirrors
- **Production ready** - All common LaTeX packages are included out of the box

The base image (`overleaf-base`) includes TeX Live scheme-basic. The full TeX Live installation is added in the runtime image build.

## Build Schedule

| Image | Schedule | Description |
|-------|----------|-------------|
| `overleaf-base` | Weekly (Sunday) | Refreshes base dependencies and TeX Live |
| `overleaf` (edge) | Daily | Builds from upstream `main` branch |
| `overleaf` (stable) | Daily + On Release | Builds from upstream releases |

Builds are skipped if the image for that upstream SHA already exists (to avoid redundant work).

## Usage

### Quick Start

```bash
# Pull the latest stable image
docker pull ghcr.io/btreemap/overleaf:latest

# Or use a specific version
docker pull ghcr.io/btreemap/overleaf:5.1.2

# Run Overleaf
docker run -d \
  -p 80:80 \
  -v overleaf-data:/var/lib/overleaf \
  ghcr.io/btreemap/overleaf:latest
```

### Using Edge Images

```bash
# Pull the latest edge image (from main branch)
docker pull ghcr.io/btreemap/overleaf:edge
```

### Docker Compose

```yaml
version: '3'
services:
  overleaf:
    image: ghcr.io/btreemap/overleaf:latest
    ports:
      - "80:80"
    volumes:
      - overleaf-data:/var/lib/overleaf
    environment:
      OVERLEAF_APP_NAME: "My Overleaf"
      
volumes:
  overleaf-data:
```

## How It Works

1. **Detect Upstream State**: Workflows query upstream for the latest `main` SHA and release tag
2. **Check GHCR**: Skip builds if images for those SHAs already exist
3. **Checkout Upstream**: Dynamically checkout `overleaf/overleaf` at the target ref
4. **Build Images**: Multi-arch builds using Docker Buildx with GHA cache
5. **Publish**: Push to GHCR with appropriate tags

## Upstream

This project builds images from the official [Overleaf Community Edition](https://github.com/overleaf/overleaf) repository.

For information about Overleaf itself:
- [Overleaf Wiki](https://github.com/overleaf/overleaf/wiki)
- [Overleaf Toolkit](https://github.com/overleaf/toolkit/)
- [Overleaf Server Pro](https://www.overleaf.com/for/enterprises)

## License

The CI/CD configuration in this repository is provided under the MIT License.

The Docker images built by this repository contain software from [overleaf/overleaf](https://github.com/overleaf/overleaf) which is licensed under the [GNU Affero General Public License v3.0](https://github.com/overleaf/overleaf/blob/main/LICENSE).

When using the built images, you must comply with the AGPL-3.0 license terms of the upstream Overleaf project.
