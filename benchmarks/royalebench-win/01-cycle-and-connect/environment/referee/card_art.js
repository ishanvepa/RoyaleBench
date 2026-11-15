/* Original, reference-informed pixel portraits for the 35 CLASSIC_DECKS cards.
 * Integer coordinates, stepped silhouettes, and a shared 48 × 60 grid keep these
 * legible in the hand and Next slot. No fonts, fetched images, IDs, or randomness.
 * Reference links and the engine-name aliases are recorded in docs/rendering.md.
 */
const CardArt = (() => {
  "use strict";
  const ink = "#142131";
  const p = (d, fill, edge = false) => `<path d="${d}" fill="${fill}"${edge ? ` stroke="${ink}" stroke-width="2" stroke-linejoin="miter"` : ""}/>`;
  const r = (x, y, w, h, fill) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill}"/>`;
  const eye = (x, y, color = "#65d9f5") => r(x, y, 6, 4, "#fff4db") + r(x + 2, y, 3, 4, color) + r(x + 3, y + 1, 2, 3, ink);
  const bolt = (x, y, color = "#c9fbff") => `<g transform="translate(${x} ${y})">${p("M7 0H3v7H0v5h5v-4h4V4h3V1H7z", color)}</g>`;
  const skull = (x, y, s = 1, bone = "#eee7cf") => `<g transform="translate(${x} ${y}) scale(${s})">` +
    p("M3 0h12v2h3v12h-3v5H4v-5H1V3h2z", "#8b9ca4", true) +
    p("M3 2h12v2h1v7h-3v4H5v-3H3z", bone) + r(4, 6, 4, 5, ink) + r(11, 6, 4, 5, ink) +
    p("M9 11h2v3H8v-2h1z", ink) + r(6, 16, 2, 3, "#c4c4b2") + r(11, 16, 2, 3, "#c4c4b2") + "</g>";
  const arrow = (x, y, s = 1) => `<g transform="translate(${x} ${y}) scale(${s})">` +
    p("M0 0h3v4h2V1h3v7H6v17H3V8H0z", "#d65c64", true) + r(3, 8, 3, 18, "#b78b62") +
    p("M1 25h7l-3 8H3z", "#e9f0e8", true) + "</g>";
  const vial = (liquid, long = false) => p(long ? "M20 8h9v8h3v5h3v30H12V22h3v-6h5z" : "M18 12h13v8h5v5h3v26H9V25h3v-5h6z", "#bedee4", true) +
    p(long ? "M16 30h15v18H16z" : "M13 32h22v15H13z", liquid) +
    r(long ? 18 : 14, 24, 3, 19, "#f0ffff") + r(long ? 19 : 17, long ? 7 : 11, long ? 11 : 15, 5, "#bd8153") +
    r(long ? 20 : 18, long ? 7 : 11, long ? 8 : 12, 2, "#e4b57c");
  const goblin = (x, y, scale = 1) => `<g transform="translate(${x} ${y}) scale(${scale})">` +
    p("M6 6H1v7h4v10h3v6h13v-6h4V12h5V4h-4l-5 4V4H9v4z", "#427e46", true) +
    p("M7 9h3V6h10v4h4v11h-3v5H10v-5H7z", "#9acb57") +
    p("M2 8h4v6H4zM25 8h3v3h-3z", "#c9dc79") + eye(9, 11, "#c89535") + eye(19, 10, "#c89535") +
    p("M16 13h3v5h3v3h-9v-3h3z", "#cee583") + p("M10 21h12v3h-2v2h-8v-2h-2z", ink) + r(12, 21, 8, 2, "#fff4dc") + "</g>";

  // rarity, background shadow, background light, portrait builder
  const ART = {
    Archer: ["common", "#24534d", "#78ad83", () =>
      p("M3 59V45h6V21h3V10h7V6h16v5h5v11h4v37z", "#632c57", true) +
      p("M7 55V42h8v-6h19v6h8v17H7z", "#3d8970") + p("M17 34h15v10H17z", "#ba7756") +
      p("M14 17h22v8h3v8h-4v7H23v-3h-7V26h-2z", "#f4bf88", true) +
      p("M13 12h21v4h5v12h-5V17h-5v12h-6V16h-4v15h-6z", "#f06cab") +
      r(17, 11, 15, 3, "#ffacd0") + eye(24, 27) + p("M31 33h5v2h-5z", "#bb615c") +
      p("M7 18h5v17H8zM8 48h27v3H8z", "#b94b88") +
      p("M37 20h3v4h2v19h-2v7h-3v-9h2V28h-2z", "#cf9857", true) + r(5, 43, 38, 2, "#f3dcab")],
    Arrows: ["common", "#397d9b", "#a5dae2", () =>
      p("M1 26h6v3H1zM37 8h9v3h-9zM26 45h12v2H26z", "#d6eef0") +
      `<g transform="rotate(23 24 30)">${arrow(4, 2, 1.05)}${arrow(19, 11, 1.2)}${arrow(34, -4, 1.1)}</g>` +
      p("M4 53h11v2H4zM33 40h10v2H33z", "#d6eef0")],
    BabyDragon: ["epic", "#206469", "#85c482", () =>
      p("M3 41V28h6v5h4v-8h23v10h7v-7h3v25H3z", "#40885e", true) +
      p("M15 59V39h20v20z", "#66b974") + p("M25 40h8v19h-8z", "#9cd98d") +
      p("M13 16h5V9h8V4h4v8h9v4h4v17h-4v11H15v-5H7V24h6z", "#53ba67", true) +
      p("M18 11V5h-6V2H7v6h5v7zM35 13l5-10h4v10l-5 7z", "#d3de8e", true) +
      p("M10 24h14v-7h11v5h5v10H9z", "#91d881") + eye(29, 19, "#e9b739") +
      p("M11 33h27v7h-4v5H20v-4h-9z", "#49332b", true) + r(14, 33, 4, 4, "#f9edce") + r(31, 34, 4, 5, "#f9edce") +
      p("M16 41h16v5H19v-2h-3z", "#51b2b3") + r(11, 27, 3, 3, "#24684d")],
    Balloon: ["epic", "#426576", "#b9cfac", () =>
      p("M6 1h36v4h4v18h-4v7h-7v4H13v-4H6v-7H2V5h4z", "#355c77", true) +
      p("M9 2h10v28h-7v-7H8zM29 2h10v21h-4v7h-6z", "#6c9caf") + r(22, 2, 3, 30, "#a1bac1") +
      r(4, 18, 40, 3, "#b99b67") + p("M10 29h2v17h-2zM36 29h2v17h-2z", "#d8c895") +
      p("M13 44h25v12H16v-4h-3z", "#866143", true) + r(16, 47, 19, 3, "#c49a65") +
      skull(15, 30, .75) + p("M7 43h9v9H5v-7h2z", ink, true) + r(7, 43, 4, 2, "#667681")],
    Bats: ["common", "#272a4c", "#5f6289", () =>
      p("M2 19h4v6h4v4h6v-9h16v9h6v-4h4v-6h4v23h-7v5h-7v5H16v-5H9v-5H2z", "#423f6f", true) +
      p("M5 29h4v5h9v10h-5v-4H5zM30 34h9v-5h4v11h-8v4h-5z", "#ad74aa") +
      p("M14 29V10h4l5 13h3l5-13h4v23h-3v12h-5v5H20v-5h-5z", "#8295bf", true) +
      p("M17 15h2v9h-2zM31 15h2v9h-2z", "#ef9cbb") + eye(16, 30, "#b6f4ff") + eye(27, 30, "#b6f4ff") +
      p("M18 39h13v6h-3v3h-7v-3h-3z", "#482f51") + r(19, 39, 3, 5, "#fff1dc") + r(27, 39, 3, 5, "#fff1dc")],
    BattleRam: ["rare", "#305d66", "#a0c9a0", () =>
      p("M8 60V39h5v-8h9v12h4v17zM29 60V35h4v-7h10v32z", "#bf8b61", true) +
      r(13, 33, 6, 9, "#e6b982") + r(34, 31, 6, 10, "#e6b982") +
      `<g transform="rotate(-18 24 25)">` + p("M3 17h32v22H3z", "#94623e", true) +
      r(4, 19, 25, 5, "#cea571") + r(4, 29, 26, 3, "#66452e") +
      p("M27 13h10v3h5v5h3v13h-4v5h-7v3H24V15h3z", "#496c7b", true) +
      p("M28 15h9v3h4v7H29z", "#94afae") + r(26, 26, 16, 8, "#365163") +
      r(26, 17, 3, 3, "#d0dbca") + r(27, 35, 3, 3, "#96afb2") + "</g>"],
    Cannon: ["common", "#9b8460", "#d8cc99", () =>
      p("M4 49h39v10H4z", "#765234", true) + r(6, 48, 35, 5, "#c99b59") +
      p("M9 51h5v8H9zM32 51h5v8h-5z", "#9f713f") +
      p("M13 43V25h4v-7h7v-6h16v4h5v23h-5v6H25v3H13z", "#253a4a", true) +
      p("M15 27h5v-6h9v19H16z", "#506b7a") + p("M19 22h6v20h-6z", "#4a99c3") +
      p("M29 15h11v4h4v16h-4v6H29v-4h-4V21h4z", "#859596", true) +
      p("M31 20h7v3h3v10h-3v3h-8v-3h-2v-9h3z", "#111f2c") + r(31, 21, 6, 3, "#324251")],
    ElectroWizard: ["legendary", "#173c65", "#569ec0", () =>
      bolt(0, 28) + bolt(37, 5) + p("M6 60V47h8v-8h20v7h9v14z", "#255a84", true) +
      p("M12 20V7h6V2h6v7h5V4h8v9h5v12z", "#172431", true) +
      p("M13 20h23v8h3v11h-5v8H20v-5h-7z", "#e0a37b", true) + r(15, 22, 17, 3, "#f6cba0") +
      p("M14 26h9v3h-9zM28 26h8v3h-8z", "#26333e") + eye(15, 30) + eye(29, 30) +
      p("M23 34h5v5h-7v-2h2z", "#ba755b") + p("M17 39h6v-2h4v2h9v4h-7v-2h-5v2h-7z", "#1b2937") +
      r(23, 46, 7, 8, "#efd4ad") + p("M13 9h5v4h6V9h5v4h7v3H23v-2H13z", "#91f4f0") + bolt(2, 44)],
    Fireball: ["rare", "#722d32", "#c3613d", () =>
      p("M43 1h5v18h-4v12h-6v9h-6v6H12v-5H7V28h5v-7h7v-6h8v-5h10V5h6z", "#e65b31", true) +
      p("M42 9h3v10h-6v10h-6v9h-6v6H13v-5H9V28h7v-6h9v-6h10v-4h7z", "#ff9f37") +
      p("M35 21h5v6h-7v9h-5v8H14v-4h-3v-9h6v-6h10v-5h8z", "#ffe37a") +
      p("M21 29h7v9h-5v5H13V33h8z", "#fff4ce") + r(5, 47, 3, 3, "#ffce60") + r(33, 44, 2, 4, "#ffb23c") + r(9, 16, 3, 4, "#ff9d37")],
    Giant: ["rare", "#6a635b", "#b9b39b", () =>
      p("M0 60V44h8v-9h32v9h8v16z", "#705140", true) + r(8, 40, 9, 20, "#9b6d49") + r(33, 40, 8, 20, "#9b6d49") +
      p("M7 16h4V9h25v5h5v23h-4v9H14v-5H8V26H5v-7h2z", "#d89160", true) +
      p("M12 16h22v4h5v14h-5v8H17v-5h-5z", "#f4be85") +
      p("M9 10h5V6h21v4h5v9h-7v-5H18v6h-7v17h5v6h17v-6h6v8h-5v5H15v-5H9z", "#cd703a") +
      p("M14 9h18v3H14zM11 16h4v17h-4z", "#f5a14f") + eye(17, 22, "#5c9fcb") + eye(30, 22, "#5c9fcb") +
      p("M25 27h4v5h-6v-2h2z", "#d69667") + p("M21 35h12v2H21z", "#8e5542")],
    GoblinBarrel: ["epic", "#3e7c7e", "#a1cfa8", () =>
      goblin(8, 3, 1) + p("M4 37h5v-4h28v4h6v15h-6v5H10v-4H4z", "#8e613f", true) +
      r(8, 37, 28, 6, "#d1a66d") + r(10, 45, 25, 9, "#b78654") + r(15, 37, 2, 17, "#684931") +
      r(28, 38, 2, 17, "#684931") + p("M5 42h36v4H5zM10 52h27v4H10z", "#728180") +
      r(9, 43, 4, 2, "#c8d1b9") + r(33, 43, 4, 2, "#c8d1b9") + p("M8 33h7v9H8zM33 33h7v9h-7z", "#9acb57", true)],
    GoblinGang: ["common", "#3f6453", "#92b678", () =>
      goblin(-5, 5, .8) + goblin(27, 4, .8) + p("M4 60V42h10v-8h21v8h9v18z", "#4b91ad", true) +
      goblin(7, 12, 1.05) + p("M3 35h4v-9h3v24H6v-8H3z", "#c1ced0", true) +
      p("M39 21h3v-8h2v25h-5z", "#e6dfbd", true) + r(40, 38, 2, 20, "#967547")],
    Golem: ["epic", "#554457", "#b5a29e", () =>
      p("M1 60V40h6V20h4V10h7V6h17v5h6v11h4v38z", "#63525e", true) +
      p("M11 14h5v-4h18v5h5v14h-7v4H16v-4H9V20h2z", "#b2a8a0") +
      p("M15 12h18v3H15zM12 17h4v7h-4z", "#dfd2b9") +
      p("M9 28h9v3h14v-4h9v12h-6v6H15v-4H9z", "#91818b") +
      p("M12 25h10v5H12zM28 25h10v5H28z", "#e65cce") + r(14, 26, 7, 2, "#ffe0ef") + r(29, 26, 7, 2, "#ffe0ef") +
      p("M16 36h17v3h-4v3H18v-2h-2z", "#302d3a") + r(18, 36, 4, 2, "#d2c2b4") +
      p("M3 45h10v13H3zM17 47h15v13H17zM37 44h9v16h-9z", "#8c7a84")],
    HogRider: ["rare", "#347782", "#a1d0bd", () =>
      p("M1 60V47h7v-6h26v4h10v15z", "#84513e", true) +
      p("M10 18h4V9h18v6h6v10h5v14h-6v10H19v-5h-7V28H8v-7h2z", "#9a6044", true) +
      p("M15 19h18v7h6v9h-6v10H21v-5h-6z", "#bd8058") +
      p("M16 14V6h5V2h8v4h5v9h-5v-5h-7v4z", "#352d2b") +
      p("M18 33h4v5h14v-4h5v11h-5v7H21v-5h-6V35z", "#3f2c29") +
      eye(19, 23, "#664d35") + eye(32, 23, "#664d35") + p("M24 34h14v9H24z", "#211f29") +
      r(25, 34, 11, 3, "#fff1d4") + r(29, 41, 7, 3, "#d78c77") + r(9, 29, 3, 6, "#f5c65d")],
    IceGolemite: ["rare", "#215689", "#7bc9df", () =>
      p("M3 60V40h5V25h3V13h6V6h6v6h6V4h5v10h6v12h4v34z", "#397fa9", true) +
      p("M14 18h5v-7h4v7h9v-6h3v9h5v17h-6v8H17v-5H9V27h5z", "#a5e4e8") +
      p("M16 13h5v11h-7v-6h2zM30 7h3v13h-3z", "#cdf8ed") +
      p("M12 27h10v5H12zM29 27h10v5H29z", "#19cbf6") +
      p("M22 30h8v8H19v-4h3z", "#2a5c77", true) + p("M14 40h22v5H14z", "#386c92") +
      r(17, 39, 4, 5, "#dcf9eb") + r(28, 39, 4, 5, "#dcf9eb") +
      p("M3 49h11v11H3zM18 48h14v12H18zM37 47h8v13h-8z", "#7ac4dc")],
    IceSpirits: ["common", "#14517d", "#5cbada", () =>
      p("M12 49H7V33H4V23h6V12h5v9h4V8h5v10h7V9h5v15h6v11h-4v11h-7v7H19v-4z", "#52cde4", true) +
      p("M13 25h3v-7h5v7h12v3h5v10h-4v7H16v-5h-5V29h2z", "#b1f3f0") +
      p("M14 31h5v5h-5zM28 29h6v6h-6z", "#35b5d8") +
      p("M18 37h16v6h-4v5h-8v-4h-4z", "#265487", true) + r(20, 38, 3, 3, "#f3fff4") +
      p("M14 50h14v4h-9v3H9v-3h5z", "#82e2eb") + r(5, 9, 3, 3, "#b1f3f0") + r(39, 48, 3, 3, "#b1f3f0")],
    InfernoTower: ["rare", "#603849", "#d27b4a", () =>
      p("M10 60v-8h7V34h-4V23h22v11h-4v18h7v8z", "#554958", true) +
      r(19, 35, 7, 24, "#a47668") + r(27, 36, 3, 21, "#352f3f") +
      p("M14 26h20v5H14zM17 22v-7h4v-5h8v5h5v7z", "#d4a058", true) +
      r(21, 14, 8, 9, "#ffad4f") + r(23, 12, 4, 10, "#ffedb3") +
      p("M0 5h9v4h8v4h7v6h-5v-3h-7v-4H5V9H0z", "#fb653b") +
      p("M0 5h6v3h8v4h9v4h-4v-2h-7v-4H4V8H0z", "#fff1a9") +
      r(13, 27, 22, 3, "#bd9689") + r(12, 53, 24, 4, "#e78644")],
    Knight: ["common", "#4c6978", "#b1c9bd", () =>
      p("M3 60V46h10v-8h24v8h8v14z", "#425a70", true) +
      p("M10 22h28v16h-4v8H20v-4h-7V32h-3z", "#e8b68a", true) +
      p("M9 23V13h5V8h19v4h6v12H9z", "#869b9d", true) +
      p("M14 11h8v8H11v-4h3zM25 10h7v10h-7z", "#c5d5cb") + r(9, 21, 30, 4, "#506778") +
      eye(16, 27, "#7095a0") + eye(29, 27, "#7095a0") +
      p("M14 32h8v3h5v-3h9v-3h5v7h-4v4H27v-3h-4v3H12v-4H8v-6h5v2z", "#e4b449", true) +
      r(13, 33, 10, 3, "#ffda6a") + r(29, 34, 9, 3, "#ffda6a") +
      p("M6 48h8v12H6zM35 48h8v12h-8z", "#91a8aa") + r(22, 48, 6, 6, "#559bc8")],
    LavaHound: ["legendary", "#5d382e", "#ae8351", () =>
      p("M3 51V26h5V15h7V8h18v6h7v9h5v28h-6v9H10v-9z", "#493d39", true) +
      p("M9 20h6V9h9v9h10v-5h4v14h5v16H31v7H15v-6H7V29h2z", "#766454") +
      p("M15 7h6V2h7v10h-7v5h-6zM6 19H1v-6h9v7zM39 19v-6h8v7h-8z", "#a08e6e", true) +
      p("M10 26h12v6H10zM29 26h12v6H29z", "#f18335") + r(13, 27, 7, 3, "#ffef9d") + r(30, 27, 7, 3, "#ffef9d") +
      p("M21 29h8v10h-3v9h-5V37h-3v-4h3z", "#a38863") +
      p("M8 40h9v4h-4v10h-3zM35 38h5v14h-5v8h-3V47h3z", "#ce6435")],
    Lightning: ["epic", "#233879", "#6a90b9", () =>
      bolt(2, 6) + bolt(35, 24) + bolt(0, 43) + vial("#386bd1") +
      p("M25 26h5v9h-4v6h-5v-7h4z", "#79c7f3") +
      p("M7 1h2v8H6v8H3v-6h2V7h2zM38 1h3v9h-4v10h-3v-7h2V6h2zM37 46h3v5h-4v6h-4v-4h3v-5h2z", "#b9f6ff")],
    Log: ["legendary", "#5c795c", "#bcd2a0", () =>
      `<g transform="rotate(-26 24 31)">` + p("M7 18h33v4h4v22h-4v4H7v-4H3V22h4z", "#70472d", true) +
      r(8, 21, 29, 23, "#aa7443") + r(9, 22, 28, 4, "#d7a468") + r(12, 30, 25, 3, "#6b482f") +
      r(12, 39, 25, 3, "#815330") + p("M6 21h7v3h4v17h-4v4H6v-4H3V25h3z", "#e0b679", true) +
      p("M8 27h4v3h2v8H8v-3h3v-4H8z", "#ad7847") +
      p("M23 19v-9h5v9zM28 44h5v9h-5zM38 27h7v7h-7z", "#b6c2be", true) + "</g>" +
      r(3, 50, 4, 3, "#e3d7a7") + r(37, 10, 3, 3, "#e3d7a7")],
    MegaMinion: ["rare", "#244c70", "#7fa5bc", () =>
      p("M1 12h5v8h6v8h24v-8h6v-8h5v30h-8v7H9v-7H1z", "#273c52", true) +
      p("M4 23h4v9h7v9H9v-4H4zM34 32h6v-9h4v14h-5v4h-5z", "#476b85") +
      p("M11 60V25h4V15h7V7h5v8h8v10h4v35z", "#4e6e7e", true) +
      p("M15 24h4V15h4v14h-8zM27 16h6v12h-6z", "#a8c2c6") +
      p("M16 31h17v13h-5v7h-7v-6h-5z", "#253b4a", true) +
      p("M14 30h8v4h-8zM28 30h8v4h-8z", "#78e5ee") +
      r(20, 37, 2, 7, "#7e9ba5") + r(28, 37, 2, 7, "#7e9ba5") + r(17, 52, 17, 4, "#8aa3ac")],
    MiniPekka: ["rare", "#17416d", "#57adca", () =>
      p("M1 60V43h9v-7h29v8h8v16z", "#36567e", true) +
      p("M9 16h5V9h20v5h6v23h-5v8H15v-7H9z", "#587fa1", true) +
      p("M14 11H9V3h5v5h4v6zM31 10h4V3h5v9h-5v4h-4z", "#8bb6cb", true) +
      p("M13 19h23v4h-3v11h-5v4H15V25h-2z", "#142d4d", true) +
      p("M17 23h15v5h-4v5h-8v-4h-3z", "#60deed") + r(18, 23, 10, 3, "#c4ffff") +
      p("M14 40h20v4H14zM17 47h17v10H17z", "#87adc0") + r(21, 49, 8, 8, "#36769c") +
      p("M2 43h7v14H2zM40 43h6v14h-6z", "#7499b2")],
    Minions: ["common", "#183e6c", "#528faf", () =>
      p("M1 10h4v10h6v8h7v-8h13v8h7v-8h5V10h4v33h-8v4h-8v13H16V47H9v-4H1z", "#246498", true) +
      p("M5 26h4v9h8v7H9v-3H5zM31 35h8v-9h4v13h-4v3h-8z", "#4694bd") +
      p("M13 26V12h4l5 8h6l5-8h4v18h-3v12h-6v7h-9v-7h-6z", "#62b3d2", true) +
      p("M17 18h2v10h-2zM32 18h2v10h-2z", "#a8dae2") +
      p("M16 29h7v4h-7zM28 29h7v4h-7z", "#bf9be1") + r(19, 29, 3, 2, "#f3d2fa") +
      p("M19 37h14v6H19z", "#21436a") + r(20, 37, 3, 4, "#f0f1d3") + r(29, 37, 3, 4, "#f0f1d3")],
    Musketeer: ["rare", "#356c85", "#99c7ca", () =>
      p("M6 60V24h5V13h25v6h6v41z", "#714b88", true) +
      p("M12 24h24v11h-4v9H20v-4h-6z", "#f4bf97", true) +
      p("M10 23V13h5V7h20v5h5v11h4v4H8v-4z", "#648eaa", true) +
      p("M16 10h7v11H12v-7h4zM27 9h6v13h-6z", "#bdd7d7") + r(10, 23, 32, 4, "#90b8c5") +
      p("M12 27h8v5h-4v7h-5zM35 28h6v14h-4v5h-6v-4h4z", "#b784c2") +
      eye(23, 29, "#4384a1") + p("M26 38h8v3h-5v2h-3z", "#b56362") +
      p("M6 53h36v7H6zM5 46h31v8H5z", "#795c49", true) + r(5, 43, 28, 5, "#9cacb2") +
      p("M1 41h8v13H1z", "#4f687b", true) + r(2, 44, 3, 7, "#b8d0d0")],
    Pekka: ["epic", "#423351", "#997eab", () =>
      p("M0 60V45h10v-8h28v8h10v15z", "#36394e", true) +
      p("M8 20h5V10h23v7h5v25h-5v9H14v-7H8z", "#444b68", true) +
      p("M13 13H7V3h6v5h6v8zM33 11h5V3h7v12h-6v6h-6z", "#bc67a3", true) +
      p("M15 13h18v4H19v7h-7v-5h3z", "#8c9db4") +
      p("M13 27h22v17h-6v6H19v-6h-6z", "#171d2e", true) +
      p("M14 28h9v6h-9zM28 28h9v6h-9z", "#f17edc") +
      p("M23 27h4v9h3v12h-4V38h-2v10h-4V36h3z", "#bfccc9") +
      p("M1 48h9v10H1zM38 48h9v10h-9z", "#687a94")],
    Poison: ["epic", "#6b382c", "#c17b43", () =>
      p("M1 44h5v-9h6v4h7v-5h10v6h8v-4h6v9h5v15H0V49h1z", "#de913b") +
      p("M0 52h9v-8h9v5h10v-5h12v8h8v8H0z", "#f1bc55") +
      vial("#df7238", true) + r(22, 32, 8, 16, "#ffad49") +
      p("M35 5h8v3h3v9h-3v5h-6v-5h-3V8h1z", "#9b542e") + r(36, 10, 3, 4, "#653c2e") + r(42, 10, 3, 4, "#653c2e") +
      r(6, 25, 3, 3, "#f4bc64") + r(39, 29, 3, 3, "#f4bc64")],
    Princess: ["legendary", "#326779", "#9ec7bb", () =>
      p("M5 60V25h4V12h8V7h17v7h7v46z", "#463d3a", true) +
      p("M7 60V45h10v-8h16v7h9v16z", "#8291b7", true) +
      p("M14 20h22v8h3v9h-6v6H22v-4h-7z", "#f5c29c", true) +
      p("M12 18h4V9h17v5h6v13h-5V17h-4v6h-7v5h-9z", "#6c5142") +
      p("M16 11h4v8h-4zM23 11h10v3H23z", "#a58160") + eye(25, 29, "#795a50") +
      p("M16 8V2h4v5h6V2h4v6h5v4H15V8z", "#ddba6b", true) + r(24, 8, 3, 3, "#66bfcc") +
      r(23, 38, 9, 2, "#bb746e") + p("M18 43h14v4H18zM24 45h4v10h-4z", "#80cae5") +
      p("M39 22h3v6h2v21h-3v8h-3v-9h3V31h-2z", "#b78152", true) + r(3, 48, 41, 2, "#d8c2a0")],
    Rocket: ["rare", "#4d6669", "#acbca5", () =>
      `<g transform="rotate(-28 24 30)">` + p("M17 35h15v10h-4v8h-4v7h-5V49h-5V39z", "#ee8e37") +
      p("M19 39h9v7h-4v9h-3V44h-2z", "#fff0a3") +
      p("M12 40V22h4V10h4V5h9v5h4v12h4v18h-8v4H19v-4z", "#73887d", true) +
      p("M19 12h11v22H19z", "#c7c9ad") + r(14, 20, 21, 4, "#c1bbb0") + r(14, 32, 21, 4, "#bab6a4") +
      p("M20 8h9v4h-9zM20 25h10v3H20z", "#e6d5aa") +
      p("M13 30H8v12h7V30zM34 30h6v12h-7V30z", "#55695e", true) + "</g>"],
    Skeletons: ["common", "#2c4f70", "#8ca5b2", () =>
      p("M6 60V48h8v-5h20v5h8v12z", "#6c8190", true) +
      p("M16 43h5v17h-5zM28 43h5v17h-5zM11 50h27v3H11zM12 56h24v3H12z", "#d5d3be", true) +
      skull(6, 9, 1.85) + p("M11 15h8v3h-8zM11 19h3v8h-3z", "#fff4d8") +
      p("M38 35h3V24h3v26h-6z", "#c2d0cd", true) + r(39, 48, 3, 11, "#a58952")],
    Tesla: ["common", "#215c81", "#77c2ca", () =>
      p("M11 60l4-29h18l4 29H11z", "#a96f41", true) +
      p("M15 36h4v24h-6zM29 36h4l3 24h-4z", "#dfaa68") +
      p("M17 40h4l12 13v5h-3L16 44zM31 40h-4L16 53v5h3l14-14z", "#6e513b", true) +
      p("M9 25h9V14h13v11h8v11H9z", "#3c8cc2", true) + r(11, 26, 26, 4, "#82c7dc") +
      r(18, 16, 13, 3, "#badadd") + r(18, 21, 13, 3, "#badadd") + r(20, 11, 9, 4, "#8dbac4") +
      bolt(24, 1) + bolt(35, 8) + r(22, 7, 4, 4, "#f0fff0")],
    Tombstone: ["rare", "#315d59", "#8fb9a1", () =>
      p("M4 54h40v6H4zM8 49h31v7H8z", "#567977", true) +
      p("M14 50V32h-4V22h5v6h3V13h5v14h3V8h5v18h3V14h5v20h-4v9h-6v7z", "#8fbcb0", true) +
      p("M17 48V33h5v-5h8v6h4v5h-6v9z", "#d2e0c2") +
      r(19, 15, 3, 12, "#d2e0c2") + r(27, 10, 3, 16, "#d2e0c2") + r(35, 16, 3, 13, "#d2e0c2") +
      p("M16 37h4v5h5v7h-8z", "#568b85") + r(10, 50, 27, 3, "#a6cabb")],
    Wizard: ["rare", "#55556f", "#aaa9b3", () =>
      p("M3 60V36h5V21h6V11h7V6h12v6h7v13h4v35z", "#275681", true) +
      p("M9 31V19h6v-8h18v6h6v15h-6V21H19v10z", "#5c91ae") +
      p("M14 25h20v6h4v9h-5v8H20v-5h-6z", "#d5a17f", true) +
      p("M14 28h5v11h5v4h10v-5h4v8h-5v7H20v-5h-6z", "#624438") +
      p("M18 28h8v3h-8zM30 28h7v3h-7z", "#533e37") + eye(19, 32, "#735d4e") + eye(31, 32, "#735d4e") +
      p("M23 41h12v4H23z", "#342c2c") + r(24, 41, 9, 2, "#f4e5c4") +
      p("M6 22h4v27h7v8H9v-4H6zM36 20h4v27h-6v-5h2z", "#c5c4b5")],
    Xbow: ["epic", "#526c66", "#bac9a6", () =>
      p("M8 60v-7h11V35h11v18h11v7z", "#647c81", true) + r(22, 38, 5, 17, "#c3d0c9") +
      p("M2 28h8v-5h29v5h7v10H35v-5H13v5H2z", "#986540", true) +
      p("M4 27h7v-2h28v2h5v4h-9v-3H13v3H4z", "#d6a668") +
      p("M9 36h5v3h20v-3h5v5H9z", "#d4d8c2") +
      p("M20 43V20h4V7h4v13h4v23z", "#829da4", true) +
      p("M24 8h3v15h-5zM23 25h5v12h-5z", "#d1e0d8") + r(22, 41, 9, 5, "#5d493a")],
    Zap: ["common", "#174d79", "#5cb6ce", () =>
      bolt(1, 11) + bolt(34, 29) + vial("#328ab7", true) +
      p("M24 26h5v8h-4v9h-5v-7h4z", "#96e5e8") +
      p("M36 0h5v7h-5v7h-6v8h-5v-7h5V8h6zM8 38h4v9H8v8H3v-5h2v-7h3z", "#d8ffff") +
      r(17, 3, 3, 3, "#e2ffff") + r(37, 51, 3, 3, "#e2ffff")],
  };

  const cache = new Map();
  function svg(name) {
    if (!Object.hasOwn(ART, name)) return null;
    if (cache.has(name)) return cache.get(name);
    const [, dark, light, draw] = ART[name];
    const art = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 60" aria-hidden="true" focusable="false" shape-rendering="crispEdges">` +
      r(0, 0, 48, 60, dark) +
      p("M0 0h48v29H42v-8h-7v-6H23v5H12v8H5v9H0z", light) +
      p("M3 7h2v2H3zM39 4h3v2h-3zM5 39h2v2H5zM42 45h2v2h-2z", light) +
      draw() + r(0, 0, 48, 1, "#ffffff66") + r(0, 59, 48, 1, ink) + "</svg>";
    cache.set(name, art);
    return art;
  }
  function mount(element, name, fallback = "") {
    const art = svg(name);
    element.classList.toggle("pixel-art", !!art);
    element.setAttribute("aria-hidden", "true");
    if (art) element.innerHTML = art; // Only locally authored, allowlisted SVG enters this sink.
    else element.textContent = fallback;
    const card = element.parentElement;
    if (card) {
      if (art) card.dataset.rarity = ART[name][0];
      else delete card.dataset.rarity;
    }
  }
  return Object.freeze({names: Object.freeze(Object.keys(ART)), svg, mount});
})();
