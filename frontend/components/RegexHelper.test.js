import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

const projectRoot = process.cwd();

async function readProjectFile(relativePath) {
  return readFile(path.join(projectRoot, relativePath), "utf8");
}

test("regex helper is a client component using the generation API", async () => {
  const component = await readProjectFile("components/RegexHelper.js");

  assert.match(component, /"use client";/);
  assert.match(
    component,
    /import \{\s*generateRegexFromDescription,\s*generateRegexFromExamples,\s*\} from "\.\.\/lib\/api";/s,
  );
});

test("regex helper exposes both generation tabs", async () => {
  const component = await readProjectFile("components/RegexHelper.js");

  assert.match(component, /id: "examples", label: "From examples"/);
  assert.match(component, /id: "description", label: "From description"/);
  assert.match(component, /generateRegexFromExamples\(\{ examples \}\)/);
  assert.match(component, /generateRegexFromDescription\(\{ description \}\)/);
});

test("regex helper only applies a regex on explicit confirmation", async () => {
  const component = await readProjectFile("components/RegexHelper.js");

  assert.match(component, /Use this regex/);
  assert.match(
    component,
    /function handleApply\(\) \{\s*if \(result\?\.regex && typeof onApply === "function"\) \{\s*onApply\(result\.regex\);/s,
  );
  assert.match(component, /onClick=\{handleApply\}/);
});

test("regex helper guards against stale in-flight responses", async () => {
  const component = await readProjectFile("components/RegexHelper.js");

  assert.match(component, /requestRef/);
  assert.match(component, /if \(requestRef\.current === token\)/);
});
