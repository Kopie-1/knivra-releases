# KNIVRA Build 25 — automatic extra arenas

Server-only upgrade; existing Build 25 game downloads remain compatible.

When a player cannot join an available lobby, the supervisor starts another arena. The allocator waits for the new process to report ready before sending players to it. More demand starts further arenas, up to the configured host limit. Existing matches continue independently.

The supplied configuration keeps arena-1 running and allows three extra arenas: four total, up to 28 human players. This is a host safety limit, not unlimited cloud capacity. Players beyond available capacity remain queued. Different requested modes and matches already in progress can also trigger another arena, even below 28 players.

Extra arenas close after they have no connected players, no pending joins or reconnect reservations, and 120 seconds of idle time. A reconnect reservation lasts up to 60 seconds, so closure may take roughly three minutes after the last disconnect. Active matches are not deliberately terminated to reduce server count. Unknown/stale heartbeat state is not treated as an empty match. The supervisor fences matchmaking before stopping a process, preventing a join/shutdown race.

Launch failures and crashed children have a 60-second retry cooldown. Never-ready workers time out after 60 seconds. A singleton lock prevents duplicate supervisors. The service has CPU, memory and process limits; it does not purchase servers or create cloud resources. An out-of-memory condition or supervisor/host failure can still interrupt sessions; this is not fault-tolerant orchestration.

## Activate on the existing Linux host

1. Reserve the desktop's LAN address (currently 192.168.4.93) in your router.
2. Keep the existing UDP 27844 rule. Forward UDP 27846–27848 to 192.168.4.93. Do not use TCP-only rules. External reachability must be checked from outside the home network.
3. Run `sudo python3 install-autoscaling.py --ports-forwarded` from this package. Use the full script path if running elsewhere. `--check` verifies the package without installing it.

The installer backs up changed files under `/var/backups/knivra-autoscale`, reuses existing protected server credentials, preserves player data and the game pack, installs the supervisor, and restarts the account service. If UFW is active it allows just the extra UDP ports. It rolls files back on a failed service/health check. Existing account sessions are in-memory; restarting accounts may require player sign-in/recovery.

Installation requires administrator access. This package being available does not mean the live host or router has been updated.

## Operations

`systemctl status knivra-autoscale` shows service state; `journalctl -u knivra-autoscale` shows worker starts/stops. No credentials are written to these logs by the supervisor. Each worker has a separate state directory and UDP port. An orderly service stop stops allocating to extra arenas and waits for their players/leases to leave (up to the service's 1,000-second shutdown timeout). Do not restart the service casually during busy matches; a timeout or unexpected host failure can kill games.

To increase the cap, edit `/etc/knivra/fleet25.json` with more unique managed IDs, UDP ports and public addresses, forward those ports, and reload the account service/supervisor during a maintenance window. Benchmark hardware first and adjust resource limits deliberately. This supervisor launches local processes only; multi-host/cloud provisioning remains future work. Account session storage and control-plane scaling limitations in Build 25's SCALING.md still apply.

## Test evidence

- 11 supervisor tests passed: demand/readiness, no duplicate boots, four-arena cap/overflow queue, idle retirement, reconnect protection, stale heartbeat safety, start failure, boot timeout, process exit, mode transition, graceful drain, and allocation fencing during stop (several checks share a test).
- Six existing fleet allocator tests passed, including concurrent allocation and no overbooking.
- End-to-end integration: seven synthetic reservations filled the base arena. Two actual authenticated Godot clients triggered one extra real Godot process, joined it, and completed consecutive rounds. The process retired after disconnect/reconnect expiry with a shortened one-second test idle delay. Production idle delay is 120 seconds.
- Installer payload hashes, Python syntax and systemd unit validation passed.
- This does not prove 28 real simultaneous internet clients or external router reachability. No live player load or cloud infrastructure was used.
