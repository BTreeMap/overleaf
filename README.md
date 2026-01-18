# Overleaf Docker Image Builder

This repository provides automated CI/CD pipelines to build and publish Docker images for [Overleaf Community Edition](https://github.com/overleaf/overleaf).

> **Note:** This repository does **not** contain any upstream Overleaf source code. All builds dynamically checkout the upstream [overleaf/overleaf](https://github.com/overleaf/overleaf) repository at build time.

## Published Images

Images are published to GitHub Container Registry (GHCR):

- **`ghcr.io/btreemap/overleaf-base`** - Base image with dependencies and TeX Live
- **`ghcr.io/btreemap/overleaf`** - Full Overleaf runtime with TeX Live scheme-full

## Image Tags

### Mirrored Images (Recommended for Production)

We mirror pre-built images from various upstream sources with multiple tags for version pinning:

#### Official (from `sharelatex/sharelatex`)

| Tag | Description |
|-----|-------------|
| `:official` | Latest official release |
| `:official-latest` | Same as `:official` |
| `:official-X.Y.Z` | Specific version (e.g., `:official-5.1.2`) |
| `:official-X.Y` | Minor version (e.g., `:official-5.1`) |
| `:official-X` | Major version (e.g., `:official-5`) |

#### Full (from `tuetenk0pp/sharelatex-full`)

Pre-built images with full TeX Live installation:

| Tag | Description |
|-----|-------------|
| `:full` | Latest full release |
| `:full-latest` | Same as `:full` |
| `:full-X.Y.Z` | Specific version (e.g., `:full-5.1.2`) |
| `:full-X.Y` | Minor version (e.g., `:full-5.1`) |
| `:full-X` | Major version (e.g., `:full-5`) |

#### CEP (from `overleafcep/sharelatex`)

Community Extended Pack with additional features:

| Tag | Description |
|-----|-------------|
| `:cep` | Latest CEP release |
| `:cep-latest` | Same as `:cep` |
| `:cep-X.Y.Z` | Specific version (e.g., `:cep-5.1.2`) |
| `:cep-X.Y` | Minor version (e.g., `:cep-5.1`) |
| `:cep-X` | Major version (e.g., `:cep-5`) |

> CEP tags from Docker Hub may include extension suffixes such as
> `5.5.4-ext-v3.2`. The mirror workflow preserves the full tag while still
> generating major/minor tags from the base `X.Y.Z` portion.

### Edge (Development/Testing)

The **edge** images are built from the upstream `main` branch with full TeX Live:

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

Images are built for:
- `linux/amd64`
- `linux/arm64` (when upstream images provide arm64; workflows skip unsupported platforms to keep builds green)

### Full TeX Live (Air-Gapped Ready)

The `ghcr.io/btreemap/overleaf` edge images include **TeX Live scheme-full** pre-installed. This means:

- **Complete LaTeX package availability** - No need to install packages at runtime
- **Air-gapped operation** - Works fully offline without network access to CTAN mirrors
- **Production ready** - All common LaTeX packages are included out of the box

The base image (`overleaf-base`) includes TeX Live scheme-basic. The full TeX Live installation is added in the runtime image build.

## Build Schedule

| Image | Schedule | Description |
|-------|----------|-------------|
| `overleaf-base` | Weekly (Sunday) | Refreshes base dependencies and TeX Live |
| `overleaf` (edge) | Daily | Builds from upstream `main` branch |
| `overleaf` (mirrored) | Daily | Mirrors from Docker Hub sources |

Builds are skipped if the image for that upstream SHA already exists (to avoid redundant work).

Mirror sync uses a binary search algorithm to efficiently detect which versions need to be mirrored, minimizing API calls.

## Usage

### Quick Start

```bash
# Pull the latest official image (mirrored from sharelatex/sharelatex)
docker pull ghcr.io/btreemap/overleaf:official

# Or use the full variant with complete TeX Live
docker pull ghcr.io/btreemap/overleaf:full

# Or use a specific version
docker pull ghcr.io/btreemap/overleaf:official-5.1.2

# Run Overleaf
docker run -d \
  -p 80:80 \
  -v overleaf-data:/var/lib/overleaf \
  ghcr.io/btreemap/overleaf:official
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
    image: ghcr.io/btreemap/overleaf:official
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

### Edge Builds

1. **Detect Upstream State**: Workflows query upstream for the latest `main` SHA
2. **Check GHCR**: Skip builds if images for those SHAs already exist
3. **Checkout Upstream**: Dynamically checkout `overleaf/overleaf` at the target ref
4. **Build Images**: Multi-arch builds using Docker Buildx with GHA cache
5. **Publish**: Push to GHCR with appropriate tags

### Mirrored Images

1. **Discover Versions**: Fetch all semantic version tags from Docker Hub sources
2. **Binary Search Optimization**: Use binary search to find which versions need mirroring
3. **Mirror**: Use `docker buildx imagetools create` to copy images without rebuilding
4. **Multi-Tag**: Apply multiple tags (X.Y.Z, X.Y, X) for version pinning flexibility

### Base Image Builds

1. **Detect Upstream**: Read the latest upstream `main` SHA and generate timestamps
2. **Weekly Refresh**: Scheduled builds always rebuild to refresh dependencies
3. **GHCR Check**: Push is skipped if the SHA-tagged image already exists
4. **Multi-Arch Build**: Build `linux/amd64` and `linux/arm64` variants in parallel
5. **Manifest Publish**: Merge digests into a multi-arch `edge` manifest

### Full Image Builds

1. **Select Version**: Use the mirror script to find the latest upstream release
2. **Guard Daily Tag**: Skip if today's date tag already exists (unless forced)
3. **Optimized Dockerfile**: Generate a single-layer image with scheme-full TeX Live
4. **Multi-Arch Build**: Build both architectures and publish a manifest list
5. **Tag Output**: Publish `latest`, date, and `<version>-full` tags

### Mirror Script Reference

The `mirror_images.py` CLI powers the mirroring workflow:

- `discover`: Lists versions to mirror, using binary search to limit GHCR checks
- `mirror`: Copies a specific version and tags it as full, minor, and major
- `update-latest`: Updates floating `latest` tags for each variant
- `latest`: Returns the newest upstream version tag from Docker Hub

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
