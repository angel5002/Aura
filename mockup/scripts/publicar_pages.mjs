// publicar_pages.mjs — publica la app compilada en GitHub Pages (rama gh-pages de origin).
//
//   npm run build && node scripts/publicar_pages.mjs
//
// Incluye la reproducción K002 (datos/k002_reproduccion.json: señal del detector derivada de la prueba en casa, sin
// video ni nombres), con autorización de Deisy del 29/10/2026 (es parte importante de la visualización).
// Trabaja en una carpeta temporal del sistema: clona gh-pages si ya existe (o la crea vacía), reemplaza su contenido
// por app/ + .nojekyll y sube un commit nuevo con un push normal (sin --force: no reescribe historia). No toca main.
import { execFileSync } from "node:child_process";
import { cpSync, existsSync, mkdtempSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const MOCKUP = resolve(fileURLToPath(import.meta.url), "..", "..");
const APP = join(MOCKUP, "app");
if (!existsSync(join(APP, "index.html"))) { console.error("Falta app/: correr antes npm run build"); process.exit(1); }

const ENV = { ...process.env, GIT_TERMINAL_PROMPT: "0" };
const git = (args, cwd) => execFileSync("git", args, { cwd, encoding: "utf8", env: ENV }).trim();
const origen = git(["remote", "get-url", "origin"], MOCKUP);
const commit = git(["rev-parse", "--short", "HEAD"], MOCKUP);
const existe = git(["ls-remote", "--heads", origen, "gh-pages"], MOCKUP) !== "";
const dir = mkdtempSync(join(tmpdir(), "aura-pages-"));
try {
  if (existe) git(["clone", "-q", "--depth", "1", "--branch", "gh-pages", origen, "."], dir);
  else git(["init", "-q", "-b", "gh-pages"], dir);
  for (const f of readdirSync(dir)) if (f !== ".git") rmSync(join(dir, f), { recursive: true, force: true });
  cpSync(APP, dir, { recursive: true });
  writeFileSync(join(dir, ".nojekyll"), "");
  git(["add", "-A"], dir);
  if (!git(["status", "--porcelain"], dir)) { console.log("sin cambios: gh-pages ya tiene esta compilación"); process.exit(0); }
  git(["-c", "user.name=hjdeisy", "-c", "user.email=ong.mpsa@gmail.com", "commit", "-q", "-m",
    `Mockup AURA compilado desde ${commit}\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`], dir);
  console.log(git(["ls-files"], dir).split("\n").length, "archivos; K002:", existsSync(join(dir, "datos", "k002_reproduccion.json")) ? "incluida" : "no está");
  execFileSync("git", ["push", "-q", origen, "gh-pages:gh-pages"], { cwd: dir, stdio: "inherit", env: ENV });
  console.log(`publicado en ${origen} (rama gh-pages) desde ${commit}`);
} finally {
  rmSync(dir, { recursive: true, force: true });
}
