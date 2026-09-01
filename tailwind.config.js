// Tailwind scans .tailwind-classes.txt, not App.jsx directly.
//
// App.jsx is ~800KB and roughly 95% of that is the embedded niche/burial
// inventory data sitting on a handful of enormous single lines. Pointing
// Tailwind's scanner at that file makes it spin at 100% CPU indefinitely.
// scripts/build.mjs pulls every className token out of App.jsx into a small
// text file first, and Tailwind scans that instead — same output, ~200ms.
module.exports = {
  content: [".tailwind-classes.txt"],
  theme: { extend: {} },
  plugins: [],
};
