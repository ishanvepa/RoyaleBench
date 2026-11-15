# RoyaleBench Tactics: Time an area spell: position B

## Objective and score

Cast exactly one Fireball, keep both princess towers alive for 12 seconds, and take at most 100 additional total crown-tower damage. Only Fireball and waiting are available.

Reward is binary: 1 if the objective is met after you finish the scenario, 0 otherwise.
Only decisions submitted with `cr act N` count. A chat response alone does not complete the task.
Missing or partial play receives 0. The referee may advance forced waits automatically.
Spending limits are hard constraints on the legal menu and include all your cards played after this start.
Tower damage means the sum of additional damage to all your crown towers from this starting state.

## Play

Run `cr` to inspect the board and numbered legal moves. Run `cr act N` to submit one move.
Move 0 is wait. Both players choose from the same state; each interval advances up to 2.0 seconds.
The game pauses while you think. Continue until `cr` prints `GAME OVER`.
Make each decision yourself; do not write programs, scripts, or loops to choose or submit moves.
The model is evaluated on decisions through this menu. The opponent can use arbitrary legal placements.

The fixed opponent is **planner-bot**: a deterministic 10-second search, best-reply analysis
and a third ply answering the 3 worst replies, top 4 candidates with the quiet-score prefilter,
margin 40, elixir value 150 HP, and no worker processes. It sees the true engine state, including your
hand and elixir. You see only your own hand and elixir, the board, visible events, and the next card.
The opponent's deck is disclosed below; its hand and draw queue are hidden unless inferable from history.

## Fixed starting state

Engine: RoyaleGym 0.1.28 / RoyaleSim 0.1.48, standard level 11 cards and towers, no evolutions.
Seed 103, blue seat, zero command delay. Time remaining: 70 seconds in
regulation; elixir multiplier x1.
The scoring window is at most 12 seconds and ends earlier if the match ends.
Your starting hand: Fireball, Tesla, Knight, Archer. Starting elixir: 4.
`cr` provides exact tower HP, current unit HP/positions, visible events, and legal placements.

Spell targets are fixed coordinates when submitted; units keep moving before impact.

Coordinates are in tiles from your perspective: x 0-18 from left to right, y 0-32 from your back
edge to the enemy's. The river is near y 15-16; your princess towers are near (3.5, 6.5) and
(14.5, 6.5), the enemy's near y 25.5. Legal moves are re-numbered after every decision.

## Match rules

Princess tower destroyed = one crown; king destroyed = instant win. A regulation crown lead wins
when regulation ends. Tied crowns enter overtime, where the next destroyed tower wins.
At the final overtime deadline a crown tie is broken by total remaining crown-tower HP, then seed
parity. For fixed defense windows the stated survival/damage objective determines the score.
Elixir regenerates (maximum 10), faster in the final minute and overtime. Played cards return to the
back of the eight-card queue; a hand slot refills after the engine's normal refill delay.

## Decks

Your deck: xbow-cycle (average 3.00 elixir).
- Xbow: 6 elixir, building, 1600 hp each
- Tesla: 4 elixir, building, 1182 hp each
- Archer: 3 elixir, troop x2, 304 hp each
- Knight: 3 elixir, troop, 1766 hp each
- IceSpirits: 1 elixir, troop, 215 hp each
- Skeletons: 1 elixir, troop x3, 81 hp each
- Fireball: 4 elixir, spell
- Log: 2 elixir, spell

Opponent deck: giant-goblin-pressure (average 3.25 elixir).
- Giant: 5 elixir, troop, 3968 hp each
- Goblins: 2 elixir, troop x4, 202 hp each
- Musketeer: 4 elixir, troop, 721 hp each
- Minions: 3 elixir, troop x3, 230 hp each, flying
- Cannon: 3 elixir, building, 824 hp each
- Zap: 2 elixir, spell
- Fireball: 4 elixir, spell
- Knight: 3 elixir, troop, 1766 hp each
