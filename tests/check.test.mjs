// Run with: node --test ~/.claude/skills/plain-language/tests/*.test.mjs
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";
import { findings, loadRules } from "../scripts/check.mjs";
import { countWords, proseUnits, sentences } from "../scripts/prose.mjs";
import { turnText } from "../hooks/transcript.mjs";

const SKILL = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const rules = loadRules();
const ids = (text, mode = "file") => findings(text, rules, { mode }).map((one) => one.id);
const blocking = (text, mode = "file") =>
  findings(text, rules, { mode })
    .filter((one) => one.severity === "block")
    .map((one) => one.id);

describe("reading Markdown as prose", () => {
  it("leaves out fenced code, and turns inline code and URLs into one word each", () => {
    const units = proseUnits("Run `npm run build --workspace a/b` now. See https://example.com/x.\n\n```\nin order to\n```\n");
    assert.deepEqual(
      units.map((unit) => unit.text),
      ["Run CODE now. See URL."],
    );
  });

  it("makes each list item, heading and table cell its own piece", () => {
    const units = proseUnits("# Title\n\n- one\n- two\n  continued\n\n| a | b |\n|---|---|\n| c | d |\n");
    assert.deepEqual(
      units.map((unit) => [unit.kind, unit.text]),
      [
        ["heading", "Title"],
        ["item", "one"],
        ["item", "two continued"],
        ["cell", "a"],
        ["cell", "b"],
        ["cell", "c"],
        ["cell", "d"],
      ],
    );
  });

  it("keeps metadata lines apart, so they are not read as one sentence", () => {
    const units = proseUnits("purpose: Find your record\nrelated: Topic 2\nneeds: Nothing\n");
    assert.equal(units.length, 3);
  });

  it("joins hard-wrapped lines and still knows which line each part came from", () => {
    const [unit] = proseUnits("First line of a sentence\nthat wraps onto line two.");
    assert.equal(unit.text, "First line of a sentence that wraps onto line two.");
    assert.equal(unit.lineAt(unit.text.indexOf("wraps")), 2);
  });

  it("skips front matter, HTML comments and lines marked plain-language-allow", () => {
    const text = "---\ntitle: in order to\n---\n<!--\nin order to\n-->\nIn order to go. <!-- plain-language-allow -->\nKept.";
    assert.deepEqual(
      proseUnits(text).map((unit) => unit.text),
      ["Kept."],
    );
  });

  it("does not end a sentence at e.g. or a version number", () => {
    assert.equal(sentences("Use a tool, e.g. Make. Version 1.2 works. Done.").length, 3);
  });

  it("counts a word only when it has a letter or a digit in it", () => {
    assert.equal(countWords("A — B (C) + 4"), 4);
  });
});

describe("phrase rules", () => {
  const cases = [
    ["wordy", "We did this in order to test it."],
    ["smothered-verb", "We need to make a decision today."],
    ["hidden-actor", "It was decided that the job stops."],
    ["throat-clearing", "It is worth noting that the job stops."],
    ["flattery-or-filler-closer", "Great question. The job stops."],
    ["cliche", "This is low-hanging fruit."],
    ["idiom", "These tests are load-bearing."],
    ["shorthand", "Run it w/ the flag."],
    ["arrow", "The value goes from 1 → 2."],
    ["stacked-hedge", "This could potentially fail."],
    ["negative-contraction", "It doesn't work."],
    ["date-format", "It ran on October 21, 2026."],
    ["inclusive-language", "Add it to the whitelist."],
    ["figurative", "Each claim rests on these measurements."],
    ["figurative", "New pull requests drove the cost."],
    ["figurative", "The smaller figure strengthens the case for skipping it."],
    ["symbol-shorthand", "The cost is ≈ $3,300."],
    ["symbol-shorthand", "The cost is $3.3k a month."],
    ["symbol-shorthand", "That is a 22× jump."],
    ["symbol-shorthand", "Compare light vs heavy jobs."],
    ["month-abbreviation", "The cuts are live by 1 Nov."],
    ["govuk-words-to-avoid", "We will liaise with the team."],
    ["govuk-tone", "Please note that the job stops."],
    ["govuk-tone", "The member can do it if he or she wants."],
    ["govuk-tone", "You should've run it first."],
  ];
  for (const [rule, text] of cases) {
    it(`blocks ${rule}`, () => assert.ok(blocking(text, "chat").includes(rule), `${rule} not found in: ${text}`));
  }

  it("does not block plain text", () => {
    assert.deepEqual(blocking("The job stops at midnight. You can start it again from the settings page.", "chat"), []);
  });

  it("does not check words inside quotation marks or inline code", () => {
    assert.deepEqual(blocking('Write "to", not "in order to". Leave `in order to` alone.', "chat"), []);
    assert.deepEqual(blocking("Write 'to', not 'in order to'.", "chat"), []);
  });

  it("does not read an apostrophe as a quotation mark", () => {
    assert.ok(blocking("The member's record doesn't change.", "chat").includes("negative-contraction"));
  });

  it("does not report a literal use that the pattern excludes", () => {
    assert.ok(!ids("Print it in landscape orientation.").includes("figurative-jargon"));
  });
});

describe("sentence and paragraph rules", () => {
  const long = `${Array.from({ length: 26 }, (_, i) => `word${i}`).join(" ")}.`;

  it("blocks a sentence over 25 words, and allows one of 25", () => {
    assert.ok(blocking(long).includes("long-sentence"));
    const ok = `${Array.from({ length: 25 }, (_, i) => `word${i}`).join(" ")}.`;
    assert.ok(!blocking(ok).includes("long-sentence"));
  });

  it("measures each list item on its own", () => {
    const items = Array.from({ length: 6 }, (_, i) => `- Item ${i} has six words here`).join("\n");
    assert.deepEqual(blocking(items), []);
  });

  it("blocks a paragraph of six sentences, but not a list of six items", () => {
    assert.ok(blocking("One. Two. Three. Four. Five. Six.").includes("long-paragraph"));
    assert.ok(!blocking("- One.\n- Two.\n- Three.\n- Four.\n- Five.\n- Six.").includes("long-paragraph"));
  });

  it("blocks an aside of five words or more in the middle of a sentence", () => {
    assert.ok(blocking("The job stops — unless somebody has paused it first — at midnight.").includes("aside-interrupts-sentence"));
    assert.ok(blocking("The job stops (unless somebody has paused it first) at midnight.").includes("aside-interrupts-sentence"));
  });

  it("does not block a short aside, a dash that ends a sentence, or a pair across two sentences", () => {
    assert.deepEqual(blocking("The job (nightly) stops at midnight."), []);
    assert.deepEqual(blocking("The job stops at midnight — every night."), []);
    assert.deepEqual(blocking("One part — a short clause. Then another sentence starts — and ends here."), []);
  });
});

describe("advice", () => {
  it("reports an abbreviation that is never spelled out, once", () => {
    const found = findings("The FFR report and the FFR view.", rules).filter((one) => one.id === "undefined-abbreviation");
    assert.equal(found.length, 1);
  });

  it("does not report an abbreviation spelled out in the text, or a known one", () => {
    assert.ok(!ids("Fit for Role (FFR) matters. The FFR view.").includes("undefined-abbreviation"));
    assert.ok(!ids("Read the API docs and the JSON file.").includes("undefined-abbreviation"));
  });

  it("reports a shouted word as shouting, not as an abbreviation", () => {
    const found = ids("You MUST run it.");
    assert.ok(found.includes("shouted-word"));
    assert.ok(!found.includes("undefined-abbreviation"));
  });

  it("never blocks on advice", () => {
    assert.deepEqual(blocking("This is very clear: 3x faster & simpler.", "chat"), []);
  });

  it("allows a short month name inside a table, and nowhere else", () => {
    const table = "| Month | Cost |\n|---|---:|\n| Sep | 189 |\n| Oct | 3865 |\n";
    assert.ok(!blocking(table).includes("month-abbreviation"));
  });

  it("reports a fragment with no subject, and not a whole sentence that starts the same way", () => {
    assert.ok(ids("Checking the filter now.", "chat").includes("no-subject"));
    assert.ok(!ids("Getting under $1,000 means a 74% cut.", "chat").includes("no-subject"));
    assert.ok(!ids("Nothing changes.", "chat").includes("no-subject"));
  });
});

describe("rules from the user's review of round two", () => {
  const blocked = [
    ["two-ideas-in-one-sentence", "A light job is one small enough for GitHub's runners, which cost nothing."],
    ["two-ideas-in-one-sentence", "Six decisions are made and eight are waiting on you."],
    ["thing-given-person-verb", "`.github/CONTEXT.md` is new and holds the CI glossary."],
    ["thing-given-person-verb", "`CONTEXT-MAP.md` gains one link to it."],
    ["thing-given-person-verb", "The function knows which row to read."],
    ["condition-after-instruction", "Tell me where you would like it kept if you need it."],
    ["figurative", "The stack repository is on pace to spend $4,000."],
  ];
  for (const [rule, text] of blocked) {
    it(`blocks ${rule}: ${text}`, () => assert.ok(blocking(text, "chat").includes(rule)));
  }

  const allowed = [
    "A member holds the Boat Operator capability.",
    "Done when someone who reads the first paragraph knows what it says.",
    "Check if your code is incorrect, or if it has expired.",
    "Read a record Slipstream has nothing in, and know what to do about it.",
    "Topic 3 covers what a capability is, and what an assessment is.",
    "Use a technical term only if the reader already uses it.",
    "Write must for a rule that has consequences if it is broken.",
  ];
  for (const text of allowed) {
    it(`allows: ${text}`, () => assert.deepEqual(blocking(text, "chat"), []));
  }

  it("asks for a comma after an opening clause, and not in a question", () => {
    assert.ok(blocking("If you need it tell me where to keep it.", "chat").includes("comma-after-opening-clause"));
    assert.deepEqual(blocking("If you need it, tell me where to keep it.", "chat"), []);
    assert.deepEqual(blocking("When does the nightly job run?", "chat"), []);
  });

  it("asks for a serial comma in a list, and not in a phrase or a name", () => {
    assert.ok(blocking("It covers words, headings and links.", "chat").includes("serial-comma"));
    assert.deepEqual(blocking("It covers words, headings, and links.", "chat"), []);
    assert.deepEqual(blocking("An assessment can have a level, such as Lift and Shift Level 2.", "chat"), []);
    assert.deepEqual(blocking("Your row shows it as Paused, with your reason and the date.", "chat"), []);
    assert.deepEqual(blocking("Comment on a line, or select lines and suggest a change.", "chat"), []);
    assert.deepEqual(blocking("Eight test inputs, run before and after the change.", "chat"), []);
    assert.deepEqual(blocking("I checked the page, before and after the change.", "chat"), []);
    assert.ok(!blocking("The report, written last week and sent today, lists the results.", "chat").includes("serial-comma"));
  });
});

describe("structure rules", () => {
  it("blocks a heading that is a question", () => {
    assert.ok(blocking("## Which members have no unit?\n\nText.").includes("heading-is-a-question"));
  });

  it("blocks a heading that skips a level, and allows going back up", () => {
    assert.ok(blocking("## One\n\n#### Two\n").includes("heading-level-skipped"));
    assert.ok(!blocking("## One\n\n### Two\n\n## Three\n").includes("heading-level-skipped"));
  });

  it("reports percentages that add up to more than the whole, even with notes in the cells", () => {
    const table = [
      "| Slice | Share of cost |",
      "|---|---:|",
      "| Pull requests | 89% |",
      "| 16-vCPU runners | 76% |",
      "| Test EQL | 52% ($1,700 a month) |",
    ].join("\n");
    assert.ok(ids(table).includes("parts-exceed-whole"));
    const whole = "| Part | Share |\n|---|---:|\n| A | 60% |\n| B | 30% |\n| C | 10% |\n";
    assert.ok(!ids(whole).includes("parts-exceed-whole"));
  });

  it("reports a column of numbers that is not right-aligned, and an empty cell", () => {
    const found = ids("| Repo | Cost |\n|---|---|\n| stack | 3865 |\n| proxy |  |\n| suite | 67 |\n");
    assert.ok(found.includes("empty-table-cell"));
    assert.ok(ids("| Repo | Cost |\n|---|---|\n| stack | 3865 |\n| proxy | 325 |\n").includes("numbers-not-right-aligned"));
  });

  it("reports the same link text going to two places", () => {
    assert.ok(ids("See [the guide](a.md) and [the guide](b.md).").includes("link-text-reused"));
  });
});

describe("the command line", () => {
  const cli = path.join(SKILL, "scripts", "check.mjs");

  it("exits 1 when something must be fixed, and 0 when nothing must", () => {
    const bad = spawnSync("node", [cli, "--chat"], { input: "We did it in order to test it." });
    assert.equal(bad.status, 1);
    const good = spawnSync("node", [cli, "--chat"], { input: "We did it to test it." });
    assert.equal(good.status, 0);
  });

  it("passes its own skill files", () => {
    const files = ["SKILL.md", "core.md", "references/guidelines.md"].map((file) => path.join(SKILL, file));
    const out = JSON.parse(execFileSync("node", [cli, "--json", ...files], { encoding: "utf8" }));
    assert.equal(out.mustFix, 0);
  });
});

describe("the hooks", () => {
  const entry = (type, content, extra = {}) => JSON.stringify({ type, message: { content }, ...extra });

  it("reads every text block Claude wrote since the person's last message", () => {
    const transcript = [
      entry("user", "first question"),
      entry("assistant", [{ type: "text", text: "Old answer." }]),
      entry("user", [{ type: "text", text: "second question" }]),
      entry("assistant", [{ type: "thinking", thinking: "in order to" }]),
      entry("assistant", [{ type: "text", text: "Part one." }]),
      entry("user", [{ type: "tool_result", content: "output" }]),
      entry("user", [{ type: "text", text: "skill text" }], { isMeta: true }),
      entry("assistant", [{ type: "text", text: "Part two." }]),
    ].join("\n");
    assert.equal(turnText(transcript), "Part one.\n\nPart two.");
  });

  function runHook(name, event) {
    return spawnSync("node", [path.join(SKILL, "hooks", name)], { input: JSON.stringify(event), encoding: "utf8" });
  }

  it("the Stop hook sends a reply back once, and lets it through the second time", () => {
    const dir = mkdtempSync(path.join(tmpdir(), "plain-language-"));
    const transcript = path.join(dir, "t.jsonl");
    writeFileSync(transcript, [entry("user", "q"), entry("assistant", [{ type: "text", text: "It doesn't work." }])].join("\n"));
    const first = runHook("stop-guard.mjs", { transcript_path: transcript, stop_hook_active: false });
    assert.equal(JSON.parse(first.stdout).decision, "block");
    const second = runHook("stop-guard.mjs", { transcript_path: transcript, stop_hook_active: true });
    assert.equal(second.stdout, "");
  });

  it("the Stop hook checks last_assistant_message, which the transcript may not have yet", () => {
    const dir = mkdtempSync(path.join(tmpdir(), "plain-language-"));
    const transcript = path.join(dir, "t.jsonl");
    writeFileSync(transcript, entry("user", "q"));
    const result = runHook("stop-guard.mjs", { transcript_path: transcript, last_assistant_message: "Under the hood, it doesn't work." });
    assert.equal(JSON.parse(result.stdout).decision, "block");
    const missing = runHook("stop-guard.mjs", { transcript_path: "/nonexistent/t.jsonl", last_assistant_message: "It does not work." });
    assert.equal(missing.stdout, "");
  });

  it("the Stop hook stays quiet when the transcript is missing", () => {
    const result = runHook("stop-guard.mjs", { transcript_path: "/nonexistent/t.jsonl" });
    assert.equal(result.status, 0);
    assert.equal(result.stdout, "");
  });

  it("the file hook checks only the paragraph an Edit touched", () => {
    const dir = mkdtempSync(path.join(tmpdir(), "plain-language-"));
    const file = path.join(dir, "doc.md");
    writeFileSync(file, "Old text, in order to stay.\n\nNew text is fine.\n");
    const clean = runHook("file-guard.mjs", { tool_name: "Edit", tool_input: { file_path: file, new_string: "New text is fine." } });
    assert.equal(clean.stdout, "");
    const dirty = runHook("file-guard.mjs", { tool_name: "Write", tool_input: { file_path: file } });
    assert.equal(JSON.parse(dirty.stdout).decision, "block");
  });

  it("the file hook ignores code files and files that switch it off", () => {
    const dir = mkdtempSync(path.join(tmpdir(), "plain-language-"));
    const code = path.join(dir, "a.ts");
    writeFileSync(code, "// in order to\n");
    assert.equal(runHook("file-guard.mjs", { tool_name: "Write", tool_input: { file_path: code } }).stdout, "");
    const off = path.join(dir, "rules.md");
    writeFileSync(off, "<!-- plain-language-check: off -->\nin order to\n");
    assert.equal(runHook("file-guard.mjs", { tool_name: "Write", tool_input: { file_path: off } }).stdout, "");
  });

  it("the session hook adds core.md, for a session and for a subagent", () => {
    const session = JSON.parse(runHook("session-start.mjs", { hook_event_name: "SessionStart" }).stdout);
    assert.match(session.hookSpecificOutput.additionalContext, /^# Plain language/);
    const subagent = JSON.parse(runHook("session-start.mjs", { hook_event_name: "SubagentStart" }).stdout);
    assert.equal(subagent.hookSpecificOutput.hookEventName, "SubagentStart");
  });
});
