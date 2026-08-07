#!/usr/bin/env node
/**
 * Assembles a loadable/packageable extension folder per platform.
 *
 * Chrome and Safari both require every file a manifest references to
 * live inside the extension's own root folder — neither resolves a
 * "../shared/x.js" path that reaches outside it. Since almost all of the
 * code here is intentionally shared between the two platforms (see
 * README.md), a build step is what makes "edit shared/ once" compatible
 * with "each platform gets a self-contained folder": this script copies
 * shared/ plus the chosen platform's manifest.json into dist/<platform>/,
 * which is what you point Chrome's "Load unpacked" at, or feed to
 * Safari's `safari-web-extension-converter`.
 *
 * No dependencies — plain Node `fs`/`path`, so there's nothing to
 * `npm install` before running it.
 *
 * Usage:
 *   node scripts/build.js chrome
 *   node scripts/build.js safari
 *   node scripts/build.js            (builds both)
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const PLATFORMS = ["chrome", "safari"];

function copyDir(src, dest) {
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      fs.mkdirSync(destPath, { recursive: true });
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

function build(platform) {
  const outDir = path.join(ROOT, "dist", platform);
  fs.rmSync(outDir, { recursive: true, force: true });
  fs.mkdirSync(outDir, { recursive: true });

  copyDir(path.join(ROOT, "shared"), outDir);
  fs.copyFileSync(
    path.join(ROOT, platform, "manifest.json"),
    path.join(outDir, "manifest.json")
  );

  console.log(`Built dist/${platform}/`);
}

const requested = process.argv[2];
const targets = requested ? [requested] : PLATFORMS;

for (const platform of targets) {
  if (!PLATFORMS.includes(platform)) {
    console.error(`Unknown platform "${platform}". Expected one of: ${PLATFORMS.join(", ")}`);
    process.exit(1);
  }
  build(platform);
}
