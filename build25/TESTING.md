# Build 25 verification

- 125 new gameplay checks across four maps: role armor/equipment, scavenged medicine, progressive object damage, heavy-only wall breaches, barrel warning delay, door damage, wedge placement/removal/collision, light destruction, all event types, rare projectile behavior, flashlight visibility bounds, synchronized environment state, match timer and reset, short combat simulations.
- Updated core arena regression suite passed. Existing expectations intentionally changed for finite armor, no free starting medical kit, Build 25 snapshot length, higher score caps and bat audio family. Original Build 24 test expectations remain recoverable in the baseline tag.
- 5,712 spawn regression cases passed.
- Six allocator integration tests passed, including eight simultaneous coordinator threads, no overbooking, stale-heartbeat removal, persistent restart state, reconnect route, build validation and rate limits.
- 1,120 logical player reservations allocated to 160 configured seven-slot sessions in 9.724 seconds (median 4.2 ms, p95 29.55 ms per sequential request). These were allocator records, not actual connected game clients.
- Four local gameplay simulations, each 240 seconds at 30 Hz with nine actors. See simulation-load.json for measured p95 and maximum tick times and snapshot sizes. Destruction navigation updates were changed from whole-map rebuilds to affected cells after an initial 482 ms spike.
- Two real authenticated Godot clients against a local account service and dedicated arena completed consecutive rounds with map rotation, correct selected role and cosmetics, and account-session loss/recovery. Repeated using the exported Build 25 server pack.
- Native Linux game launched; menu, arena and blackout screenshots captured and reviewed. Wide-screen darkness alignment repaired.
- Browser build launched and entered a Breacher practice match. Keyboard movement was observed; combat, damage/armor loss and kill feed ran. A long-audio-buffer failure found during testing was fixed by preserving streaming music and avoiding redundant pause changes. No console errors were seen in the subsequent running match. A later browser-control timeout limits claims about individually verified pickup/attack commands.
- Server installer payload checksums and Python syntax validated. It requires administrator execution for live activation and contains rollback logic; live activation is reported separately in DELIVERY.md.

Not established: thousands of connected players, production uptime/SLA, real packet-loss resilience, Windows OS behavior, physical phone/tablet ergonomics, subjective professional audio mixing, or a complete major studio art standard. This remains an early-access release.
