// Dev-only: step film.html through time in headless Chromium.
//   node frames.js <film.html> --stills <dir> <seconds...>
//   node frames.js <film.html> --video <out.mp4> <fps> <soundtrack.wav>
//   node frames.js <film.html> --hero <frames dir> <fps> <from> <to>
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
  } else if (mode === "--hero") {
    // Frames for the README's looping animation: the layout scene only, cropped to the
    // diagram and its caption. render.py assembles them.
    const [fps, from, to] = rest.map(Number), total = Math.round((to - from) * fps);
    fs.mkdirSync(target, { recursive: true });
    for (let f = 0; f < total; f++) {
      await page.evaluate(t => window.render(t), from + f / fps);
      await page.screenshot({ path: path.join(target, `${String(f).padStart(4, "0")}.png`),
                              clip: { x: 330, y: 44, width: 1260, height: 960 } });
    }
  } else {
    const fps = +rest[0], audio = rest[1], total = Math.round(duration * fps);
    const ff = spawn("ffmpeg", ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(fps), "-i", "-",
      "-i", audio, "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
      "-c:a", "aac", "-b:a", "192k", "-t", String(duration), "-movflags", "+faststart", target],
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
