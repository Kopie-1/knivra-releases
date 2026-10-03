# Build 25 server operations and scaling

## What runs where

- Clients send movement/aim/action intentions; an authoritative Godot process owns actors, damage, inventory, doors, lights, props, timed events and scores. Snapshot format 25 is incompatible with Build 24.
- Each arena process is isolated: unique UDP port, KNIVRA_SERVER_ID, data directory and account credentials. A crashed arena cannot corrupt another arena's world. Matches are 12 minutes (deathmatch/team deathmatch) or 15 minutes (capture the flag), with high score caps.
- The account HTTP API remains separate from gameplay. Build 25 replaces its one-arena matchmaker with a transactional fleet allocator. Only operator-configured endpoints may be advertised. Trusted heartbeats expire after 12 seconds; connection reservations expire after 30 seconds; reconnect leases expire after 60 seconds. A player receives at most one lease. Unknown builds and unconfigured servers are rejected.
- Persistent SQLite WAL allocation records allow allocator restarts and multiple coordinator workers on one host. Account sessions are still in memory and account writes use SQLite with one service lock. The account API is NOT yet a stateless replicated service.

## Existing host installation

Use the packaged server/install-build25.py installer. Run --check first; install with sudo. It verifies every payload checksum, stops the existing services, backs up changed files, installs the arena pack and matchmaker, configures persistent allocation state, restarts services, and checks local account health. Failure restores previous files. It does not change passwords, account records, cosmetics, payment integration, domain routing, or firewall rules.

Backups live under /var/backups/knivra-build25/<timestamp>. Restore the files recorded in files.json (numeric files correspond to the listed destinations), remove newly introduced drop-ins, reload systemd and restart accounts/public services. Preserve the account database. Build 24 remains downloadable and its source is preserved under baseline-build-24.

Current production configuration has ONE arena, with seven public human slots. Installing this release does not purchase or provision a fleet.

## Add independent arena workers

Configure KNIVRA_FLEET_JSON on the account service as an object such as:

```json
{"arena-1":{"address":"game-a.example:27844","capacity":7},"arena-2":{"address":"game-b.example:27844","capacity":7}}
```

Configure each trusted worker with KNIVRA_SERVER_ID matching a key, KNIVRA_GAME_PORT, KNIVRA_ACCOUNTS_URL, KNIVRA_PUBLIC_SERVER=1, and server account credentials/key injected via systemd credentials or a secret manager. Start the matching Godot binary with --headless --main-pack server25.pck -- --dedicated. Bind only assigned UDP ports; account HTTP stays behind TLS. Keep credentials out of source and client exports. Use unique XDG_DATA_HOME/XDG_CONFIG_HOME per process. The provided existing-host launcher already loads credentials via systemd; extend it to select each instance's credentials and port.

Set KNIVRA_ALLOCATION_DB to a writable local durable filesystem shared by coordinator processes on that host. Do not put a SQLite WAL file on a network filesystem. Fleet configuration is static and operator controlled; automatic VM/container provisioning is not included. Stop allocating by sending state=draining while existing matches finish. A process restart loses the active match; reconnect does not restore a crashed world.

## Path to thousands of actual connected players

1. Provision roughly ceil(players/7) concurrent arena workers plus headroom (1,000 players implies at least 143 seven-player arenas). Measure CPU and memory per instance before choosing density; each Godot process is heavier than a lightweight room object.
2. Move accounts, results and allocator state to PostgreSQL with transactional capacity checks/unique player leases. Move sessions and rate limits to shared TTL storage; remove the global account lock. Preserve idempotent ranked-result handling. Only then replicate stateless HTTP frontends behind a load balancer.
3. Add region-aware fleet configuration, orchestration, health/readiness probes, graceful drain, per-region queues, autoscaling based on waiting players and spare arena slots, durable metrics, alerting and backups.
4. Add edge request/connection protection, per-worker service identity instead of a shared fleet secret, version-gated admission tickets bound to allocated arena, and abuse/load tests. The current trusted fleet shares a key; do not treat it as a multi-tenant hosting platform.
5. Run real multi-host client tests for simultaneous login, queue allocation, packet loss/latency, reconnect storms, crashes, disk pressure and rolling upgrades. Benchmark bandwidth and snapshot fragmentation. Current clients receive full match snapshots; spatial interest filtering and delta snapshots are future bandwidth/privacy improvements.

## Measured limits

See allocator-load.json and simulation-load.json. The allocator test exercises 1,120 logical reservations over 160 configured sessions; it does not start 160 servers or connect 1,120 real clients. Gameplay simulations use nine local AI actors. Authenticated integration tests use two actual Godot clients and a local account service. These results do not establish thousands-player capacity, production availability, or internet latency tolerance. CPU and disk on the user's development machine differ from production infrastructure.
