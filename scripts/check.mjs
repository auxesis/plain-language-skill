#!/usr/bin/env node
// Checks prose against the plain-language rules in rules.json, and reports each
// problem with the line it is on, the ISO 24495 clause it breaks, and what to write
// instead.
//
// Usage:
//   node check.mjs [--json] [--block-only] [--chat] [file ...]
//
// With no file, it reads standard input. It exits 1 when there is a finding that
// must be fixed, and 0 otherwise, so it can sit in a script or a hook.
//
// It checks what a machine can check: word lists, sentence and paragraph length,
// asides that interrupt a sentence. It cannot decide whether the reader needs a
// sentence at all (ISO 24495-1 Principle 1), whether a word is familiar to this
// reader, or whether a metaphor that is not on the list is a metaphor. Those stay
// with the writer.
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { countWords, PLACEHOLDERS, proseUnits, sentences } from "./prose.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));

export function loadRules(file = path.join(HERE, "rules.json")) {
  const raw = JSON.parse(readFileSync(file, "utf8"));
  const compile = (rule) => {
    const flags = `g${rule.flags ?? "i"}`;
    const items = rule.items
      ? rule.items.map((item) => ({ re: new RegExp(item.pattern, flags), instead: item.instead }))
      : rule.patterns.map((pattern) => ({ re: new RegExp(pattern, flags) }));
    return { ...rule, items };
  };
  const tv = raw.thingVerbs;
  const between = `(?:(?:${tv.between})\\s+){0,3}`;
  return {
    limits: raw.limits,
    known: new Set(raw.knownAbbreviations),
    shouted: new Set(raw.shoutedWords),
    phrases: raw.phrases.map(compile),
    source: raw.sourcePatterns.map(compile),
    thingVerbs: {
      ...tv,
      subjects: [
        new RegExp(`\\b(?:${tv.things.join("|")})\\s+${between}(${tv.blockVerbs})\\b`, "gi"),
        new RegExp(`\\b(?:${tv.pronouns.join("|")})\\s+${between}(${tv.pronounVerbs})\\b`, "gi"),
      ],
      held: new RegExp(`\\b(?:${tv.blockVerbs})\\s+(?:${tv.heldThings.join("|")})\\b`, "gi"),
      thingSubject: new RegExp(`^\\s*(?:(?:the|a|an|this|that|each|every|its|our|your|their|one|new)\\s+)?(?:[\\w-]+\\s+){0,2}?(?:${tv.things.join("|")})\\b`, "i"),
      anyVerb: new RegExp(`\\b(?:${tv.pronounVerbs})\\b`, "i"),
      person: new RegExp(tv.person, "i"),
    },
  };
}

const PROSE_KINDS = new Set(["paragraph", "item"]);

function excerptAround(piece, index) {
  const all = sentences(piece.text);
  const sentence = all.findLast((one) => one.offset <= index) ?? all[0];
  const text = (sentence?.text ?? piece.text).trim();
  return text.length > 160 ? `${text.slice(0, 157)}...` : text;
}

function lastLine(piece) {
  return piece.segments.at(-1)?.line ?? piece.line;
}

function finding(rule, piece, index, say) {
  return {
    id: rule.id,
    severity: rule.severity,
    clause: rule.clause,
    line: piece.lineAt(index),
    span: [piece.line, lastLine(piece)],
    excerpt: excerptAround(piece, index),
    say,
  };
}

function phraseFindings(piece, rules) {
  const found = [];
  for (const rule of rules.phrases) {
    if (rule.skipKinds?.includes(piece.kind) || rule.scope === "sentence") continue;
    for (const item of rule.items) {
      item.re.lastIndex = 0;
      let match;
      while ((match = item.re.exec(piece.masked))) {
        const say = rule.say.replace("{instead}", item.instead ?? "");
        found.push({ ...finding(rule, piece, match.index, say), match: match[0].trim() });
        if (match[0] === "") item.re.lastIndex++;
      }
    }
  }
  return found;
}

// A thing given a person's verb: "the table holds a flag", "CODE gains one link". The
// subject decides, so "a member holds a capability" is literal and is not reported.
function thingVerbFindings(piece, sentence, masked, rules) {
  const tv = rules.thingVerbs;
  const rule = { id: "thing-given-person-verb", severity: "block", clause: tv.clause };
  const found = [];
  for (const re of tv.subjects) {
    re.lastIndex = 0;
    let match;
    while ((match = re.exec(masked))) {
      const upToVerb = masked.slice(0, match.index + match[0].length - match[1].length);
      if (tv.person.test(upToVerb)) continue;
      found.push({ ...finding(rule, piece, sentence.offset + match.index, tv.say), match: match[0] });
    }
  }
  tv.held.lastIndex = 0;
  let match;
  while ((match = tv.held.exec(masked))) {
    found.push({ ...finding(rule, piece, sentence.offset + match.index, tv.say), match: match[0] });
  }
  // The subject is a thing and the verb comes later: "CODE is new and holds the glossary".
  if (!found.length && tv.thingSubject.test(masked)) {
    const later = tv.anyVerb.exec(masked);
    if (later && !tv.person.test(masked.slice(0, later.index + later[0].length))) {
      found.push({ ...finding(rule, piece, sentence.offset + later.index, tv.say), match: later[0] });
    }
  }
  return found;
}

// Two clauses in one sentence: ", which" adding a second statement, or "and" joining two
// clauses that each have a verb, as in "Six decisions are made and eight are waiting".
const HELPING_VERB = "(?:is|are|was|were|has|have|had|will|can|cannot|could|must|should|would|does|do|did)";
const JOINED_CLAUSE = new RegExp(
  `\\s(and|but)\\s+(?!(?:what|which|who|whom|whose|where|when|why|how|whether|that|if)\\b)(?:\\S+\\s+){0,3}?(?<!\\bto\\s)${HELPING_VERB}\\b`,
  "g",
);

function twoIdeasFindings(piece, sentence, masked) {
  const rule = { id: "two-ideas-in-one-sentence", severity: "block", clause: "1: 5.3.4 a)" };
  const found = [];
  const which = /,\s+which\b/.exec(masked);
  if (which) {
    found.push(
      finding(rule, piece, sentence.offset + which.index, "\", which\" adds a second idea to this sentence. Make it a sentence of its own."),
    );
  }
  JOINED_CLAUSE.lastIndex = 0;
  let match;
  while ((match = JOINED_CLAUSE.exec(masked))) {
    const before = masked.slice(0, match.index);
    if (!new RegExp(`\\b${HELPING_VERB}\\b`).test(before)) continue;
    found.push(
      finding(rule, piece, sentence.offset + match.index, `"${match[1]}" joins two statements. Write two sentences: "Six decisions are made. Eight are waiting for you."`),
    );
    break;
  }
  return found;
}

// House style: a comma after an opening "If" or "When" clause, and a serial comma
// before the "and" or "or" that ends a list of three or more.
const OPENING_CLAUSE = /^\s*(?:If|When|Whenever|Unless|Once|Because|Although|Though|While|After|Before|Since|Until)\b/;
const LIST_END = /([\p{L}\p{N}][\p{L}\p{N}'’-]*(?:\s[\p{L}\p{N}'’-]+){0,3}),\s([\p{L}\p{N}][\p{L}\p{N}'’-]*(?:\s[\p{L}\p{N}'’-]+){0,3})\s(and|or)\s[\p{L}\p{N}]/gu;
const CLAUSE_WORDS = /\b(?:I|you|we|they|it|he|she|is|are|was|were|has|have|had|will|can|cannot|do|does|did|must|should|would|could)\b/;
// A phrase after the comma, not a list item: "with your reason and the date", "such as Lift and Shift".
const NOT_AN_ITEM = /^(?:and|or|nor|with|without|by|for|from|in|on|at|to|into|onto|of|as|then|so|but|which|who|whom|where|when|while|such|including|like|especially|plus|except|both|either|neither|each|every|not|only|also|even)\b|^[\p{L}]+(?:ed|ing)\b/iu;
// A past participle that is not regular: "inputs, run before the change", "the report, written last week".
const IRREGULAR_PARTICIPLE = /^(?:run|made|done|given|taken|written|shown|seen|found|kept|left|sent|built|held|known|told|brought|bought|paid|led|lost|won|begun|chosen|drawn|driven|broken|spoken|thrown|hidden|grown)\b/iu;
// A pair of words joined by "and" or "or", not the end of a list: "before and after", "in and out".
const PAIRED_WORDS = new Set(["before", "after", "in", "out", "up", "down", "on", "off", "over", "under", "back", "forth", "to", "from", "above", "below", "inside", "outside", "here", "there"]);

function commaFindings(piece, sentence, masked) {
  const found = [];
  const trimmed = masked.trim();
  if (OPENING_CLAUSE.test(trimmed) && !trimmed.includes(",") && !trimmed.endsWith("?") && countWords(trimmed) > 4) {
    found.push(
      finding(
        { id: "comma-after-opening-clause", severity: "block", clause: "house style; 1: 5.3.3 d)" },
        piece,
        sentence.offset,
        "Put a comma after the opening clause: \"If you need it, tell me where to keep it.\"",
      ),
    );
  }
  LIST_END.lastIndex = 0;
  let match;
  while ((match = LIST_END.exec(masked))) {
    const firstComma = masked.indexOf(",");
    const commaAt = match.index + match[1].length;
    if (OPENING_CLAUSE.test(trimmed) && commaAt === firstComma) continue;
    if (CLAUSE_WORDS.test(match[2]) || NOT_AN_ITEM.test(match[2]) || IRREGULAR_PARTICIPLE.test(match[2]) || countWords(match[2]) > 3) continue;
    const before = match[2].split(/\s+/).pop().toLowerCase();
    const after = (masked.slice(match.index + match[0].length - 1).match(/^[\p{L}]+/u) || [""])[0].toLowerCase();
    if (PAIRED_WORDS.has(before) && PAIRED_WORDS.has(after)) continue;
    found.push(
      finding(
        { id: "serial-comma", severity: "block", clause: "house style; 1: 5.3.3 d)" },
        piece,
        sentence.offset + match.index,
        `Put a comma before "${match[3]}" at the end of a list: "words, headings, and links".`,
      ),
    );
    break;
  }
  return found;
}

function sentencePhraseFindings(piece, sentence, masked, rules) {
  const found = [];
  for (const rule of rules.phrases.filter((one) => one.scope === "sentence")) {
    for (const item of rule.items) {
      item.re.lastIndex = 0;
      const match = item.re.exec(masked.trim());
      if (match) found.push({ ...finding(rule, piece, sentence.offset, rule.say), match: match[0].slice(0, 60) });
    }
  }
  return found;
}

const ASIDE_RULE = {
  id: "aside-interrupts-sentence",
  severity: "block",
  clause: "1: 5.3.3 a) 3)",
};
const ASIDES = [
  /\S\s+[—–]\s*((?:[^\s—–()]+\s+){4,}[^\s—–()]+)\s*[—–]\s+\S/g,
  /\S\s+\(((?:[^\s—–()]+\s+){4,}[^\s—–()]+)\)\s+\S/g,
];

// A sentence that opens with an -ing word and has no subject or helping verb, such as
// "Checking the filter now." A sentence like "Running setup rebuilds the package" is
// whole, and this cannot always tell the two apart, so it only advises.
const AUXILIARY = /\b(?:is|are|was|were|be|been|has|have|had|does|do|did|can|could|will|would|should|must|may|might|I|we|you|it|they|he|she)\b/i;
const ING_NOUNS = /^(?:Nothing|Anything|Something|Everything|Training|Testing|Pricing|Billing|Logging|Hosting|Morning|Evening|Spring|String|Thing)\b/;
// Verbs that often follow an -ing subject: "Getting under $1,000 means a 74% cut."
const COMMON_VERBS = /\b(?:means|removes|triples|doubles|halves|costs|takes|accepts|makes|needs|saves|shows|helps|stops|breaks|leaves|gives|adds|keeps|changes|marks|deletes|fails|rebuilds|stays|works|uses|causes|cuts|reduces|increases|affects|depends|requires|lets|puts|turns|moves|returns|sends|tells|matters|wins|beats|avoids|prevents|fixes|catches|misses|skips|runs)\b/;

function isFragment(text) {
  const trimmed = text.trim();
  if (!/^[A-Z][a-z]+ing\b/.test(trimmed) || ING_NOUNS.test(trimmed)) return false;
  return !AUXILIARY.test(trimmed) && !COMMON_VERBS.test(trimmed);
}

function sentenceFindings(piece, rules) {
  const found = [];
  const { sentenceWords } = rules.limits;
  for (const sentence of sentences(piece.text)) {
    const words = countWords(sentence.text);
    if (words > sentenceWords) {
      found.push(
        finding(
          { id: "long-sentence", severity: "block", clause: "1: 5.3.4 a), c)" },
          piece,
          sentence.offset,
          `This sentence has ${words} words; the limit is ${sentenceWords}. Cut words first. Split it only if it still has more than one idea.`,
        ),
      );
    }
    const masked = piece.masked.slice(sentence.offset, sentence.offset + sentence.text.length);
    found.push(
      ...thingVerbFindings(piece, sentence, masked, rules),
      ...twoIdeasFindings(piece, sentence, masked),
      ...commaFindings(piece, sentence, masked),
      ...sentencePhraseFindings(piece, sentence, masked, rules),
    );
    for (const re of ASIDES) {
      re.lastIndex = 0;
      const match = re.exec(masked);
      if (!match) continue;
      found.push(
        finding(
          ASIDE_RULE,
          piece,
          sentence.offset + match.index,
          "This aside cuts the sentence in half. Make it a sentence of its own, after this one, or delete it.",
        ),
      );
    }
    if (isFragment(sentence.text)) {
      found.push(
        finding(
          { id: "no-subject", severity: "advise", clause: "1: 5.3.3 a), c)" },
          piece,
          sentence.offset,
          "This looks like a fragment with no subject. Say who is doing it: \"I am checking the filter\", not \"Checking the filter\".",
        ),
      );
    }
    if (/;\s+[a-z]/.test(masked)) {
      found.push(
        finding(
          { id: "semicolon-joins-ideas", severity: "advise", clause: "1: 5.3.4 a)" },
          piece,
          sentence.offset,
          "A semicolon joins two ideas into one sentence. Make two sentences, or a list.",
        ),
      );
    }
  }
  return found;
}

function paragraphFindings(piece, rules) {
  const { paragraphSentences } = rules.limits;
  const count = sentences(piece.text).length;
  if (piece.kind !== "paragraph" || count <= paragraphSentences) return [];
  return [
    finding(
      { id: "long-paragraph", severity: "block", clause: "1: 5.3.5 a)" },
      piece,
      0,
      `This paragraph has ${count} sentences; the limit is ${paragraphSentences}. A paragraph is one topic. Split it where the topic changes, or turn a run of parallel points into a list.`,
    ),
  ];
}

const GENERIC_HEADING = /^(?:introduction|overview|background|miscellaneous|misc|general|other|details|notes|further reading|more information|useful links|see also)$/i;

function headingFindings(piece, rules) {
  if (piece.kind !== "heading") return [];
  const found = [];
  const words = countWords(piece.text);
  if (words > rules.limits.headingWords) {
    found.push(
      finding(
        { id: "long-heading", severity: "advise", clause: "1: 5.2.4 d)" },
        piece,
        0,
        `This heading has ${words} words. Keep a heading short enough to scan.`,
      ),
    );
  }
  if (/\?\s*$/.test(piece.text)) {
    found.push(
      finding(
        { id: "heading-is-a-question", severity: "block", clause: "GOV.UK: clear structure; 1: 5.2.4 b)" },
        piece,
        0,
        "A heading is a statement, not a question: readers want answers. Write \"Find members who have no unit\", not \"Which members have no unit?\".",
      ),
    );
  }
  if (GENERIC_HEADING.test(piece.text.trim().replace(/[:.]$/, ""))) {
    found.push(
      finding(
        { id: "generic-heading", severity: "advise", clause: "GOV.UK: clear structure; 1: 5.2.4 b)" },
        piece,
        0,
        "This heading does not say what the section contains. Name the topic, or start with a verb for a task.",
      ),
    );
  }
  return found;
}

// Words ending in -ion, -ment, -ance or -ence are usually verbs turned into nouns.
// Three in one sentence make it slow to read.
function nounHeavyFindings(piece) {
  const found = [];
  for (const sentence of sentences(piece.text)) {
    const nouns = sentence.text.match(/\b[a-z]{3,}(?:tion|sion|ment|ance|ence)s?\b/gi) ?? [];
    if (nouns.length < 3) continue;
    found.push(
      finding(
        { id: "noun-heavy", severity: "advise", clause: "GOV.UK: clear language; 1: 5.3.4 b)" },
        piece,
        sentence.offset,
        `This sentence has ${nouns.length} nouns made from verbs (${nouns.slice(0, 4).join(", ")}). Turn some back into verbs and name who does them.`,
      ),
    );
  }
  return found;
}

function shoutedFindings(piece, rules) {
  const found = [];
  for (const match of piece.masked.matchAll(/\b[A-Z]{2,}(?:['’][A-Z]+)?\b/g)) {
    if (!rules.shouted.has(match[0].replace(/['’]/g, ""))) continue;
    found.push(
      finding(
        { id: "shouted-word", severity: "advise", clause: "1: 5.2.3 a) 1), 5.3.7" },
        piece,
        match.index,
        `"${match[0]}" in capitals reads as shouting. Explain why the rule matters instead, or use bold for the one thing that must stand out.`,
      ),
    );
  }
  return found;
}

const ROMAN = /^(?=[MDCLXVI]+$)M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$/;

function abbreviationFindings(pieces, rules) {
  const fullText = pieces.map((piece) => piece.text).join("\n");
  const seen = new Set();
  const found = [];
  for (const piece of pieces) {
    for (const match of piece.masked.matchAll(/\b[A-Z][A-Z0-9]{1,5}s?\b/g)) {
      const word = match[0];
      const bare = word.replace(/s$/, "");
      if (seen.has(bare)) continue;
      seen.add(bare);
      if (PLACEHOLDERS.has(word) || rules.known.has(word) || rules.known.has(bare)) continue;
      if (rules.shouted.has(word) || ROMAN.test(word) || /^\d/.test(word)) continue;
      const defined = new RegExp(`\\(\\s*${bare}s?\\s*\\)|\\b${bare}s?\\s+\\(`).test(fullText);
      if (defined) continue;
      found.push(
        finding(
          { id: "undefined-abbreviation", severity: "advise", clause: "1: 5.3.2 d), e)" },
          piece,
          match.index,
          `"${word}" is not spelled out anywhere. Spell it out the first time, unless this reader already uses it.`,
        ),
      );
    }
  }
  return found;
}

function variationFindings(pieces, rules) {
  const { minSentenceVariation, variationNeedsSentences } = rules.limits;
  const lengths = pieces
    .filter((piece) => piece.kind === "paragraph")
    .flatMap((piece) => sentences(piece.text).map((sentence) => countWords(sentence.text)));
  if (lengths.length < variationNeedsSentences) return [];
  const mean = lengths.reduce((sum, n) => sum + n, 0) / lengths.length;
  const spread = Math.sqrt(lengths.reduce((sum, n) => sum + (n - mean) ** 2, 0) / lengths.length);
  if (spread >= minSentenceVariation) return [];
  return [
    {
      id: "flat-rhythm",
      severity: "advise",
      clause: "1: 5.3.4 c)",
      line: pieces[0].line,
      span: [pieces[0].line, pieces[0].line],
      excerpt: "",
      say: `Sentence lengths barely vary (standard deviation ${spread.toFixed(1)} words, floor ${minSentenceVariation}). Mix short sentences with longer ones so the text does not read flat.`,
    },
  ];
}

function lineFinding(id, severity, clause, line, excerpt, say) {
  return { id, severity, clause, line, span: [line, line], excerpt: excerpt.trim().slice(0, 160), say };
}

const NUMBER_CELL = /^[-+]?[$£€]?\d[\d,]*(?:\.\d+)?\s?(?:%|[a-zA-Z]{1,3})?$/;

// Checks one Markdown table. `rows` is [{ line, cells }], header first, divider second.
function tableFindings(rows) {
  const found = [];
  const [header, divider, ...body] = rows;
  if (!divider || !/^[\s|:-]+$/.test(divider.raw)) return found;
  const columns = header.cells.length;
  const at = header.line;
  if (columns < 2 || body.length < 2) {
    found.push(lineFinding("table-too-small", "advise", "GOV.UK: tables", at, header.raw, "A table this small is easier to read as a sentence or a list."));
  }
  const aligns = divider.cells.map((cell) => (/:\s*$/.test(cell) && !/^\s*:/.test(cell) ? "right" : "other"));
  for (let c = 0; c < columns; c++) {
    const values = body.map((row) => (row.cells[c] ?? "").trim());
    const empty = body.find((row) => !(row.cells[c] ?? "").trim());
    if (empty) {
      found.push(lineFinding("empty-table-cell", "advise", "GOV.UK: tables", empty.line, empty.raw, "An empty cell is ambiguous. Write \"no data\", \"not applicable\" or \"0\"."));
    }
    const numbers = values.filter(Boolean).map((value) => value.replace(/\*\*/g, ""));
    if (numbers.length >= 2 && numbers.every((value) => NUMBER_CELL.test(value))) {
      if (aligns[c] !== "right") {
        found.push(lineFinding("numbers-not-right-aligned", "advise", "GOV.UK: tables; 3: 5.3.7 j)", divider.line, header.raw, `Column "${header.cells[c].trim()}" holds numbers. Right-align it with "---:" so the digits line up.`));
      }
    }
    // A cell that starts with a percentage, such as "52% ($1,700 a month)", counts too.
    const percents = values.filter(Boolean).map((value) => /^\**\s*(-?\d+(?:\.\d+)?)\s?%/.exec(value));
    if (percents.length >= 3 && percents.every(Boolean)) {
      const sum = percents.reduce((total, match) => total + Number.parseFloat(match[1]), 0);
      if (sum > 101) {
        found.push(lineFinding("parts-exceed-whole", "advise", "3: 5.3.6, 5.3.7", header.line, header.raw, `The percentages in "${header.cells[c].trim()}" add up to ${Math.round(sum)}%. If the rows are meant to be parts of one total, they overlap. Use one breakdown per table.`));
      }
    }
  }
  return found;
}

function structureFindings(markdown) {
  const found = [];
  const lines = markdown.split("\n");
  const linkTargets = new Map();
  let inFence = false;
  let previousLevel = 0;
  let table = [];

  const closeTable = () => {
    if (table.length) found.push(...tableFindings(table));
    table = [];
  };

  lines.forEach((line, i) => {
    const number = i + 1;
    if (/^\s*(```|~~~)/.test(line)) {
      inFence = !inFence;
      return;
    }
    if (inFence || line.includes("plain-language-allow")) return;
    const text = line.replace(/(`+)[\s\S]*?\1/g, "CODE");

    if (/^\s*\|/.test(text)) {
      const cells = text.trim().replace(/^\||\|$/g, "").split("|");
      table.push({ line: number, raw: line, cells });
      return;
    }
    closeTable();

    const heading = /^\s{0,3}(#{1,6})\s/.exec(text);
    if (heading) {
      const level = heading[1].length;
      if (previousLevel && level > previousLevel + 1) {
        found.push(lineFinding("heading-level-skipped", "block", "GOV.UK: headings; 1: 5.2.3 d)", number, line, `This heading jumps from level ${previousLevel} to level ${level}. Screen reader users move by heading level, so do not skip one.`));
      }
      previousLevel = level;
    }
    if (/^\s*\*\*[^*]+\*\*:?\s*$/.test(text) && !lines[i - 1]?.trim()) {
      found.push(lineFinding("bold-as-heading", "advise", "GOV.UK: headings; 1: 5.2.3 d)", number, line, "A line of bold text used as a heading is not a heading to a screen reader. Use a Markdown heading."));
    }
    if (/\[\^[^\]]+\]/.test(text)) {
      found.push(lineFinding("footnote", "advise", "GOV.UK: footnotes; 1: 5.2.5", number, line, "Footnotes are made for print. Put important information in the text, and leave the rest out."));
    }
    for (const link of text.matchAll(/\[([^\]]+)\]\(([^)\s]+)/g)) {
      const label = link[1].trim().toLowerCase();
      const targets = linkTargets.get(label) ?? new Map();
      targets.set(link[2], number);
      linkTargets.set(label, targets);
    }
  });
  closeTable();

  for (const [label, targets] of linkTargets) {
    if (targets.size < 2) continue;
    const at = Math.max(...targets.values());
    found.push(lineFinding("link-text-reused", "advise", "GOV.UK: links", at, lines[at - 1], `The link text "${label}" goes to ${targets.size} different places. Give each destination its own link text.`));
  }
  return found;
}

function sourceFindings(markdown, rules) {
  const found = [];
  let inFence = false;
  markdown.split("\n").forEach((line, i) => {
    if (/^\s*(```|~~~)/.test(line)) inFence = !inFence;
    if (inFence || line.includes("plain-language-allow")) return;
    const text = line.replace(/(`+)[\s\S]*?\1/g, "CODE");
    for (const rule of rules.source) {
      for (const item of rule.items) {
        item.re.lastIndex = 0;
        if (!item.re.test(text)) continue;
        found.push({
          id: rule.id,
          severity: rule.severity,
          clause: rule.clause,
          line: i + 1,
          span: [i + 1, i + 1],
          excerpt: line.trim().slice(0, 160),
          say: rule.say,
        });
      }
    }
  });
  return found;
}

// Every finding for one Markdown text, in line order. `mode` is "file" or "chat"; a
// chat reply is too short for the rhythm check to mean anything.
export function findings(markdown, rules = loadRules(), { mode = "file" } = {}) {
  const pieces = proseUnits(markdown);
  const found = [...sourceFindings(markdown, rules), ...structureFindings(markdown), ...abbreviationFindings(pieces, rules)];
  for (const piece of pieces) {
    found.push(...phraseFindings(piece, rules), ...headingFindings(piece, rules), ...shoutedFindings(piece, rules));
    if (PROSE_KINDS.has(piece.kind)) {
      found.push(...sentenceFindings(piece, rules), ...paragraphFindings(piece, rules), ...nounHeavyFindings(piece));
    }
  }
  if (mode === "file") found.push(...variationFindings(pieces, rules));

  const unique = new Map();
  for (const one of found) {
    const key = `${one.id}|${one.line}|${one.match ?? one.excerpt}`;
    if (!unique.has(key)) unique.set(key, one);
  }
  return [...unique.values()].sort((a, b) => a.line - b.line || a.id.localeCompare(b.id));
}

export function clauseName(clause) {
  return clause.replace(/\b([13]): /g, "ISO 24495-$1 ");
}

const LABEL = { block: "must fix", advise: "consider" };

// One finding as text. `where` is a file name, or null for a chat reply, whose line
// numbers mean nothing to the reader.
export function format(where, one) {
  const place = where ? `${where}:${one.line}  ` : "";
  const head = `${place}${LABEL[one.severity]}  ${one.id} (${clauseName(one.clause)})`;
  const quote = one.match ? `  "${one.match}" in: ${one.excerpt}` : one.excerpt ? `  ${one.excerpt}` : "";
  return [head, quote, `  ${one.say}`].filter(Boolean).join("\n");
}

async function readStdin() {
  let text = "";
  process.stdin.setEncoding("utf8");
  for await (const chunk of process.stdin) text += chunk;
  return text;
}

async function main(argv) {
  const json = argv.includes("--json");
  const blockOnly = argv.includes("--block-only");
  const mode = argv.includes("--chat") ? "chat" : "file";
  const files = argv.filter((arg) => !arg.startsWith("--"));
  const rules = loadRules();
  const inputs = files.length
    ? files.map((file) => ({ where: file, text: readFileSync(file, "utf8") }))
    : [{ where: "stdin", text: await readStdin() }];

  const results = inputs.map(({ where, text }) => {
    const all = findings(text, rules, { mode });
    return { where, findings: blockOnly ? all.filter((one) => one.severity === "block") : all };
  });

  const total = (severity) =>
    results.reduce((sum, result) => sum + result.findings.filter((one) => one.severity === severity).length, 0);

  if (json) {
    console.log(JSON.stringify({ results, mustFix: total("block"), consider: total("advise") }, null, 2));
  } else {
    for (const result of results) {
      for (const one of result.findings) console.log(`${format(result.where, one)}\n`);
    }
    console.log(`${total("block")} must fix, ${total("advise")} to consider.`);
  }
  process.exitCode = total("block") > 0 ? 1 : 0;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await main(process.argv.slice(2));
}
