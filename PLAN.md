# PLAN: MCP Gateway

A gateway that sits between AI agents and the MCP servers they use, so every tool call is authenticated, permission-checked, rate-limited, and logged.

## How a tool call flows

1. The agent connects to the gateway only, over Streamable HTTP.
2. The gateway checks the agent's API key.
3. It checks that this agent is allowed to use this tool.
4. It checks the agent's rate limit.
5. It forwards the call to the right upstream MCP server, with a timeout.
6. It writes an audit record.

## Stack

- Python 3.12, managed with uv
- MCP Python SDK (pinned to one exact version) and FastAPI
- PostgreSQL: agents, API key hashes, upstream servers, policies, audit log
- Redis: rate-limit counters and permission cache
- Docker Compose for local development
- GitHub Actions for CI, GitHub Container Registry for images
- One AWS EC2 instance for the deployed version

## Week 1: gateway core

- [ ] Setup: public repo with MIT license, `.env` in `.gitignore`, secret scanning with push protection, MCP SDK pinned to one version
  - [x] MIT license, `.env` in `.gitignore`, `mcp==2.3.0` pinned (5 Oct)
  - [ ] Repo public, secret scanning with push protection turned on
- [ ] Two upstream MCP servers in Docker: a small notes server (add and search tools) written for this project, and one open-source reference server
  - [x] Notes server (`add_note`, `search_notes`) in Docker, tested with MCP Inspector (5 Oct)
  - [ ] Open-source reference server
- [ ] The gateway: agents connect over Streamable HTTP; the gateway connects to both upstreams, merges their tool lists with a prefix per server (`notes.search`), and routes each tool call to the right upstream
- [ ] PostgreSQL schema for agents, API keys (hashes only), upstream servers, policies, and the audit log, managed with versioned SQL migration files
- [ ] Docker Compose starts everything with one command; tested with MCP Inspector

Design questions: Why prefix tool names by server? What should listing tools return if one upstream is down? Why store only hashes of API keys?

## Week 2: control

- [ ] API-key authentication on every request
- [ ] Per-agent allow and deny rules for each tool, stored in PostgreSQL and cached in Redis, with the cache cleared whenever a rule changes
- [ ] Token-bucket rate limiting per agent and per tool in Redis, made atomic with a Lua script so simultaneous calls cannot slip past the limit
- [ ] An audit row for every call (agent, tool, decision, status, latency), with secrets in arguments redacted and each row storing a hash of the previous row so tampering is detectable
- [ ] Timeouts on every upstream call, so one slow server cannot hang an agent

Design questions: What goes wrong if the rate limiter is not atomic? How do cached permissions stay fresh? What does the hash chain catch, and what can it not protect against?

## Week 3: tests and CI

- [ ] Unit tests for the policy checks and the rate limiter
- [ ] An integration test that starts the Compose stack and makes real MCP calls through the gateway
- [ ] A concurrency test that fires many simultaneous calls at an agent with a small limit and checks that exactly the allowed number succeed
- [ ] GitHub Actions: run all tests on every pull request; on merge to main, build the image for `linux/amd64` and `linux/arm64` with `docker buildx` and push it to GitHub Container Registry

Design questions: Why test the limiter under real concurrency instead of in sequence? What runs on a pull request versus on main? How is a bad image rolled back?

## Week 4: deploy and measure

- [ ] AWS budget alert first, then one free-tier EC2 instance running the Compose stack
- [ ] HTTPS through Caddy with a free DuckDNS subdomain; only port 443 open; secrets in a `.env` file on the server, never in the repo
- [ ] A k6 load test measuring the gateway's added latency (p50 and p95 against calling an upstream directly) and the limiter's accuracy under load
- [ ] README with the architecture diagram, key design decisions, a short threat model, measured numbers, and a demo video
- [ ] A real MCP client connected to the deployed gateway

Design questions: How is the deployment secured? What dominates the gateway's latency? Do rate limits still hold with two gateway copies? (They should, because the counters live in Redis.)

## If behind schedule

Cut in this order: the demo video, then the hash chain (keep a plain audit log), then the Redis permission cache (read rules from PostgreSQL), then the public deployment (demo locally). Never cut the rate limiter, the concurrency test, or CI, and never expose the gateway without HTTPS.

## Rules for this project

- Never commit secrets. If a key leaks, rotate it immediately; deleting the commit is not enough.
- Expose the gateway only over HTTPS, with only port 443 open. SSH by key only, from one IP.
- Treat tool arguments as untrusted input. Demo upstream servers get no access to real files or anything sensitive.
- Pin the MCP SDK version and note the MCP spec version in the README. Upgrade on purpose.
- No admin UI yet; Swagger docs and SQL are enough.
- One feature per commit, with tests.

## Cost

- Set an AWS budget alert of about $1 before launching anything, and check the current free-tier terms and expiry.
- AWS charges hourly for public IPv4 addresses, so stop the instance when not in use. Stopping can change the IP, so keep the DuckDNS record updated.
- Free-tier instances have about 1 GB of memory: use low memory settings and a swap file, and keep Kafka and Kubernetes local.
- Avoid anything billed by the hour: load balancers, NAT gateways, managed Kafka, managed Kubernetes, managed databases beyond the free allowance.

| Need | Free option | Watch out for |
| --- | --- | --- |
| Code hosting and CI | Public GitHub repo and GitHub Actions | Actions minutes are only unlimited for public repos |
| Container registry | GitHub Container Registry | Keep the image public |
| Database and cache | PostgreSQL and Redis in Docker | Nothing, as long as they run in your own containers |
| Hosting | One AWS free-tier EC2 instance | IPv4 charges, 1 GB memory, credits expiring |
| HTTPS and a domain | DuckDNS subdomain with Caddy (Let's Encrypt) | The IP changing after a stop and start |
| Kafka and Kubernetes (later) | Docker and kind on the laptop | Do not run them on the EC2 instance |
| Load testing | k6 from the laptop | Only test your own servers |
| MCP testing | MCP Inspector | Nothing |
| LLM usage | None needed; the gateway never calls an LLM | Nothing |

## Development machine (MacBook M1, 8 GB)

- OrbStack instead of Docker Desktop, with memory capped at about 4 GB.
- Keep at least 15 GB of disk free; run `docker system prune` every week or two.
- The Mac builds ARM images and many EC2 instances are x86, so CI builds both architectures (or deploy to an ARM Graviton instance).
- For Kafka and Kubernetes later, run one at a time, use a single-node Kafka (or Redpanda) and a single-node kind cluster, and stop other containers first.

## Later: Kafka, microservices, and Kubernetes

### Step 1: separate audit service fed by Kafka

- [ ] The gateway publishes audit events to Kafka instead of writing to PostgreSQL on every call
- [ ] A separate audit service consumes the events, stores them, and serves a usage API: calls, denials, and latency per agent and per tool
- [ ] An idempotent consumer keyed by event ID, so a redelivered event is never counted twice
- [ ] A documented, tested decision for when Kafka is down: buffer locally, block tool calls, or drop events and alert
- [ ] Stop the audit service, send traffic, restart it, and show that no events were lost

Design questions: What is gained and risked by moving auditing off the request path? How is double counting avoided with at-least-once delivery? If the audit system cannot record a call, should the gateway still allow it?

### Step 2: Kubernetes

- [ ] Every service on a local kind cluster with Deployments, Services, ConfigMaps, Secrets, health probes, and resource limits
- [ ] Three gateway replicas, with a test showing rate limits still hold across all of them
- [ ] A HorizontalPodAutoscaler on the gateway, scaled under a k6 load test

Design questions: Pod versus Deployment versus Service? Readiness versus liveness probes? Why does keeping state in Redis make scaling the gateway safe?

### Step 3: further

- Replace API keys with OAuth-based authorization, following the MCP authorization specification.
- A small admin page for managing agents and policies.
