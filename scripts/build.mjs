// Builds the whole app into dist/ as a single self-contained index.html.
//
// Everything is inlined (CSS + JS + icons) so the output is one file that can be
// dropped on any static host — surge, Netlify, a USB stick — with no server, no
// build step and no external requests except the Google Fonts stylesheet.
//
//   npm run build     -> dist/index.html + dist/CNAME
//   npm run deploy    -> build, then surge dist alphaagentsystem.surge.sh
//
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import * as esbuild from "esbuild";
import postcss from "postcss";
import tailwindcss from "tailwindcss";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const p = (...parts) => resolve(root, ...parts);

const SURGE_DOMAIN = "alphaagentsystem.surge.sh";
const CLASSES_FILE = p(".tailwind-classes.txt");

const step = (msg) => console.log(`  ${msg}`);

// 1. Extract Tailwind class names ------------------------------------------------
// See tailwind.config.js for why Tailwind can't scan App.jsx directly.
step("extracting Tailwind classes…");
const source = readFileSync(p("App.jsx"), "utf8");
const classes = new Set();
for (const match of source.matchAll(/className=\{?["`]([^"`]*)["`]/g)) {
  for (const token of match[1].split(/\s+/)) {
    if (token && !token.includes("$")) classes.add(token);
  }
}
writeFileSync(CLASSES_FILE, [...classes].sort().join("\n"));
step(`  ${classes.size} classes`);

// 2. Tailwind ---------------------------------------------------------------------
// Run Tailwind through PostCSS in-process rather than shelling out to the CLI:
// on Windows, Node refuses to execFileSync a .cmd shim (EINVAL), so `npx tailwindcss`
// breaks there. No subprocess means no platform-specific launcher at all.
step("building CSS…");
mkdirSync(p("dist"), { recursive: true });
const inputCss = readFileSync(p("input.css"), "utf8");
const { css } = await postcss([tailwindcss({ config: p("tailwind.config.js") })])
  .process(inputCss, { from: p("input.css"), to: undefined });

// 3. Bundle the app ---------------------------------------------------------------
step("bundling JS…");
const bundle = await esbuild.build({
  entryPoints: [p("src-entry.jsx")],
  bundle: true,
  minify: true,
  jsx: "automatic",
  format: "iife",
  write: false,
  logLevel: "silent",
});
const js = bundle.outputFiles[0].text;

// A stray "</script>" inside the bundle would close the tag early and break the
// page, so fail loudly rather than shipping something subtly broken.
if (/<\/script/i.test(js)) throw new Error("bundle contains </script — cannot inline safely");
if (/<\/style/i.test(css)) throw new Error("stylesheet contains </style — cannot inline safely");

// 4. Assemble ---------------------------------------------------------------------
step("writing dist/index.html…");
const html = `<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Alpha Agent System</title>
<style>
html,body{margin:0;padding:0;background:#111113;color-scheme:dark;}
img{max-width:100%}
${css}
</style>
</head>
<body>
<div id="root"></div>
<script>
${js}
</script>
</body>
</html>
`;
writeFileSync(p("dist", "index.html"), html);
writeFileSync(p("dist", "CNAME"), `${SURGE_DOMAIN}\n`);

const kb = (n) => `${Math.round(n / 1024)}KB`;
console.log(`\n✓ dist/index.html  ${kb(html.length)}  (css ${kb(css.length)} · js ${kb(js.length)})`);
console.log(`  deploy with:  npm run deploy`);
