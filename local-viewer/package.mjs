// Generate the CLI's offline assets from the exact website/Python source.
import { mkdir, copyFile, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
const root = resolve(import.meta.dirname, "..");
const target = resolve(root, "cli/alpha_poker_cli/_recap");
const dojo = resolve(root, "cli/alpha_poker_cli/dojo_engine");
await mkdir(dojo, {recursive: true});
await writeFile(resolve(dojo, "__init__.py"), "# Generated from public engine and dojo source.\n");
for (const name of ["engine.py", "evaluator.py", "dojo.py", "summit_policy.py", "dojo_catalog.json"]) {
  await copyFile(resolve(root, `server/alpha_poker/${name}`), resolve(dojo, name));
}
await mkdir(target, {recursive: true});
await writeFile(resolve(target, "__init__.py"), "# Generated shared recap package. Do not edit.\n");
for (const [source, name] of [
  ["server/alpha_poker/evaluator.py", "evaluator.py"],
  ["server/alpha_poker_api/recaps.py", "recaps.py"],
  ["server/alpha_poker_api/recap_chips.py", "recap_chips.py"],
  ["server/alpha_poker_api/recap_equity.py", "recap_equity.py"],
]) {
  const contents = (await readFile(resolve(root, source), "utf8")).replaceAll("from alpha_poker.evaluator import", "from .evaluator import");
  await writeFile(resolve(target, name), contents);
}
await copyFile(resolve(root, "public/robot-avatars.png"), resolve(root, "cli/alpha_poker_cli/viewer/robot-avatars.png"));
await mkdir(resolve(root, "cli/alpha_poker_cli/viewer/characters"), {recursive: true});
for (const name of ["elephant", "bear", "octopus", "bird"]) {
  await copyFile(resolve(root, `public/characters/${name}.webp`), resolve(root, `cli/alpha_poker_cli/viewer/characters/${name}.webp`));
}
await writeFile(resolve(root, "cli/alpha_poker_cli/viewer/THIRD_PARTY_LICENSES.txt"),
  (await Promise.all(["react", "react-dom", "scheduler"].map(async name => `${name}\n${await readFile(resolve(root, `node_modules/${name}/LICENSE`), "utf8")}`))).join("\n\n"));
