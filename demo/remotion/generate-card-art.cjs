// Reuse the game's authored card portraits in the demo HUD.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "../..");
const source = fs.readFileSync(path.join(root, "cr_arena/card_art.js"), "utf8");
const art = vm.runInNewContext(`${source}\nCardArt;`);
const out = path.join(__dirname, "public/cards");
fs.mkdirSync(out, { recursive: true });

for (const name of ["IceSpirits", "Cannon", "Fireball", "HogRider", "Log"]) {
  const svg = art.svg(name);
  if (!svg) throw new Error(`Missing game card art: ${name}`);
  fs.writeFileSync(path.join(out, `${name}.svg`), svg);
}
console.log("Staged five game card portraits for the demo HUD.");
