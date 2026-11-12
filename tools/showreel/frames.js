// Dev-only: step film.html through time in headless Chromium.
//   node frames.js <film.html> --stills <dir> <seconds...>
//   node frames.js <film.html> --video <out.mp4> <fps>
// Called by render.py, which prepares the page.
const { chromium } = require("playwright");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

(async () => {
  const [page_, mode, target, ...rest] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.goto("file://" + path.resolve(page_));
  await page.evaluate(() => document.fonts.ready);
  const duration = await page.evaluate(() => window.DURATION);

  if (mode === "--stills") {
    fs.mkdirSync(target, { recursive: true });
    for (const s of rest) {
      await page.evaluate(t => window.render(t), +s);
      await page.screenshot({ path: path.join(target, `t${(+s).toFixed(2).padStart(5, "0")}.png`) });
    }
  } else {
    const fps = +rest[0], total = Math.round(duration * fps);
    const ff = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(fps), "-i", "-",
      "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", target],
      { stdio: ["pipe", "inherit", "inherit"] });
    for (let f = 0; f < total; f++) {
      await page.evaluate(t => window.render(t), f / fps);
      const png = await page.screenshot({ type: "png" });
      if (!ff.stdin.write(png)) await new Promise(r => ff.stdin.once("drain", r));
      if (f % 300 === 0) console.log(`frame ${f}/${total}`);
    }
    ff.stdin.end();
    const code = await new Promise(r => ff.on("close", r));
    if (code) process.exitCode = code;
    else console.log(target);
  }
  await browser.close();
})();
