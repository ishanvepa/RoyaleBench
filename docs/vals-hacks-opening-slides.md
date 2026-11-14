# Vals Hacks Opening Slides

- **Source:** [Google Slides deck](https://docs.google.com/presentation/d/1H-QNpvj9yiOsfHkSJIJDYn4V4CeQp6YcT4lULLvALts/edit)
- **Deck date:** November 14–15, 2026
- **Slides:** 17
- **Extraction:** Visible slide text and speaker notes, organized by slide. Text is preserved as shown; line breaks and visual layout are represented as readable lists.
- **Visuals:** Embedded images, logos, and screenshots are not transcribed. Where the text view exposed an asset name, it is included. Slide 16 contains five images whose contents are not identified by the text view.

## Slide 1 — Welcome, Hackers

**Visible text**

- VALS HACKS
- NOVEMBER 14–15, 2026
- WELCOME, HACKERS
- San Francisco, CA
- November 14–15, 2026
- Visual asset: `logo-vals.png`

**Speaker notes**

> Welcome everyone as they settle in. Hand off to Ryan for opening remarks.

## Slide 2 — Opening Remarks

**Visible text**

- OPENING REMARKS
- WHY WE’RE HOSTING VALS HACKS
- BENCH MAXXING
- Footer: VALS HACKS · NOV 14–15, 2026
- Slide number: 2

**Speaker notes**

> Ryan: opening remarks. Who Vals is, why we’re hosting, and encouragement. Keep it short — no keynote today.

## Slide 3 — Today’s Agenda

**Visible text**

- DAY ONE · SATURDAY, NOV 14
- TODAY’S AGENDA
- **12:00 PM — CHECK-IN:** Name tags, and we collect your email for prizes
- **1:00 PM — OPENING REMARKS:** Rayan, CEO of Vals AI
- **1:15 PM — TRACKS + LOGISTICS:** Tracks, food, Wi-Fi, the space, timeline
- **1:30 PM — TEAM GROUPING:** Find your team
- **2:00 PM — HACKING BEGINS:** Snacks all day; Vals staff on hand
- **6:00 PM — DINNER + NETWORKING:** Dessert, and teams share what they’re building
- Footer: VALS HACKS · NOV 14–15, 2026
- Slide number: 3

**Speaker notes**

> Hacking continues overnight with Vals staff on site. If a guest speaker is added, they go in the evening slot.

## Slide 4 — Tomorrow’s Agenda

**Visible text**

- DAY TWO · SUNDAY, NOV 15
- TOMORROW’S AGENDA
- **8:00 AM — BREAKFAST:** Bagels and coffee
- **12:00 PM — LUNCH + MERCH:** Grab a shirt, stickers or a hat
- **2:00 PM — SUBMISSIONS DUE:** Submit on the platform; we’ll post a reminder in Slack
- **2:00 PM — JUDGES ARRIVE:** Have your demo ready
- **2:30 PM — JUDGING:** Teams present to the judges
- **3:00 PM — WINNERS ANNOUNCED:** Winning demos on the big screen
- Footer: VALS HACKS · NOV 14–15, 2026
- Slide number: 4

**Speaker notes**

> If scoring takes an hour or two, prizes are awarded right after judging; otherwise we contact winners by email and mail prizes.

## Slide 5 — The Tracks

**Visible text**

- PICK YOUR TRACK
- THE TRACKS
- **TRACK ONE — BUILD YOUR OWN EVAL:** Design a benchmark that measures something models still get wrong.
- **TRACK TWO — POST-TRAIN A SMALL MODEL:** Use Tinker to post-train a small model and show it got better.
- **TRACK THREE — POST-TRAIN VALS POKER BOT:** Post-train a bot to compete on PokerBench, Vals’ 10-player no-limit table.
- Footer: VALS HACKS · NOV 14–15, 2026
- Slide number: 5
- Visual assets: six images named `image.png`

**Speaker notes**

> Sandboxes for Tracks One and Two are covered by Modal.

## Slide 6 — Get Set Up

**Visible text**

- HACKATHON.VALS.AI
- GET SET UP
- **SIGN IN:** Sign in with your email and a one-time code.
- **WAIT FOR APPROVAL:** Pick your track. An organizer approves you at check-in.
- **CREATE OR JOIN A TEAM:** Create a team with a name, track and 1–4 people. Or join with a teammate’s code.
- Footer: VALS HACKS NOV 14–15, 2026
- Slide number: 6
- Visual assets: `screen-signin.png`, `screen-waiting.png`, `screen-team.png`

## Slide 7 — How “Build Your Own Eval” Works

**Visible text**

- TRACK ONE
- HOW “BUILD YOUR OWN EVAL” WORKS
- **FIND MODEL FAILURES:** Find tasks that leading AI models still get wrong.
- **BUILD ON VALKYRIE:** Build your benchmark, a set of tests, on Valkyrie. Use your team’s organization.
- **SHOW YOUR WORK:** Submit a code repository, a writeup and a short demo video.
- **PRESENT TO JUDGES:** Judges score model difficulty, novelty, demo clarity and project completeness.
- Footer: VALS HACKS NOV 14–15, 2026
- Slide number: 7
- Visual assets: `logo-openai-white.png`, `logo-claude-white.png`, `logo-modal-white.png`

**Speaker notes**

> First, second and third place on PokerBench take home cash prizes from Applied Compute.

## Slide 8 — Build Your Own Eval

**Visible text**

- TRACK ONE SETUP
- BUILD YOUR OWN EVAL
- **CLAIM AND INSTALL:** Claim Claude and OpenAI credits to test tasks. Claim Modal credits to run them. Install uv to manage Python tools. Run `uv tool install valkyrie-cli`.
- **SIGN IN AND RUN:** Run `valkyrie login`. Run `valkyrie org use <team org>`. Start at quickstart step 3. Use Harbor’s task-file format. Upload with dataset commands. Watch with `valkyrie tui`. Submit on hackathon.vals.ai.
- Footer: VALS HACKS NOV 14–15, 2026
- Slide number: 8
- Visual assets: `screen-eval.png`, `logo-valkyrie.png`, `logo-openai.png`, `logo-claude.png`, `logo-modal.png`

## Slide 9 — How Post-Training Works

**Visible text**

- TRACK TWO
- HOW POST-TRAINING WORKS
- **TRAIN A SMALL MODEL:** Train further on Tinker. Use at most 9B active parameters, the settings used for each token.
- **SOLVE HARD PROBLEMS:** Your model writes C++ solutions for hard competitive programming problems.
- **SUBMIT FOR SCORING:** Submit a Tinker checkpoint, a saved model. We score it on a private test set.
- **CLIMB THE LEADERBOARD:** Your team’s best score sets its rank on the live leaderboard.
- Footer: VALS HACKS NOV 14–15, 2026
- Slide number: 9
- Visual assets: `logo-tinker-white.png`, `logo-modal-white.png`

**Speaker notes**

> First, second and third place on PokerBench take home cash prizes from Applied Compute.

## Slide 10 — Train with Tinker

**Visible text**

- TRACK TWO SETUP
- TRAIN WITH TINKER
- **SAVE AND SUBMIT:** Save your model’s learned settings with `save_weights_for_sampler`. Enter the `tinker://` path and its owner’s Tinker key under Submit a model. Keep the saved settings available past Sun 3 PM.
- **PLAN YOUR ATTEMPTS:** Your team gets 4 attempts per hour. Edits count. Wait for each run to finish. Your submission page shows the time left.
- Footer: VALS HACKS NOV 14–15, 2026
- Slide number: 10
- Visual assets: `screen-tinker.png`, `logo-tinker.png`, `logo-modal.png`

## Slide 11 — How PokerBench Works

**Visible text**

- TRACK THREE · BACKED BY APPLIED COMPUTE
- HOW POKERBENCH WORKS
- **10-PLAYER TABLE:** No-limit Texas Hold’em, bot against bot.
- **SAME STARTING LINE:** Every team starts from the same reference setup.
- **NO SURPRISES:** You get the exact harness your bot will be scored in.
- **LIVE ALL WEEKEND:** Live rankings, with tournament checkpoints overnight.
- Footer: VALS HACKS · NOV 14–15, 2026
- Slide number: 11
- Visual asset: `logo-applied-white.png`

**Speaker notes**

> First, second and third place on PokerBench take home cash prizes from Applied Compute.

## Slide 12 — Poker Bot Setup

**Visible text**

- TRACK THREE SETUP
- POKER BOT SETUP
- **OPEN YOUR LINKS:** Open the Applied Compute links on your home page. Train your poker model there.
- **FOLLOW THE GAMES:** Your bot plays no-limit Texas Hold’em against other teams’ bots. Applied Compute runs the games and keeps the live leaderboard. Your home page has your track guide, team code, credits, Slack and schedule.
- Footer: VALS HACKS NOV 14–15, 2026
- Slide number: 12
- Visual assets: `screen-poker.png`, `logo-applied.png`

## Slide 13 — $60K+ in Prizes

**Visible text**

- PRIZES
- $60K+ IN PRIZES
- Across all three tracks.
- **TRACK ONE**
  - 1st: Nintendo Switch 2 + Modal & Claude credits
  - 2nd: AirPods Max + Modal & Claude credits
  - 3rd: WHOOP fitness tracker + Modal & Claude credits
- **TRACK TWO**
  - 1st: Nintendo Switch 2 + Tinker & Modal credits
  - 2nd: AirPods Max + Tinker & Modal credits
  - 3rd: WHOOP fitness tracker + Claude & Modal credits
- **TRACK THREE**
  - 1st: $7,500
  - 2nd: $5,000
  - 3rd: $3,200
- Footer: VALS HACKS · NOV 14–15, 2026
- Slide number: 13
- Visual assets: six images named `image.png`

**Speaker notes**

> Leaving before awards? That’s okay — we collected your email at check-in and will reach out if you win.

## Slide 14 — What You Get to Build With

**Visible text**

- COMPUTE AND CREDITS
- WHAT YOU GET TO BUILD WITH
- Each person gets $100 for Claude. Sign in to your API account. Claim in Your credits.
- Each person gets $100 for OpenAI. Sign in to your API account. Claim in Your credits.
- Each person gets $100 for Tinker. Sign in to Tinker. Claim from Your credits on your home page.
- Sandbox compute for Tracks One and Two is covered by Modal.
- Platform is provided by Applied Compute
- **HELP AND CODES:** Open Your credits on your home page after check-in. Staff load the codes and links into the portal. Ask any Vals team member in a Vals Hacks shirt.
- Footer: VALS HACKS NOV 14–15, 2026
- Slide number: 14
- Visual assets: `logo-claude.png`, `logo-openai.png`, `logo-tinker.png`, `logo-modal.png`, `logo-applied.png`

**Speaker notes**

> Confirm credit amounts and redemption steps with Jarett and Langston before the event.

## Slide 15 — Know Before You Hack

**Visible text**

- LOGISTICS
- KNOW BEFORE YOU HACK
- **WI-FI:** Network: Vals AI Guest · Password: `WhoEvalsTheEvals?`
- **FOOD:** Snacks and drinks all day, dinner tonight, breakfast tomorrow. evi and water fountain have fizzy + flat water.
- **SLACK:** #announcements for updates, a channel for each track, and #social.
- **THE SPACE:** Please respect our space! Dispose of trash properly, respect our furniture, clean up after yourself!
- **RESTROOMS:** Back hall, please don’t enter the shower room!
- **ENTRY:** Doors are locked. When you exit, buzz the intercom and be prepared to say first + last name for re-entry
- Footer: VALS HACKS · NOV 14–15, 2026
- Slide number: 15

**Speaker notes**

> Join the Slack from the Luma invite if you haven’t yet. All announcements go there.

## Slide 16 — Our Supporters

**Visible text**

- THANK YOU
- OUR SUPPORTERS
- Footer: VALS HACKS · NOV 14–15, 2026
- Slide number: 16
- Visual assets: five images named `image.png`; image contents are not identified in the text view.

**Speaker notes**

> Reps from Thinking Machines, Applied Compute and Modal may be around during hacking — say hi.

## Slide 17 — Let’s Benchmaxx

**Visible text**

- VALS HACKS
- NOVEMBER 14–15, 2026
- LET’S BENCHMAXX
- Submissions due Sunday at 2:00 PM.
- Visual asset: `logo-vals.png`

**Speaker notes**

> Send teams off to hack. Point them to Slack for announcements.
