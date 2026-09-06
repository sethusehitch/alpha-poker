import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("hand replay return link preserves an exact result recap", async () => {
  const [page, workspace] = await Promise.all([
    readFile(
      new URL("../app/hands/[hand_id]/page.tsx", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../app/components/rivals/RivalsWorkspace.tsx", import.meta.url),
      "utf8",
    ),
  ]);
  assert.match(
    page,
    /searchParams: Promise<\{ rival\?: string; result\?: string \}>/,
  );
  assert.match(page, /rival=\$\{encodeURIComponent\(query\.rival\)\}&result=/);
  assert.match(
    workspace,
    /\?rival=\$\{encodeURIComponent\(data\.challenge\.opponent_username/,
  );
  assert.match(
    workspace,
    /Completed \{time\(data\.challenge\.completed_at\)\}/,
  );
});
