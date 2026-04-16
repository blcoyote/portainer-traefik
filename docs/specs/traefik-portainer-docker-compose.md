# Spec: Traefik & Portainer Docker Compose Stack

## Intent Description

Provision a Docker Compose infrastructure stack with two services: **Traefik** as a reverse proxy with automatic SSL via Let's Encrypt, and **Portainer** as a container management UI. Traefik terminates TLS for the domain `elcoyote.dk` and its subdomains, automatically obtaining and renewing certificates through the ACME HTTP-01 challenge (Let's Encrypt, registered to `blc@elcoyote.dk`). All HTTP traffic is redirected to HTTPS. Portainer is accessible only on the internal network (not exposed through Traefik). The Traefik dashboard is available internally but not exposed to the public internet. Future services deployed through Portainer can opt into Traefik routing by applying Docker labels. Each service has its own configuration directory. All persistent state (Traefik certificates/ACME data, Portainer database) survives container restarts via bind mounts.

**Prerequisites:**
- Public DNS for `elcoyote.dk` and subdomains must point to the host
- Ports 80 and 443 must be open on the host firewall
- `acme.json` must be pre-created with `touch traefik/acme.json && chmod 600 traefik/acme.json`
- The `proxy` network must be created before first start: `docker network create proxy`

## User-Facing Behavior

```gherkin
Feature: Traefik reverse proxy with Let's Encrypt SSL

  Background:
    Given the Docker Compose stack is running
    And Traefik is connected to the "proxy" Docker network

  Scenario: Traefik obtains SSL certificate from Let's Encrypt
    When Traefik starts for the first time
    Then it registers with Let's Encrypt using "blc@elcoyote.dk"
    And it stores the ACME certificate data in "traefik/acme.json"
    And the certificate data persists across container restarts

  Scenario: HTTP requests are redirected to HTTPS
    When a client sends an HTTP request to port 80
    Then the client receives a 301 redirect to the HTTPS URL on port 443

  Scenario: HTTPS traffic is terminated by Traefik
    Given a service is running with Traefik labels for "app.elcoyote.dk"
    When a client sends an HTTPS request to "app.elcoyote.dk"
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

## Architecture Specification

**Components**

| Component | Image | Role |
|---|---|---|
| Traefik | `traefik:v3.4` | Reverse proxy, TLS termination, ACME client |
| Portainer | `portainer/portainer-ce:lts` | Container management UI |

**Network topology**

- `proxy` — external Docker bridge network shared between Traefik and any service that needs reverse proxying
- Portainer connects to `proxy` only so it can manage containers on that network, but has no Traefik routing labels

**Entrypoints**

| Name | Port | Purpose |
|---|---|---|
| `web` | 80 | HTTP — redirects to `websecure` |
| `websecure` | 443 | HTTPS — TLS termination |

**Traefik dashboard**: Enabled via `--api.insecure=true` on port 8080, bound to `127.0.0.1` only (not published to `0.0.0.0`).

**Certificate storage**: Let's Encrypt ACME data stored in `./traefik/acme.json` (bind mount). File must have mode `600`. Uses HTTP-01 challenge.

**Directory structure**

```
.
├── docker-compose.yml
├── traefik/
│   ├── traefik.yml          # Static configuration
│   └── acme.json            # ACME cert storage (pre-created, chmod 600)
└── portainer/
    └── data/                 # Portainer persistent data
```

**Constraints**
- Traefik uses the Docker provider to discover services via labels
- Traefik's Docker socket is mounted read-only (`/var/run/docker.sock:/var/run/docker.sock:ro`)
- The `proxy` network must be created externally (`docker network create proxy`) so services deployed later through Portainer can join it
- Portainer exposes port 9443 only on `127.0.0.1` for local access
- Traefik log level set to `INFO` by default

**Dependencies**
- Public DNS for `elcoyote.dk` and subdomains must point to the host
- Ports 80 and 443 must be open on the host firewall

## Acceptance Criteria

| # | Criterion | Pass condition |
|---|---|---|
| AC-1 | `docker compose up -d` starts both services without errors | Both containers reach "running" state |
| AC-2 | Traefik obtains a valid Let's Encrypt certificate | `acme.json` is non-empty and contains certificate data |
| AC-3 | HTTP-to-HTTPS redirect works | `curl -I http://elcoyote.dk` returns 301 with `Location: https://...` |
| AC-4 | Traefik dashboard is not publicly accessible | Port 8080 is bound to `127.0.0.1` only |
| AC-5 | Portainer is not publicly accessible | Port 9443 is bound to `127.0.0.1` only; no Traefik route exists for Portainer |
| AC-6 | Data persists across `docker compose down && docker compose up -d` | `acme.json` and `portainer/data/` retain their contents |
| AC-7 | A test service with Traefik labels on the `proxy` network is routable via HTTPS | Deploying a test container with appropriate labels makes it reachable at its subdomain |
| AC-8 | A service without labels or not on `proxy` network is not routed | No Traefik route is created for unlabeled/disconnected services |
| AC-9 | Docker socket is mounted read-only | Traefik cannot write to the Docker socket |

## Consistency Gate

- [x] Intent is unambiguous
- [x] Every behavior has a corresponding BDD scenario
- [x] Architecture constrains without over-engineering
- [x] Terminology consistent across artifacts
- [x] No contradictions between artifacts
