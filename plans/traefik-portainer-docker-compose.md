# Plan: Traefik & Portainer Docker Compose Stack

**Created**: 2026-04-16
**Branch**: main (to be initialized)
**Status**: approved
**Spec**: `docs/specs/traefik-portainer-docker-compose.md`

## Goal

Create a production-ready Docker Compose stack that runs Traefik as a reverse proxy with automatic Let's Encrypt SSL for `example.com`, and Portainer as an internal-only container management UI. The setup must be self-contained with persistent data, separated configuration directories, and allow future services to opt into Traefik routing via Docker labels.

## Acceptance Criteria

- [ ] AC-1: `docker compose up -d` starts both services without errors
- [ ] AC-2: Traefik obtains a valid Let's Encrypt certificate (`acme.json` non-empty)
- [ ] AC-3: HTTP-to-HTTPS redirect works (port 80 -> 301 -> port 443)
- [ ] AC-4: Traefik dashboard bound to `127.0.0.1:8080` only
- [ ] AC-5: Portainer bound to `127.0.0.1:9443` only, no Traefik route
- [ ] AC-6: Data persists across `docker compose down && docker compose up -d`
- [ ] AC-7: Test service with Traefik labels on `proxy` network is routable via HTTPS
- [ ] AC-8: Service without labels or not on `proxy` network is not routed
- [ ] AC-9: Docker socket mounted read-only

## User-Facing Behavior

```gherkin
Feature: Traefik reverse proxy with Let's Encrypt SSL

  Background:
    Given the Docker Compose stack is running
    And Traefik is connected to the "proxy" Docker network

  Scenario: Traefik obtains SSL certificate from Let's Encrypt
    When Traefik starts for the first time
    Then it registers with Let's Encrypt using "admin@example.com"
    And it stores the ACME certificate data in "traefik/acme.json"
    And the certificate data persists across container restarts

  Scenario: HTTP requests are redirected to HTTPS
    When a client sends an HTTP request to port 80
    Then the client receives a 301 redirect to the HTTPS URL on port 443

  Scenario: HTTPS traffic is terminated by Traefik
    Given a service is running with Traefik labels for "app.example.com"
    When a client sends an HTTPS request to "app.example.com"
    Then Traefik terminates TLS and forwards the request to the service

  Scenario: Service opts into Traefik routing via Docker labels
    Given a new service is deployed through Portainer
    And the service has Traefik enable, router, and entrypoint labels
    And the service is on the "proxy" network
    When Traefik detects the new container
    Then it creates a route for the service based on its labels

  Scenario: Traefik dashboard is not publicly accessible
    When a client sends a request to the Traefik dashboard from the internet
    Then the request is refused
    But the dashboard is accessible from the Docker host internally

  Scenario: Portainer is not publicly accessible
    Given Portainer is running
    Then Portainer is not routed through Traefik
    And Portainer is only accessible on the Docker host's internal network

  Scenario: Data persists across restarts
    Given the stack has been running and accumulating state
    When the stack is stopped and started again
    Then Traefik's ACME certificates are still present
    And Portainer's database and configuration are intact

  Scenario: Service without Traefik labels is not routed
    Given a service is running without Traefik Docker labels
    Then Traefik does not create a route for that service

  Scenario: Service not on the proxy network is not discovered
    Given a service has Traefik labels but is not on the "proxy" network
    Then Traefik does not route traffic to that service
```

## Steps

### Step 1: Create setup script for prerequisites

**Complexity**: standard
**RED**: Verify `proxy` network, `traefik/acme.json`, and `portainer/data/` do not exist — stack cannot start without them
**GREEN**: Create `setup.sh` with pre-flight checks and prerequisite creation:
- Verify Docker is installed and running (exit with clear error if not)
- Verify ports 80 and 443 are not already in use (warn if bound)
- Create the `proxy` Docker network if it doesn't exist
- Create `traefik/` directory and `traefik/acme.json` with mode 600 if it doesn't exist
- Create `portainer/data/` directory if it doesn't exist
- Print summary of what was created/verified
**REFACTOR**: None needed
**Files**: `setup.sh`
**Commit**: `add setup script with pre-flight checks and prerequisite creation`

### Step 2: Create Traefik static configuration

**Complexity**: standard
**RED**: Verify `traefik/traefik.yml` does not exist
**GREEN**: Create `traefik/traefik.yml` with:
- Entrypoints: `web` (port 80), `websecure` (port 443)
- HTTP-to-HTTPS redirect on the `web` entrypoint
- ACME/Let's Encrypt certificate resolver: HTTP-01 challenge, email `admin@example.com`, storage `/etc/traefik/acme.json`
- Let's Encrypt staging CA URL commented out with instructions to switch for testing
- Docker provider enabled with `exposedByDefault: false`
- API/dashboard enabled
- Log level `INFO`
**REFACTOR**: None needed
**Files**: `traefik/traefik.yml`
**Commit**: `add traefik static configuration with Let's Encrypt and entrypoints`

### Step 3: Create Docker Compose with both services

**Complexity**: standard
**RED**: Run `docker compose config` — fails because `docker-compose.yml` does not exist
**GREEN**: Create `docker-compose.yml` with both services:

**Traefik service:**
- Image: `traefik:v3.4`
- Ports: `0.0.0.0:80:80`, `0.0.0.0:443:443` (public), `127.0.0.1:8080:8080` (dashboard, internal only)
- Volumes: `/var/run/docker.sock:/var/run/docker.sock:ro`, `./traefik/traefik.yml:/etc/traefik/traefik.yml:ro`, `./traefik/acme.json:/etc/traefik/acme.json`
- Networks: `proxy`
- Labels: `traefik.enable=false`
- Restart: `unless-stopped`

**Portainer service:**
- Image: `portainer/portainer-ce:lts`
- Ports: `127.0.0.1:9443:9443` (internal only)
- Volumes: `/var/run/docker.sock:/var/run/docker.sock`, `./portainer/data:/data`
- Networks: `proxy`
- Labels: `traefik.enable=false`
- Restart: `unless-stopped`

**Network:**
- `proxy`: external, pre-created via `setup.sh`

**REFACTOR**: Verify `docker compose config` parses without errors; verify all port bindings, mount paths, and network references match the spec
**Files**: `docker-compose.yml`
**Commit**: `add docker compose with traefik and portainer services`

### Step 4: Add README with setup, troubleshooting, and service example

**Complexity**: standard
**RED**: No operator documentation exists — operator has no guidance for setup, troubleshooting, or adding services
**GREEN**: Create `README.md` covering:
- **Prerequisites**: DNS, firewall, Docker
- **Quick start**: `./setup.sh && docker compose up -d`
- **Adding a new service**: complete example showing required Traefik labels and `proxy` network attachment for a sample `whoami` service
- **Troubleshooting**: how to check Traefik logs, verify certificate status, diagnose DNS/ACME failures, reset ACME state, switch to Let's Encrypt staging server
- **Portainer first login**: note about the admin password timeout window on initial access
- **Architecture overview**: which config lives where (static in `traefik.yml`, dynamic via Docker labels)
**REFACTOR**: None needed
**Files**: `README.md`
**Commit**: `add README with setup, troubleshooting, and service example`

## Complexity Classification

| Rating | Criteria | Review depth |
|--------|----------|--------------|
| `trivial` | Single-file rename, config change, typo fix, documentation-only | Skip inline review; covered by final `/code-review` |
| `standard` | New function, test, module, or behavioral change within existing patterns | Spec-compliance + relevant quality agents |
| `complex` | Architectural change, security-sensitive, cross-cutting concern, new abstraction | Full agent suite including opus-tier agents |

## Pre-PR Quality Gate

- [ ] `docker compose config` parses without errors
- [ ] All containers start and reach healthy/running state
- [ ] Port bindings verified (127.0.0.1 for internal services, 0.0.0.0 for public)
- [ ] `/code-review` passes
- [ ] README covers setup, troubleshooting, and adding-a-service example

## Risks & Open Questions

- **DNS dependency**: AC-2 and AC-3 can only be fully verified on the target host where `example.com` DNS resolves. Local validation is limited to `docker compose config` parsing.
- **Let's Encrypt rate limits**: Use the staging CA URL (`https://acme-staging-v02.api.letsencrypt.org/directory`) during iterative testing. The `traefik.yml` includes the staging URL as a commented-out option.
- **Docker socket security**: Mounting the Docker socket (even read-only) gives Traefik visibility into all containers. This is an accepted trade-off for Docker label-based routing. A future hardening step would be a Docker socket proxy (e.g., `tecnativa/docker-socket-proxy`).
- **Portainer network exposure**: Portainer is on the `proxy` network with `traefik.enable=false`. Misconfiguration of this label would expose Portainer through Traefik. The README documents this risk.
- **Portainer first-login timeout**: Portainer requires setting an admin password within a timeout window on first access. The README documents this.

## Plan Review Summary

All four review personas approved the plan (after one revision cycle for UX and Design blockers).

**Resolved blockers (revision 1):**
- Setup script now includes pre-flight checks (Docker running, port availability) with clear error messages
- DNS failure mode documented in README troubleshooting section; staging CA URL included in traefik.yml
- Rollback/troubleshooting guidance added to README (logs, cert status, ACME reset, staging switch)
- Service-addition example with full Traefik labels included in README
- Port bindings made explicit: `0.0.0.0` for public ports, `127.0.0.1` for internal
- Step ordering fixed: setup.sh (Step 1) runs before compose file creation (Step 3)

**Warnings retained (non-blocking):**
- Portainer on `proxy` network relies on `traefik.enable=false` label as sole guard — documented as risk
- No container healthchecks defined — acceptable for initial deployment, consider adding later
- Docker socket proxy (e.g., `tecnativa/docker-socket-proxy`) recommended as future hardening step
- Let's Encrypt staging server should be used during iterative testing to avoid rate limits
- Portainer admin password timeout on first access — documented in README

| Reviewer | Verdict |
|----------|---------|
| Acceptance Test Critic | approve |
| Design & Architecture Critic | approve |
| UX Critic | approve (after revision) |
| Strategic Critic | approve |
