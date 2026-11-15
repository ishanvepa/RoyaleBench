# RoyaleBench Tactics: One-Fireball Balloon defense

## Objective and score

Keep all three crown towers alive for 16 seconds using exactly one Fireball play and no other card. Spend at most 4 elixir and take at most 240 additional total crown-tower damage. Your left princess tower has 241 HP. A Balloon attack destroys it; its 240-damage death bomb is allowed and must be included in the damage total. You may wait before playing. After your one accepted card play, or after 12 decisions, the referee resolves the remaining window as waits.

Reward is 1 only for a completed, independently replayed sequence meeting every requirement;
otherwise 0. Damage is summed across all three of your crown towers over the full window,
including delayed explosions. Spending counts all accepted card plays. A chat response alone
does not complete the task. These are survival objectives, not full-match wins.

## Play

Run `cr` to inspect the current board and zero-based hand slots. Use `cr play SLOT X Y` to play
or `cr wait` to wait. Command shape only: `cr play 0 8.5 10.5`; choose your own timing and position.
Each decision advances **1 second** of simulated time.
Thinking does not advance the clock. Only **Fireball** may be played, exactly once. Other cards
are present in the hand but are unavailable for this scenario. After an accepted Fireball play,
the referee resolves the rest of the 16 seconds automatically. If you have not played after
12 decisions, it finishes with waits; that fails. Continue until `GAME OVER`. Make each
decision yourself; do not write programs, scripts, or loops to choose or submit moves.
Missing or partial play scores zero.

Coordinates use your perspective: 0 <= x < 18, 0 <= y < 32, your back edge at y=0. Coordinates
are rounded only to engine subtile precision, with no placement snapping by the referee.
Malformed syntax does not advance time. A well-formed illegal action (including another card,
invalid slot, unaffordable card, or illegal location) consumes one interval as a wait, spends
no elixir and reports its rejection. Attempts and accepted placements are independently replayed.

## Fixed starting state

Engine: RoyaleGym 0.1.28 / RoyaleSim 0.1.48, standard level 11 cards and towers, no evolutions.
Seed 42, blue seat, zero additional command delay. Card deployment timers and spell flight time
still apply. There are 170 seconds left in regulation, normal x1 elixir regeneration, and a
16-second scoring window. You start with 4 elixir. The elixir bar
regenerates to a maximum of 10; the one-card restriction and spending limit remain in force.

Your crown towers have HP: king 4824, left princess 241, right
princess 3052. The opponent's towers have HP: king 4824, left princess 3052, right princess 3052.
All six towers are alive and both sides have zero crowns. Your princess towers are centered at
(3.5, 6.5) and (14.5, 6.5); the river is around y=15–17.

The only troop on the starting board is an enemy **full-health Balloon (1676 HP) at (3.5, 20.5)**,
already active and approaching your left bridge. You have no deployed troops or buildings.
`cr` reports current unit positions and HP, tower HP, elixir, hand slots, and next card.

Starting hand in slot order: Skeletons (1 elixir), Fireball (4), Knight (3), Archer (3).
Subsequent draw queue: Giant (5), Minions (3), Cannon (3), Zap (2).
The spell restriction is exactly one Fireball; no other card is available.

There are **no additional enemy deployments during this window**. The fixed opponent is the
existing deterministic Planner (10-second horizon, three plies, top 4, 3 answers, margin 40,
elixir value 150 HP, quiet-score prefilter, workers=0), with privileged engine information.
It starts with zero elixir and a deck whose cheapest cards cost six, so it cannot afford a play
within 16 seconds at x1 regeneration. Its deck is Golem, ThreeMusketeers, Pekka, MegaKnight, LavaHound, Rocket, Lightning, RoyalRecruits.
Losing a princess awards the opponent a crown; losing your king ends the match.
