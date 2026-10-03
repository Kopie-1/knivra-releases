# KNIVRA Build 25 — Arena Overhaul

Pick Up a Fight.

Build 25 builds on the checksum-verified Build 24 source. This is an early-access arena overhaul, not a claim of finished AAA production quality.

- Windows: open Knivra-25.exe. Linux: extract Knivra-25-Linux.tar.gz and run Play-Knivra.sh. Browser: open the hosted knivra25.html through the website; browser play is offline practice.
- Choose Support, Assault or Breacher. Scavenge weapons and medical supplies. All roles carry a wedge and automatic flashlight. Breachers carry a separate hammer; Assault can carry two firearms.
- WASD/arrows move, mouse aims, left click attacks, Q picks up/swaps, R reloads, 1/2 or wheel switches guns, V places/removes your wedge from inside a room, B swings the Breacher hammer, H heals self and right click heals a nearby ally with a scavenged medical kit. TAB scores, ESC pause/menu.
- Props show damage and break. Marked short wall panels require heavy damage. Barrels warn before exploding. Doors accept wedges and can be breached. Existing glass behavior remains.
- Lights can be shot out. Darkness uses an automatic 220-unit forward cone with wall clipping and muzzle illumination. Dark enemies outside useful visibility are not drawn; full world snapshots still reach clients (see SCALING.md).
- 12-minute deathmatch/team deathmatch and 15-minute capture-the-flag targets, with high score caps. Blackout, rare drop, lockdown, supply cache, bounty, ammo shortage, overload and last-call events occur on a timed sequence.
- Arc launcher is a rare timed bouncing explosive that disables nearby lights. Its model is distinct and unbranded. Bounties grant an extra elimination point.
- Deployment menu, class cards, health/armor/ammo HUD, event notices, smoother loading, cleaner typography and contrast option. Existing account/cosmetic services remain.
- New synthesized bat/hammer/impact/destruction/warning/event sound variants; existing firearm families retain spatial playback and randomized pitch. Further bespoke firearm recordings and a complete art replacement remain future work.

Public Build 25 matchmaking requires the matching server25.pck and allocator. The packaged administrator installer is required on the existing host; website release notes indicate rollout status. Build 24 remains recoverable. Source is in Knivra-Build25-Source.zip; Git history backup is Knivra-Build25-History.bundle. Godot 4.7.2 is used; adapt export-template paths to your machine.

Known limits: no Windows hardware playtest, no physical mobile test, no distributed thousands-client load test. Browser multiplayer transport, automatic infrastructure provisioning, stateless replicated accounts, skill/region matchmaking, and a full studio-quality art/audio replacement are not included. See TESTING.md and SCALING.md for evidence and next steps.
