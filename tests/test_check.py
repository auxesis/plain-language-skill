# Run with: python3 -m unittest, from the root of the repository.
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
SKILL = os.path.join(ROOT, "skills", "plain-language")
sys.path[:0] = [os.path.join(SKILL, "scripts"), os.path.join(ROOT, "hooks")]

import failure  # noqa: E402
import shared  # noqa: E402
from check import findings, load_rules  # noqa: E402
from prose import count_words, prose_units, sentences  # noqa: E402
from settings import SettingsError, names_for  # noqa: E402
from transcript import turn_text  # noqa: E402

rules = load_rules()

# Each hook the tests run inherits this environment: a data folder of its own, and no
# saved settings, so the hooks use the defaults in plugin.json.
DATA = tempfile.TemporaryDirectory(prefix="plain-language-data-")
SAVED_ENVIRONMENT = dict(os.environ)


def setUpModule():
    for key in [key for key in os.environ if key.startswith("CLAUDE_PLUGIN_OPTION_")]:
        del os.environ[key]
    os.environ["CLAUDE_PLUGIN_DATA"] = DATA.name


def tearDownModule():
    os.environ.clear()
    os.environ.update(SAVED_ENVIRONMENT)
    DATA.cleanup()


def ids(text, mode="file"):
    return [one["id"] for one in findings(text, rules, mode=mode)]


def blocking(text, mode="file"):
    return [one["id"] for one in findings(text, rules, mode=mode) if one["severity"] == "block"]


def temporary_folder(test):
    folder = tempfile.TemporaryDirectory(prefix="plain-language-")
    test.addCleanup(folder.cleanup)
    return folder.name


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def add_cases(cls, name, cases, check):
    """Adds one test method to `cls` for each case, so each case passes or fails on its own."""
    for index, case in enumerate(cases):
        def test(self, case=case):
            check(self, case)

        slug = re.sub(r"\W+", "_", str(case[0] if isinstance(case, tuple) else case)).strip("_").lower()[:40]
        test.__doc__ = f"{name}: {case}"
        setattr(cls, f"test_{name}_{index:02d}_{slug}", test)


class ReadingMarkdownAsProse(unittest.TestCase):
    def test_leaves_out_fenced_code_and_turns_inline_code_and_urls_into_one_word_each(self):
        units = prose_units("Run `npm run build --workspace a/b` now. See https://example.com/x.\n\n```\nin order to\n```\n")
        self.assertEqual([unit.text for unit in units], ["Run CODE now. See URL."])

    def test_makes_each_list_item_heading_and_table_cell_its_own_piece(self):
        units = prose_units("# Title\n\n- one\n- two\n  continued\n\n| a | b |\n|---|---|\n| c | d |\n")
        self.assertEqual(
            [(unit.kind, unit.text) for unit in units],
            [
                ("heading", "Title"),
                ("item", "one"),
                ("item", "two continued"),
                ("cell", "a"),
                ("cell", "b"),
                ("cell", "c"),
                ("cell", "d"),
            ],
        )

    def test_keeps_metadata_lines_apart_so_they_are_not_read_as_one_sentence(self):
        units = prose_units("purpose: Find your record\nrelated: Topic 2\nneeds: Nothing\n")
        self.assertEqual(len(units), 3)

    def test_joins_hard_wrapped_lines_and_still_knows_which_line_each_part_came_from(self):
        [unit] = prose_units("First line of a sentence\nthat wraps onto line two.")
        self.assertEqual(unit.text, "First line of a sentence that wraps onto line two.")
        self.assertEqual(unit.line_at(unit.text.index("wraps")), 2)

    def test_skips_front_matter_html_comments_and_lines_marked_plain_language_allow(self):
        text = "---\ntitle: in order to\n---\n<!--\nin order to\n-->\nIn order to go. <!-- plain-language-allow -->\nKept."
        self.assertEqual([unit.text for unit in prose_units(text)], ["Kept."])

    def test_does_not_end_a_sentence_at_e_g_or_a_version_number(self):
        self.assertEqual(len(sentences("Use a tool, e.g. Make. Version 1.2 works. Done.")), 3)

    def test_counts_a_word_only_when_it_has_a_letter_or_a_digit_in_it(self):
        self.assertEqual(count_words("A — B (C) + 4"), 4)

    # The tests below are new in the Python version. They cover the places where the
    # port had to replace a JavaScript feature that Python's re module does not have.

    def test_ends_a_sentence_before_a_capital_letter_that_is_not_ascii(self):
        self.assertEqual(len(sentences("It works. Émile agrees.")), 2)
        self.assertEqual(len(sentences("It works. émile agrees.")), 1)

    def test_counts_a_word_made_of_letters_that_are_not_ascii(self):
        self.assertEqual(count_words("café — naïve ½"), 3)


PHRASE_CASES = [
    ("wordy", "We did this in order to test it."),
    ("smothered-verb", "We need to make a decision today."),
    ("hidden-actor", "It was decided that the job stops."),
    ("throat-clearing", "It is worth noting that the job stops."),
    ("flattery-or-filler-closer", "Great question. The job stops."),
    ("cliche", "This is low-hanging fruit."),
    ("idiom", "These tests are load-bearing."),
    ("shorthand", "Run it w/ the flag."),
    ("arrow", "The value goes from 1 → 2."),
    ("stacked-hedge", "This could potentially fail."),
    ("negative-contraction", "It doesn't work."),
    ("date-format", "It ran on October 21, 2026."),
    ("inclusive-language", "Add it to the whitelist."),
    ("figurative", "Each claim rests on these measurements."),
    ("figurative", "New pull requests drove the cost."),
    ("figurative", "The smaller figure strengthens the case for skipping it."),
    ("symbol-shorthand", "The cost is ≈ $3,300."),
    ("symbol-shorthand", "The cost is $3.3k a month."),
    ("symbol-shorthand", "That is a 22× jump."),
    ("symbol-shorthand", "Compare light vs heavy jobs."),
    ("month-abbreviation", "The cuts are live by 1 Nov."),
    ("govuk-words-to-avoid", "We will liaise with the team."),
    ("govuk-tone", "Please note that the job stops."),
    ("govuk-tone", "The member can do it if he or she wants."),
    ("govuk-tone", "You should've run it first."),
]


class PhraseRules(unittest.TestCase):
    def test_does_not_block_plain_text(self):
        self.assertEqual(blocking("The job stops at midnight. You can start it again from the settings page.", "chat"), [])

    def test_does_not_check_words_inside_quotation_marks_or_inline_code(self):
        self.assertEqual(blocking('Write "to", not "in order to". Leave `in order to` alone.', "chat"), [])
        self.assertEqual(blocking("Write 'to', not 'in order to'.", "chat"), [])

    def test_does_not_read_an_apostrophe_as_a_quotation_mark(self):
        self.assertIn("negative-contraction", blocking("The member's record doesn't change.", "chat"))

    def test_does_not_report_a_literal_use_that_the_pattern_excludes(self):
        self.assertNotIn("figurative-jargon", ids("Print it in landscape orientation."))

    # New in the Python version: rules.json contains JavaScript patterns.

    def test_compiles_every_pattern_in_rules_json_without_a_warning(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            load_rules()

    def test_reports_an_emoji_but_not_a_trademark_sign(self):
        self.assertIn("emoji", ids("The build passed 🎉 today."))
        self.assertNotIn("emoji", ids("Claude™ is a name."))


def _blocks_phrase(self, case):
    rule, text = case
    self.assertIn(rule, blocking(text, "chat"), f"{rule} not found in: {text}")


add_cases(PhraseRules, "blocks", PHRASE_CASES, _blocks_phrase)

LONG = " ".join(f"word{i}" for i in range(26)) + "."


class SentenceAndParagraphRules(unittest.TestCase):
    def test_blocks_a_sentence_over_25_words_and_allows_one_of_25(self):
        self.assertIn("long-sentence", blocking(LONG))
        ok = " ".join(f"word{i}" for i in range(25)) + "."
        self.assertNotIn("long-sentence", blocking(ok))

    def test_measures_each_list_item_on_its_own(self):
        items = "\n".join(f"- Item {i} has six words here" for i in range(6))
        self.assertEqual(blocking(items), [])

    def test_blocks_a_paragraph_of_six_sentences_but_not_a_list_of_six_items(self):
        self.assertIn("long-paragraph", blocking("One. Two. Three. Four. Five. Six."))
        self.assertNotIn("long-paragraph", blocking("- One.\n- Two.\n- Three.\n- Four.\n- Five.\n- Six."))

    def test_blocks_an_aside_of_five_words_or_more_in_the_middle_of_a_sentence(self):
        self.assertIn("aside-interrupts-sentence", blocking("The job stops — unless somebody has paused it first — at midnight."))
        self.assertIn("aside-interrupts-sentence", blocking("The job stops (unless somebody has paused it first) at midnight."))

    def test_does_not_block_a_short_aside_a_dash_that_ends_a_sentence_or_a_pair_across_two_sentences(self):
        self.assertEqual(blocking("The job (nightly) stops at midnight."), [])
        self.assertEqual(blocking("The job stops at midnight — every night."), [])
        self.assertEqual(blocking("One part — a short clause. Then another sentence starts — and ends here."), [])


class Advice(unittest.TestCase):
    def test_reports_an_abbreviation_that_is_never_spelled_out_once(self):
        found = [one for one in findings("The FFR report and the FFR view.", rules) if one["id"] == "undefined-abbreviation"]
        self.assertEqual(len(found), 1)

    def test_does_not_report_an_abbreviation_spelled_out_in_the_text_or_a_known_one(self):
        self.assertNotIn("undefined-abbreviation", ids("Fit for Role (FFR) matters. The FFR view."))
        self.assertNotIn("undefined-abbreviation", ids("Read the API docs and the JSON file."))

    def test_reports_a_shouted_word_as_shouting_not_as_an_abbreviation(self):
        found = ids("You MUST run it.")
        self.assertIn("shouted-word", found)
        self.assertNotIn("undefined-abbreviation", found)

    def test_never_blocks_on_advice(self):
        self.assertEqual(blocking("This is very clear: 3x faster & simpler.", "chat"), [])

    def test_allows_a_short_month_name_inside_a_table_and_nowhere_else(self):
        table = "| Month | Cost |\n|---|---:|\n| Sep | 189 |\n| Oct | 3865 |\n"
        self.assertNotIn("month-abbreviation", blocking(table))

    def test_reports_a_fragment_with_no_subject_and_not_a_whole_sentence_that_starts_the_same_way(self):
        self.assertIn("no-subject", ids("Checking the filter now.", "chat"))
        self.assertNotIn("no-subject", ids("Getting under $1,000 means a 74% cut.", "chat"))
        self.assertNotIn("no-subject", ids("Nothing changes.", "chat"))

    # New in the Python version. Python's \b treats "É" as part of a word, so it does
    # not find the abbreviation "COLE" inside "ÉCOLE", as the JavaScript version did.
    def test_does_not_report_part_of_a_word_that_starts_with_a_letter_that_is_not_ascii(self):
        self.assertNotIn("undefined-abbreviation", ids("The ÉCOLE report is ready."))


ROUND_TWO_BLOCKED = [
    ("two-ideas-in-one-sentence", "A light job is one small enough for GitHub's runners, which cost nothing."),
    ("two-ideas-in-one-sentence", "Six decisions are made and eight are waiting on you."),
    ("thing-given-person-verb", "`.github/CONTEXT.md` is new and holds the CI glossary."),
    ("thing-given-person-verb", "`CONTEXT-MAP.md` gains one link to it."),
    ("thing-given-person-verb", "The function knows which row to read."),
    ("condition-after-instruction", "Tell me where you would like it kept if you need it."),
    ("figurative", "The stack repository is on pace to spend $4,000."),
]

ROUND_TWO_ALLOWED = [
    "A member holds the Boat Operator capability.",
    "Done when someone who reads the first paragraph knows what it says.",
    "Check if your code is incorrect, or if it has expired.",
    "Read a record Slipstream has nothing in, and know what to do about it.",
    "Topic 3 covers what a capability is, and what an assessment is.",
    "Use a technical term only if the reader already uses it.",
    "Write must for a rule that has consequences if it is broken.",
]


class RulesFromTheReviewOfRoundTwo(unittest.TestCase):
    def test_asks_for_a_comma_after_an_opening_clause_and_not_in_a_question(self):
        self.assertIn("comma-after-opening-clause", blocking("If you need it tell me where to keep it.", "chat"))
        self.assertEqual(blocking("If you need it, tell me where to keep it.", "chat"), [])
        self.assertEqual(blocking("When does the nightly job run?", "chat"), [])

    def test_asks_for_a_serial_comma_in_a_list_and_not_in_a_phrase_or_a_name(self):
        self.assertIn("serial-comma", blocking("It covers words, headings and links.", "chat"))
        self.assertEqual(blocking("It covers words, headings, and links.", "chat"), [])
        self.assertEqual(blocking("An assessment can have a level, such as Lift and Shift Level 2.", "chat"), [])
        self.assertEqual(blocking("Your row shows it as Paused, with your reason and the date.", "chat"), [])
        self.assertEqual(blocking("Comment on a line, or select lines and suggest a change.", "chat"), [])
        self.assertEqual(blocking("Eight test inputs, run before and after the change.", "chat"), [])
        self.assertEqual(blocking("I checked the page, before and after the change.", "chat"), [])
        self.assertNotIn("serial-comma", blocking("The report, written last week and sent today, lists the results.", "chat"))
        self.assertEqual(blocking("For the run without the skill, all hooks and skills were turned off.", "chat"), [])
        self.assertIn("serial-comma", blocking("For the test, it covers words, headings and links.", "chat"))


def _blocks_round_two(self, case):
    rule, text = case
    self.assertIn(rule, blocking(text, "chat"))


def _allows_round_two(self, text):
    self.assertEqual(blocking(text, "chat"), [])


add_cases(RulesFromTheReviewOfRoundTwo, "blocks", ROUND_TWO_BLOCKED, _blocks_round_two)
add_cases(RulesFromTheReviewOfRoundTwo, "allows", ROUND_TWO_ALLOWED, _allows_round_two)

# The review of round three is in pull request 1. Most of these texts are quoted from it.
ROUND_THREE_BLOCKED = [
    ("repeated-word", "Now the stand-in in each test:"),
    ("repeated-word", "Read the the file first."),
    ("question-heading-items", "## Questions for the next round\n\n- **Weekly cost estimate:** where it gets posted.\n"),
    ("question-heading-items", "## Questions for the next round\n\n- **Tool setup:** the mise tool-setup step takes about 16% of all job time.\n"),
    ("question-heading-items", "## Open questions\n\n### Billing\n\n1. The names of the summary checks that become required.\n"),
    ("whether-item", "## Facts I still need to check\n\n- Whether the RunsOn trial licence has an end date.\n"),
    ("whether-item", "- **Dependabot:** whether to group its updates.\n"),
    # From the review of the first description of pull request 10: things given a person's
    # verb, in headings as well as in sentences.
    ("thing-given-person-verb", "## What the checker cannot see\n\nThe checker never checks code blocks.\n"),
    ("thing-given-person-verb", "## How the checks behave on real text\n\nThe checks ran over 77 files.\n"),
    ("thing-given-person-verb", "## Each review comment, and the change that answers it\n\nThe table lists them.\n"),
    ("thing-given-person-verb", "The test cannot see the new file."),
]

ROUND_THREE_ALLOWED = [
    "Now the stand-in for each test:",
    "The reviewer answered each comment.",
    "You can see the file in the pull request.",
    "You can see the table below.",
    # Database documentation says that a transaction sees data. The user allowed it.
    "Under SERIALIZABLE, each transaction sees the data as it was when the transaction started.",
    "## Review comments and changes\n\nThe checker skips code blocks.\n",
    "Run `npm test` `--watch` again.",
    "## Questions for the next round\n\n- **Dependabot:** should updates be grouped?\n  In 20 days, 40 Dependabot branches cost $115.\n- **Weekly cost estimate:** where does it get posted?\n",
    "## Questions\n\n- Is the job done?\n\n## Next steps\n\n- Run the tests again.\n",
    "## Decisions\n\n- **Dependabot:** updates are grouped by week.\n",
    "- Whether or not you use mise, run the tests before you push.\n",
    # Found in the sample of real replies: inline code becomes the word CODE.
    "It cancels one of the transactions with a serialisation error, code `40001`.",
    # A nested item under a question contains a detail.
    "## Questions waiting for your answers\n\n1. **Q2:** which checks run only once per pull request?\n   - The Test EQL heavy suite.\n   - udeps and Miri.\n",
    # A part that asks its questions in paragraphs has lists of options.
    "## Questions\n\n**Q1:** Should stack use a merge queue? These are the choices:\n\n- (a) A merge queue.\n- (b) A label that a person adds.\n",
    "## Questions for this round\n\n**Q1. What starts the pre-merge run.** There are two options:\n\n1. A GitHub merge queue.\n2. A label that a person adds.\n\nShall the pre-merge run be a GitHub merge queue?\n",
]

ROUND_THREE_ADVISED = [
    ("pronoun-start", "They skip any new or unstaged file without failing."),
    ("pronoun-start", "Their output does not list which files they read."),
    ("pronoun-start", "It runs at midnight."),
    ("pronoun-start", "This means that the job stops."),
    ("pronoun-start", "These are the two options."),
    ("purpose-last", "- calls the callback with an empty list of entries and the observer, to match the real callback signature\n"),
    ("purpose-last", "We call the job twice, to make sure it stops."),
]

ROUND_THREE_NOT_ADVISED = [
    ("pronoun-start", "The guards skip any new or unstaged file without failing."),
    ("pronoun-start", "This file is new, and these tests pass."),
    ("pronoun-start", "This process runs every night."),
    ("pronoun-start", "The guards read only files that git tracks, so they skip new files."),
    ("purpose-last", "- match the real callback signature, by calling the callback with the observer and an empty list of entries\n"),
    ("purpose-last", "Give the report to the team, to the person on call, or to me."),
]


class RulesFromTheReviewOfRoundThree(unittest.TestCase):
    def test_reports_a_question_heading_item_only_under_that_heading(self):
        text = "## Questions\n\n- Is the job done?\n- The job is done.\n\n## Notes\n\n- The job is done.\n"
        found = [one["line"] for one in findings(text, rules) if one["id"] == "question-heading-items"]
        self.assertEqual(found, [4])

    def test_never_blocks_on_a_pronoun_or_a_purpose_at_the_end(self):
        for _, text in ROUND_THREE_ADVISED:
            with self.subTest(text=text):
                self.assertEqual(blocking(text, "chat"), [])


def _blocks_round_three(self, case):
    rule, text = case
    self.assertIn(rule, blocking(text, "chat"))


def _allows_round_three(self, text):
    self.assertEqual(blocking(text, "chat"), [])


def _advises_round_three(self, case):
    rule, text = case
    self.assertIn(rule, ids(text, "chat"))


def _does_not_advise_round_three(self, case):
    rule, text = case
    self.assertNotIn(rule, ids(text, "chat"))


add_cases(RulesFromTheReviewOfRoundThree, "blocks", ROUND_THREE_BLOCKED, _blocks_round_three)
add_cases(RulesFromTheReviewOfRoundThree, "allows", ROUND_THREE_ALLOWED, _allows_round_three)
add_cases(RulesFromTheReviewOfRoundThree, "advises", ROUND_THREE_ADVISED, _advises_round_three)
add_cases(RulesFromTheReviewOfRoundThree, "does_not_advise", ROUND_THREE_NOT_ADVISED, _does_not_advise_round_three)


class StructureRules(unittest.TestCase):
    def test_blocks_a_heading_that_is_a_question(self):
        self.assertIn("heading-is-a-question", blocking("## Which members have no unit?\n\nText."))

    def test_blocks_a_heading_that_skips_a_level_and_allows_going_back_up(self):
        self.assertIn("heading-level-skipped", blocking("## One\n\n#### Two\n"))
        self.assertNotIn("heading-level-skipped", blocking("## One\n\n### Two\n\n## Three\n"))

    def test_reports_percentages_that_add_up_to_more_than_the_whole_even_with_notes_in_the_cells(self):
        table = "\n".join(
            [
                "| Slice | Share of cost |",
                "|---|---:|",
                "| Pull requests | 89% |",
                "| 16-vCPU runners | 76% |",
                "| Test EQL | 52% ($1,700 a month) |",
            ]
        )
        self.assertIn("parts-exceed-whole", ids(table))
        whole = "| Part | Share |\n|---|---:|\n| A | 60% |\n| B | 30% |\n| C | 10% |\n"
        self.assertNotIn("parts-exceed-whole", ids(whole))

    def test_reports_a_column_of_numbers_that_is_not_right_aligned_and_an_empty_cell(self):
        found = ids("| Repo | Cost |\n|---|---|\n| stack | 3865 |\n| proxy |  |\n| suite | 67 |\n")
        self.assertIn("empty-table-cell", found)
        self.assertIn("numbers-not-right-aligned", ids("| Repo | Cost |\n|---|---|\n| stack | 3865 |\n| proxy | 325 |\n"))

    def test_reports_the_same_link_text_going_to_two_places(self):
        self.assertIn("link-text-reused", ids("See [the guide](a.md) and [the guide](b.md)."))

    # New in the Python version. Python's \s does not match U+FEFF, the byte order mark.
    def test_reads_the_first_line_of_a_file_with_a_byte_order_mark_as_a_heading(self):
        self.assertIn("heading-is-a-question", blocking("﻿## Which members have no unit?\n\nText."))


CLI = os.path.join(SKILL, "scripts", "check.py")


def run(arguments, text=None, cwd=None, env=None):
    return subprocess.run(
        [sys.executable, "-I", *arguments],
        input=text,
        capture_output=True,
        encoding="utf-8",
        cwd=cwd,
        env=env,
    )


class TheCommandLine(unittest.TestCase):
    def test_exits_1_when_something_must_be_fixed_and_0_when_nothing_must(self):
        self.assertEqual(run([CLI, "--chat"], "We did it in order to test it.").returncode, 1)
        self.assertEqual(run([CLI, "--chat"], "We did it to test it.").returncode, 0)

    def test_runs_when_it_is_reached_through_a_symlink(self):
        link = os.path.join(temporary_folder(self), "check.py")
        os.symlink(CLI, link)
        bad = run([link, "--chat"], "We did it in order to test it.")
        self.assertEqual(bad.returncode, 1)
        self.assertRegex(bad.stdout, "must fix")

    def test_passes_its_own_skill_files(self):
        files = [os.path.join(SKILL, file) for file in ("SKILL.md", "core.md", "references/guidelines.md")]
        out = json.loads(run([CLI, "--json", *files]).stdout)
        self.assertEqual(out["mustFix"], 0)


def entry(type, content, **extra):
    return json.dumps({"type": type, "message": {"content": content}, **extra})


def run_hook(name, event, cwd=None, env=None):
    return run([os.path.join(ROOT, "hooks", name)], json.dumps(event), cwd=cwd, env=env)


def sent_back(result):
    """The text the Stop hook gave back to Claude, or None when it let the turn end."""
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"] if result.stdout else None


def findings_file(name="session.txt"):
    """A file in the findings folder, where the Stop hook writes findings for Claude to read."""
    folder = os.path.join(os.environ["CLAUDE_PLUGIN_DATA"], "findings")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    write(path, "findings\n")
    return path


def display_event(delta, final=True, turn="turn-1", message="message-1", session="session-1"):
    return {"session_id": session, "turn_id": turn, "message_id": message, "final": final, "delta": delta}


class TheHooks(unittest.TestCase):
    def test_reads_every_text_block_claude_wrote_since_the_persons_last_message(self):
        transcript = "\n".join(
            [
                entry("user", "first question"),
                entry("assistant", [{"type": "text", "text": "Old answer."}]),
                entry("user", [{"type": "text", "text": "second question"}]),
                entry("assistant", [{"type": "thinking", "thinking": "in order to"}]),
                entry("assistant", [{"type": "text", "text": "Part one."}]),
                entry("user", [{"type": "tool_result", "content": "output"}]),
                entry("user", [{"type": "text", "text": "skill text"}], isMeta=True),
                entry("assistant", [{"type": "text", "text": "Part two."}]),
            ]
        )
        self.assertEqual(turn_text(transcript), "Part one.\n\nPart two.")

    def test_starts_a_turn_at_a_message_from_another_agent_or_from_a_stop_hook_and_not_at_a_skills_text(self):
        peer = {"isMeta": True, "origin": {"kind": "peer"}, "turnOrigin": "peer", "turnPosition": {"turnIndex": 2}}
        from_peer = "\n".join(
            [
                entry("user", "question"),
                entry("assistant", [{"type": "text", "text": "Old answer."}]),
                entry("user", "Another Claude session sent a message: done.", **peer),
                entry("assistant", [{"type": "text", "text": "New answer."}]),
            ]
        )
        self.assertEqual(turn_text(from_peer), "New answer.")
        after_feedback = "\n".join(
            [
                entry("user", "question"),
                entry("assistant", [{"type": "text", "text": "First draft."}]),
                entry("user", "Stop hook feedback:\nWrite the reply again.", isMeta=True),
                entry("assistant", [{"type": "text", "text": "Second draft."}]),
            ]
        )
        self.assertEqual(turn_text(after_feedback), "Second draft.")
        skill = "\n".join(
            [
                entry("user", "question"),
                entry("assistant", [{"type": "text", "text": "Part one."}]),
                entry("user", "Base directory for this skill: /skills/x", isMeta=True, turnCompanion=True),
                entry("assistant", [{"type": "text", "text": "Part two."}]),
            ]
        )
        self.assertEqual(turn_text(skill), "Part one.\n\nPart two.")

    def test_the_stop_hook_sends_a_reply_back_once_and_lets_it_through_the_second_time(self):
        transcript = os.path.join(temporary_folder(self), "t.jsonl")
        write(transcript, "\n".join([entry("user", "q"), entry("assistant", [{"type": "text", "text": "It doesn't work."}])]))
        first = run_hook("stop-guard.py", {"transcript_path": transcript, "stop_hook_active": False})
        self.assertIn("Your reply breaks", sent_back(first))
        second = run_hook("stop-guard.py", {"transcript_path": transcript, "stop_hook_active": True})
        self.assertEqual(second.stdout, "")

    def test_the_stop_hook_checks_last_assistant_message_which_the_transcript_may_not_have_yet(self):
        transcript = os.path.join(temporary_folder(self), "t.jsonl")
        write(transcript, entry("user", "q"))
        result = run_hook("stop-guard.py", {"transcript_path": transcript, "last_assistant_message": "Under the hood, it doesn't work."})
        self.assertIn("Your reply breaks", sent_back(result))
        missing = run_hook("stop-guard.py", {"transcript_path": "/nonexistent/t.jsonl", "last_assistant_message": "It does not work."})
        self.assertEqual(missing.stdout, "")

    def test_the_stop_hook_stays_quiet_when_the_transcript_is_missing(self):
        result = run_hook("stop-guard.py", {"transcript_path": "/nonexistent/t.jsonl"})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_the_file_hook_checks_only_the_paragraph_an_edit_touched(self):
        file = os.path.join(temporary_folder(self), "doc.md")
        write(file, "Old text, in order to stay.\n\nNew text is fine.\n")
        clean = run_hook("file-guard.py", {"tool_name": "Edit", "tool_input": {"file_path": file, "new_string": "New text is fine."}})
        self.assertEqual(clean.stdout, "")
        dirty = run_hook("file-guard.py", {"tool_name": "Write", "tool_input": {"file_path": file}})
        self.assertEqual(json.loads(dirty.stdout)["decision"], "block")

    def test_the_file_hook_ignores_code_files_and_files_that_switch_it_off(self):
        folder = temporary_folder(self)
        code = os.path.join(folder, "a.ts")
        write(code, "// in order to\n")
        self.assertEqual(run_hook("file-guard.py", {"tool_name": "Write", "tool_input": {"file_path": code}}).stdout, "")
        off = os.path.join(folder, "rules.md")
        write(off, "<!-- plain-language-check: off -->\nin order to\n")
        self.assertEqual(run_hook("file-guard.py", {"tool_name": "Write", "tool_input": {"file_path": off}}).stdout, "")

    def test_the_file_hook_still_checks_a_file_that_only_mentions_the_marker_in_a_sentence(self):
        readme = os.path.join(temporary_folder(self), "README.md")
        write(readme, "To skip a file, put `plain-language-check: off` on a line of its own.\n\nWe did it in order to test it.\n")
        result = run_hook("file-guard.py", {"tool_name": "Write", "tool_input": {"file_path": readme}})
        self.assertRegex(result.stdout, '"decision":"block"')

    def test_the_session_hook_adds_core_md_for_a_session_and_for_a_subagent(self):
        session = json.loads(run_hook("session-start.py", {"hook_event_name": "SessionStart"}).stdout)
        self.assertRegex(session["hookSpecificOutput"]["additionalContext"], "^# Plain language")
        subagent = json.loads(run_hook("session-start.py", {"hook_event_name": "SubagentStart"}).stdout)
        self.assertEqual(subagent["hookSpecificOutput"]["hookEventName"], "SubagentStart")

    # New in the Python version. A hook runs in the folder of the project that is open,
    # so a file there named like one of the hook's modules must not be imported.
    def test_every_hook_ignores_python_files_and_variables_in_the_project_folder(self):
        folder = temporary_folder(self)
        for name in ("json", "re", "shutil", "stat", "tempfile", "time", "check", "prose", "settings", "shared", "transcript"):
            write(os.path.join(folder, f"{name}.py"), "raise SystemExit('imported from the project folder')\n")
        env = {**os.environ, "PYTHONPATH": folder}
        file = os.path.join(folder, "doc.md")
        write(file, "We did it in order to test it.\n")
        transcript = os.path.join(folder, "t.jsonl")
        write(transcript, entry("assistant", [{"type": "text", "text": "It doesn't work."}]))
        events = {
            "session-start.py": {"hook_event_name": "SessionStart"},
            "prompt-reminder.py": {},
            "stop-guard.py": {"transcript_path": transcript},
            "file-guard.py": {"tool_name": "Write", "tool_input": {"file_path": file}},
            "message-display.py": display_event("It works."),
            "read-findings.py": {"tool_name": "Read", "tool_input": {"file_path": findings_file()}},
        }
        for name, event in events.items():
            with self.subTest(hook=name):
                result = run_hook(name, event, cwd=folder, env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("project folder", result.stderr)
                self.assertTrue(json.loads(result.stdout))

    def test_the_prompt_hook_adds_a_one_line_reminder(self):
        result = json.loads(run_hook("prompt-reminder.py", {}).stdout)
        self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        self.assertNotIn("\n", result["hookSpecificOutput"]["additionalContext"])

    # The plugin can be installed anywhere, so the hooks name core.md by the path they
    # find from their own location.
    def test_the_reminder_and_the_findings_name_the_core_md_that_exists(self):
        reminder = json.loads(run_hook("prompt-reminder.py", {}).stdout)["hookSpecificOutput"]["additionalContext"]
        file = os.path.join(temporary_folder(self), "doc.md")
        write(file, "We did it in order to test it.\n")
        reason = json.loads(run_hook("file-guard.py", {"tool_name": "Write", "tool_input": {"file_path": file}}).stdout)["reason"]
        for text in (reminder, reason):
            with self.subTest(text=text[:40]):
                path = re.search(r"(/\S+/core\.md)", text).group(1)
                self.assertEqual(path, os.path.join(SKILL, "core.md"))
                self.assertTrue(os.path.isfile(path))


# Three passages from a real guide that the checker misread before it knew the names.
GLOSSARY = "- **Fit for Role assessment** — one of the eight Fit for Role assessments.\n  They are Swim, Lift and Shift, Carry, Hike, Drag, Haul, Hold, and Ladder Climb and Lift.\n"
CLUSTER = "For a whole cluster, select every unit in it, and the cluster's own name too. aXcelerate's filter does not accept a cluster name on its own.\n"
RANK = "The Rank and Insignia Procedure awards a rank on three things: training and skills, service experience and proficiency, and aptitude and behaviour.\n"
NAMED_CASES = [
    ("a name with and in it is not the end of a list", GLOSSARY, "Lift and Shift", "serial-comma"),
    ("a name that starts with a small letter can start a sentence", CLUSTER, "aXcelerate", "long-sentence"),
    ("a name made of a pair is one item in a list", RANK, "service experience and proficiency", "serial-comma"),
]


def blocking_with(text, names, mode="file"):
    return [one["id"] for one in findings(text, rules, mode=mode, names=names) if one["severity"] == "block"]


def repository(test, settings=None):
    """A temporary git repository, with a settings file at its top when `settings` is given."""
    root = temporary_folder(test)
    os.mkdir(os.path.join(root, ".git"))
    if settings is not None:
        write(os.path.join(root, ".plain-language.json"), settings if isinstance(settings, str) else json.dumps(settings))
    return root


class ProjectNames(unittest.TestCase):
    def test_a_name_counts_as_one_word(self):
        text = f"Members {' '.join(f'w{i}' for i in range(21))} passed Ladder Climb and Lift.\n"
        self.assertIn("long-sentence", blocking(text))
        self.assertNotIn("long-sentence", blocking_with(text, ("Ladder Climb and Lift",)))

    def test_matches_a_name_only_in_its_own_case_and_as_a_whole_word(self):
        for written in ("axcelerate", "aXcelerateX"):
            with self.subTest(written=written):
                self.assertIn("long-sentence", blocking_with(CLUSTER.replace("aXcelerate", written), ("aXcelerate",)))

    def test_shows_the_readers_own_words_in_every_finding(self):
        [wordy] = [one for one in findings("aXcelerate does it in order to test it.", rules, names=("aXcelerate",)) if one["id"] == "wordy"]
        self.assertEqual(wordy["excerpt"], "aXcelerate does it in order to test it.")
        [repeated] = [one for one in findings("Pass Lift and Shift Lift and Shift first.", rules, names=("Lift and Shift",)) if one["id"] == "repeated-word"]
        self.assertEqual(repeated["match"], "Lift and Shift Lift and Shift")

    def test_does_not_read_two_names_of_the_same_length_as_one_word_twice(self):
        self.assertNotIn("repeated-word", blocking_with("Pass Hike Drag first.", ("Hike", "Drag")))

    # Each name is read as one stand-in word of the same length. A rule that matched the
    # stand-in would report a problem the reader cannot see.
    def test_no_rule_matches_the_word_that_stands_in_for_a_name(self):
        for length in range(1, 61):
            name = "q" * length
            for text in (f"The {name} is here.", f"{name} is here.", f"- {name}"):
                with self.subTest(text=text):
                    self.assertEqual(findings(text, rules, mode="chat", names=(name,)), [])

    def test_finds_the_nearest_settings_file_up_to_the_top_of_the_repository(self):
        root = repository(self, {"names": ["aXcelerate"]})
        os.makedirs(os.path.join(root, "docs", "guide"))
        page = os.path.join(root, "docs", "guide", "page.md")
        self.assertEqual(names_for(page), ("aXcelerate",))
        write(os.path.join(root, "docs", ".plain-language.json"), json.dumps({"names": ["Lift and Shift"]}))
        self.assertEqual(names_for(page), ("Lift and Shift",))

    # In a git worktree, .git is a file, not a folder.
    def test_does_not_use_a_settings_file_above_the_top_of_the_repository(self):
        outer = temporary_folder(self)
        write(os.path.join(outer, ".plain-language.json"), json.dumps({"names": ["aXcelerate"]}))
        os.mkdir(os.path.join(outer, "project"))
        write(os.path.join(outer, "project", ".git"), "gitdir: /elsewhere\n")
        self.assertEqual(names_for(os.path.join(outer, "project", "page.md")), ())

    BROKEN = [
        ("not JSON", '{"names": ["aXcelerate"]', "cannot be read as JSON"),
        ("not an object", '["aXcelerate"]', "must be a JSON object"),
        ("an unknown setting", '{"names": [], "rules": {"long-sentence": false}}', '"rules" is not a setting'),
        ("names that are not a list", '{"names": "aXcelerate"}', '"names" must be a list'),
        ("a name that is not a string", '{"names": [7]}', "each name must be a string"),
        ("a name with no letter in it", '{"names": [" - "]}', "each name must be a string"),
        ("a name that ends with a space", '{"names": ["aXcelerate "]}', "starts or ends with a space"),
    ]

    def check_broken(self, case):
        _, content, reason = case
        root = repository(self, content)
        with self.assertRaises(SettingsError) as raised:
            names_for(root)
        self.assertEqual(raised.exception.path, os.path.join(root, ".plain-language.json"))
        self.assertIn(reason, raised.exception.reason)

    def test_the_command_line_reads_the_settings_file_for_each_file_and_for_standard_input(self):
        root = repository(self)
        page = os.path.join(root, "page.md")
        write(page, CLUSTER)
        self.assertEqual(run([CLI, page]).returncode, 1)
        self.assertEqual(run([CLI, "--chat"], CLUSTER, cwd=root).returncode, 1)
        write(os.path.join(root, ".plain-language.json"), json.dumps({"names": ["aXcelerate"]}))
        self.assertEqual(run([CLI, page]).returncode, 0)
        self.assertEqual(run([CLI, "--chat"], CLUSTER, cwd=root).returncode, 0)

    def test_the_command_line_exits_2_and_names_a_broken_settings_file(self):
        root = repository(self, '{"names": "aXcelerate"}')
        page = os.path.join(root, "page.md")
        write(page, CLUSTER)
        result = run([CLI, page])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn(os.path.join(root, ".plain-language.json"), result.stderr)
        self.assertIn('"names" must be a list', result.stderr)

    def test_the_file_hook_reads_the_names_and_reports_a_broken_settings_file(self):
        root = repository(self, {"names": ["aXcelerate"]})
        page = os.path.join(root, "page.md")
        write(page, CLUSTER)
        event = {"tool_name": "Write", "tool_input": {"file_path": page}}
        self.assertEqual(run_hook("file-guard.py", event).stdout, "")
        write(os.path.join(root, ".plain-language.json"), "{")
        reason = json.loads(run_hook("file-guard.py", event).stdout)["reason"]
        self.assertIn(os.path.join(root, ".plain-language.json"), reason)
        self.assertIn("was not checked", reason)

    def test_the_file_hook_checks_the_settings_file_when_claude_writes_it(self):
        root = repository(self, {"names": ["aXcelerate"]})
        event = {"tool_name": "Write", "tool_input": {"file_path": os.path.join(root, ".plain-language.json")}}
        self.assertEqual(run_hook("file-guard.py", event).stdout, "")
        write(os.path.join(root, ".plain-language.json"), json.dumps({"names": ["aXcelerate"], "sentenceWords": 40}))
        self.assertRegex(json.loads(run_hook("file-guard.py", event).stdout)["reason"], '"sentenceWords" is not a setting')

    def test_the_stop_hook_reads_the_names_for_the_sessions_folder(self):
        root = repository(self, {"names": ["aXcelerate"]})
        event = {"transcript_path": "/nonexistent/t.jsonl", "last_assistant_message": CLUSTER, "cwd": root}
        self.assertEqual(run_hook("stop-guard.py", event).stdout, "")
        self.assertIn("Your reply breaks", sent_back(run_hook("stop-guard.py", {**event, "cwd": temporary_folder(self)})))
        write(os.path.join(root, ".plain-language.json"), '{"names": [7]}')
        reason = sent_back(run_hook("stop-guard.py", event))
        self.assertIn("Your reply was not checked", reason)


add_cases(
    ProjectNames,
    "names",
    NAMED_CASES,
    lambda self, case: (
        self.assertIn(case[3], blocking(case[1])),
        self.assertNotIn(case[3], blocking_with(case[1], (case[2],))),
    ),
)
add_cases(ProjectNames, "broken", ProjectNames.BROKEN, ProjectNames.check_broken)


def env_with(value):
    """The environment with PLAIN_LANGUAGE_HOOKS set to `value`, or without it for None."""
    env = {key: item for key, item in os.environ.items() if key != "PLAIN_LANGUAGE_HOOKS"}
    if value is not None:
        env["PLAIN_LANGUAGE_HOOKS"] = value
    return env


class TheSwitchThatTurnsOffTheHooks(unittest.TestCase):
    def events(self):
        """For each hook, an event that makes it print something when it is on."""
        file = os.path.join(temporary_folder(self), "doc.md")
        write(file, "We did it in order to test it.\n")
        return {
            "session-start.py": {"hook_event_name": "SessionStart"},
            "prompt-reminder.py": {},
            "stop-guard.py": {"last_assistant_message": "We did it in order to test it."},
            "file-guard.py": {"tool_name": "Write", "tool_input": {"file_path": file}},
            "message-display.py": display_event("It works."),
            "read-findings.py": {"tool_name": "Read", "tool_input": {"file_path": findings_file()}},
        }

    def test_every_hook_exits_with_0_and_prints_nothing_when_the_variable_is_false(self):
        events = self.events()
        for value in ("false", "FALSE", " false "):
            for name, event in events.items():
                with self.subTest(value=value, hook=name):
                    result = run_hook(name, event, env=env_with(value))
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_every_hook_runs_when_the_variable_is_true_or_unset_or_any_other_value(self):
        events = self.events()
        for value in ("true", None, "0"):
            for name, event in events.items():
                with self.subTest(value=value, hook=name):
                    result = run_hook(name, event, env=env_with(value))
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertTrue(json.loads(result.stdout))

    def test_the_checker_ignores_the_variable(self):
        result = run([CLI, "--chat"], "We did it in order to test it.", env=env_with("false"))
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout, "must fix")


def plugin_hooks():
    """Each (event, matcher, hook) in the plugin's hooks/hooks.json."""
    with open(os.path.join(ROOT, "hooks", "hooks.json"), encoding="utf-8") as handle:
        hooks = json.load(handle)["hooks"]
    return [(event, entry.get("matcher"), hook) for event, entries in hooks.items() for entry in entries for hook in entry["hooks"]]


def read_json(*path):
    with open(os.path.join(ROOT, *path), encoding="utf-8") as handle:
        return json.load(handle)


GUARD = "command -v python3 >/dev/null 2>&1 || exit 0; "
# Only the SessionStart command says that python3 is missing. A warning from every
# other hook would come with every message and every edit.
SESSION_GUARD = "command -v python3 >/dev/null 2>&1 || { printf '%s\\n' '{\"systemMessage\":"
HOOK_FILE = re.compile(r'python3 -I "\$\{CLAUDE_PLUGIN_ROOT\}/(hooks/[\w-]+\.py)"')


def run_command(test, command, plugin_root):
    """Runs a hook command the way Claude Code does: it puts the plugin's folder in place of
    ${CLAUDE_PLUGIN_ROOT}, also sets that variable, and runs the command with a shell."""
    # PATH starts with a python3 that is this Python, so the command reaches Python
    # instead of exiting at "command -v".
    programs = temporary_folder(test)
    os.symlink(sys.executable, os.path.join(programs, "python3"))
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": plugin_root, "PATH": programs + os.pathsep + os.environ.get("PATH", "")}
    command = command.replace("${CLAUDE_PLUGIN_ROOT}", plugin_root)
    return subprocess.run(["/bin/sh", "-c", command], input="{}", capture_output=True, encoding="utf-8", env=env)


class ThePlugin(unittest.TestCase):
    def test_hooks_json_has_one_command_for_each_of_the_seven_events(self):
        hooks = plugin_hooks()
        self.assertEqual(
            [(event, matcher) for event, matcher, _ in hooks],
            [
                ("SessionStart", None),
                ("SubagentStart", None),
                ("UserPromptSubmit", None),
                ("Stop", None),
                ("MessageDisplay", None),
                ("PreToolUse", "Read"),
                ("PostToolUse", "Write|Edit|MultiEdit"),
            ],
        )
        for event, _, hook in hooks:
            with self.subTest(event=event):
                self.assertEqual(hook["type"], "command")
                # Claude Code holds each batch of a reply until the MessageDisplay hook
                # returns, so that hook keeps the event's default timeout of 10 seconds.
                self.assertEqual(hook["timeout"], 10 if event == "MessageDisplay" else 30)

    def test_each_hook_command_runs_a_file_that_exists_and_has_the_guard_and_exit_1_at_the_end(self):
        for event, _, hook in plugin_hooks():
            with self.subTest(event=event):
                command = hook["command"]
                self.assertTrue(command.startswith(SESSION_GUARD if event == "SessionStart" else GUARD), command)
                self.assertTrue(command.endswith(" || exit 1"), command)
                self.assertTrue(os.path.isfile(os.path.join(ROOT, HOOK_FILE.search(command).group(1))), command)

    def test_each_hook_command_runs_its_hook_from_the_plugin_folder(self):
        for event, _, hook in plugin_hooks():
            with self.subTest(event=event):
                result = run_command(self, hook["command"], ROOT)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")

    # Python exits with code 2 when the file it is asked to run is missing, and Claude Code
    # reads exit code 2 from a prompt hook as an instruction to block the prompt. Each
    # command must turn that into exit code 1.
    def test_no_hook_command_exits_with_code_2_when_its_file_is_missing(self):
        empty = temporary_folder(self)
        for event, _, hook in plugin_hooks():
            with self.subTest(event=event):
                result = run_command(self, hook["command"], empty)
                self.assertIn("No such file", result.stderr)
                self.assertEqual(result.returncode, 1)

    # The install id uses the marketplace entry's name, and the skill's prefix uses the
    # manifest's name, so the two must be the same. Neither file sets a version, so Claude
    # Code uses the commit as the version, and users get each commit when they update.
    def test_the_marketplace_lists_the_plugin_at_the_root_under_the_same_name_and_no_version(self):
        plugin = read_json(".claude-plugin", "plugin.json")
        (listed,) = read_json(".claude-plugin", "marketplace.json")["plugins"]
        self.assertEqual(plugin["name"], "plain-language")
        self.assertEqual(listed["name"], plugin["name"])
        self.assertEqual(listed["source"], "./")
        self.assertNotIn("version", plugin)
        self.assertNotIn("version", listed)
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "skills", plugin["name"], "SKILL.md")))


def broken_copy(test, module, code):
    """A copy of the plugin in which `module` ends with `code`, so that a hook fails."""
    copy = os.path.join(temporary_folder(test), "plugin")
    for folder in ("hooks", "skills"):
        shutil.copytree(os.path.join(ROOT, folder), os.path.join(copy, folder), ignore=shutil.ignore_patterns("__pycache__"))
    path = {"shared.py": ("hooks", "shared.py"), "check.py": ("skills", "plain-language", "scripts", "check.py")}[module]
    with open(os.path.join(copy, *path), "a", encoding="utf-8") as handle:
        handle.write("\n" + code)
    return copy


PROSE = "We did it in order to test it."
SYNTAX_ERROR = "def broken(:\n"
RAISES_IN_EMIT = "def emit(payload):\n    raise RuntimeError('forced failure')\n"
RAISES_IN_FINDINGS = "def findings(*args, **kwargs):\n    raise RuntimeError('forced failure')\n"
# Each hook, the module it imports, code that makes it fail while it runs, the hook's
# event, and what its warning says was not done.
FAILING_HOOKS = [
    ("session-start.py", "shared.py", RAISES_IN_EMIT, "SessionStart", "the plain-language rules were not added to this session"),
    ("prompt-reminder.py", "shared.py", RAISES_IN_EMIT, "UserPromptSubmit", "the plain-language reminder was not added to this message"),
    ("stop-guard.py", "check.py", RAISES_IN_FINDINGS, "Stop", "Claude's reply was not checked"),
    ("file-guard.py", "check.py", RAISES_IN_FINDINGS, "PostToolUse", "the prose Claude just wrote to doc.md was not checked"),
    ("message-display.py", "shared.py", RAISES_IN_EMIT, "MessageDisplay", "Claude's reply was shown without the plain-language check"),
    ("read-findings.py", "shared.py", RAISES_IN_EMIT, "PreToolUse", "Claude may need your permission to read the plain-language findings"),
]


class WhenAHookFails(unittest.TestCase):
    def event(self, hook):
        file = os.path.join(temporary_folder(self), "doc.md")
        write(file, PROSE + "\n")
        return {
            "session-start.py": {"hook_event_name": "SessionStart"},
            "prompt-reminder.py": {},
            "stop-guard.py": {"last_assistant_message": PROSE},
            "file-guard.py": {"tool_name": "Write", "tool_input": {"file_path": file}},
            "message-display.py": display_event(PROSE),
            "read-findings.py": {"tool_name": "Read", "tool_input": {"file_path": findings_file()}},
        }[hook]

    def run_copy(self, copy, hook, env=None):
        result = run([os.path.join(copy, "hooks", hook)], json.dumps(self.event(hook)), env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_each_hook_warns_the_person_and_does_not_block_claude_when_its_code_fails(self):
        for hook, module, code, event, missed in FAILING_HOOKS:
            with self.subTest(hook=hook):
                out = json.loads(self.run_copy(broken_copy(self, module, code), hook))
                self.assertEqual(list(out), ["systemMessage"])
                message = out["systemMessage"]
                self.assertIn(f"the {event} hook failed at {module} line ", message)
                self.assertIn(missed, message)
                self.assertIn("RuntimeError: forced failure", message)
                self.assertNotIn(PROSE, message)

    def test_each_hook_warns_when_the_code_it_imports_cannot_be_read(self):
        for hook, module, _, event, _ in FAILING_HOOKS:
            with self.subTest(hook=hook):
                message = json.loads(self.run_copy(broken_copy(self, module, SYNTAX_ERROR), hook))["systemMessage"]
                self.assertIn(f"the {event} hook failed at {module} line ", message)
                self.assertIn("SyntaxError", message)

    def test_a_failing_hook_says_nothing_when_the_hooks_are_switched_off(self):
        env = {**os.environ, "PLAIN_LANGUAGE_HOOKS": "false"}
        for hook, module, code, _, _ in FAILING_HOOKS:
            for broken in (code, SYNTAX_ERROR):
                with self.subTest(hook=hook, broken=broken[:12]):
                    self.assertEqual(self.run_copy(broken_copy(self, module, broken), hook, env=env), "")

    def test_the_warning_quotes_at_most_200_characters_of_the_error(self):
        out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        with mock.patch.dict(os.environ, {"PLAIN_LANGUAGE_HOOKS": ""}), mock.patch.object(sys, "stdout", out):
            try:
                raise ValueError("x" * 500)
            except ValueError as error:
                self.assertEqual(failure.report("Stop", "nothing was checked", error), 0)
        detail = json.loads(out.buffer.getvalue())["systemMessage"].split("The error was ", 1)[1]
        self.assertEqual(len(detail), failure.LIMIT)
        self.assertTrue(detail.endswith("..."))

    def test_only_the_session_command_says_that_python3_is_missing(self):
        env = {**os.environ, "PATH": temporary_folder(self), "CLAUDE_PLUGIN_ROOT": ROOT}
        for event, _, hook in plugin_hooks():
            with self.subTest(event=event):
                command = hook["command"].replace("${CLAUDE_PLUGIN_ROOT}", ROOT)
                result = subprocess.run(["/bin/sh", "-c", command], input="{}", capture_output=True, encoding="utf-8", env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                if event == "SessionStart":
                    self.assertRegex(json.loads(result.stdout)["systemMessage"], "python3 was not found")
                else:
                    self.assertEqual(result.stdout, "")


REPLY = "The server is up only while your machine and the tunnel are up."


def stop_event(text, session="session-1", active=False):
    return {"session_id": session, "last_assistant_message": text, "stop_hook_active": active}


def with_settings(**values):
    """The environment with these saved settings, the way Claude Code passes them to a hook."""
    return {**os.environ, **{f"CLAUDE_PLUGIN_OPTION_{key.upper()}": value for key, value in values.items()}}


def data_path(*parts):
    return os.path.join(os.environ["CLAUDE_PLUGIN_DATA"], *parts)


class TheFindingsSetting(unittest.TestCase):
    def test_the_manifest_declares_both_settings_with_the_defaults_the_hooks_use(self):
        options = read_json(".claude-plugin", "plugin.json")["userConfig"]
        self.assertEqual(sorted(options), ["findings", "hide_drafts"])
        self.assertEqual(options["findings"]["options"], list(shared.FINDINGS_STYLES))
        self.assertEqual(options["findings"]["default"], shared.DEFAULT_FINDINGS)
        self.assertEqual(options["hide_drafts"]["type"], "boolean")
        self.assertEqual(options["hide_drafts"]["default"], shared.DEFAULT_HIDE_DRAFTS)

    def reason(self, env=None, session="session-1"):
        result = run_hook("stop-guard.py", stop_event(REPLY, session=session), env=env)
        self.addCleanup(run_hook, "stop-guard.py", stop_event("It works.", session=session, active=True))
        return sent_back(result)

    def test_full_findings_have_the_advice_with_its_example_and_the_path_to_the_rules(self):
        reason = self.reason(with_settings(findings="full"))
        self.assertIn(REPLY, reason)
        self.assertIn('Write two sentences: "Six decisions are made. Eight are waiting for you."', reason)
        self.assertIn("The rules and the reasons for them:", reason)

    def test_short_findings_leave_out_the_example_and_the_path_to_the_rules(self):
        reason = self.reason(with_settings(findings="short"))
        self.assertIn(REPLY, reason)
        self.assertIn("Write two sentences.", reason)
        self.assertNotIn("Six decisions", reason)
        self.assertNotIn("The rules and the reasons for them:", reason)

    def test_file_findings_are_the_default_and_ask_claude_to_read_the_full_findings(self):
        for name, env in (("unset", None), ("FILE", with_settings(findings="FILE")), ("unknown", with_settings(findings="long"))):
            with self.subTest(setting=name):
                session = f"s-file-{name}"
                reason = self.reason(env, session=session)
                path = data_path("findings", f"{session}.txt")
                self.assertEqual(reason, f"Your reply breaks the plain-language rules (ISO 24495-1). Read {path} for the sentences to fix. Then write the corrected reply as if it were the first.")
                with open(path, encoding="utf-8") as handle:
                    written = handle.read()
                self.assertIn(REPLY, written)
                self.assertIn("The rules and the reasons for them:", written)

    # The screen can show a rewrite after the Stop hook has run, so the display hook's
    # record of a hidden reply stays until the person's next message.
    def test_the_end_of_the_turn_deletes_the_sessions_findings_and_keeps_its_display_files(self):
        session = "s-end"
        self.reason(session=session)
        run_hook("message-display.py", display_event(REPLY, session=session))
        paths = [data_path("findings", f"{session}.txt"), data_path("sent-back", session)]
        hidden = data_path("display", session, "hidden")
        for path in [*paths, hidden]:
            self.assertTrue(os.path.exists(path), path)
        self.assertEqual(run_hook("stop-guard.py", stop_event(REPLY, session=session, active=True)).stdout, "")
        for path in paths:
            self.assertFalse(os.path.exists(path), path)
        self.assertTrue(os.path.exists(hidden))
        run_hook("prompt-reminder.py", {"session_id": session})
        self.assertFalse(os.path.exists(hidden))

    def test_the_end_of_any_turn_deletes_files_older_than_a_day(self):
        old, new = findings_file("s-old.txt"), findings_file("s-new.txt")
        self.addCleanup(os.remove, new)
        os.utime(old, (0, 0))
        self.assertEqual(run_hook("stop-guard.py", stop_event("It works.", session="s-other")).stdout, "")
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(new))

    # stop_hook_active is true when a Stop hook from any plugin sent the turn back.
    def test_the_stop_hook_checks_a_turn_that_another_plugins_hook_sent_back(self):
        session = "s-other-hook"
        first = run_hook("stop-guard.py", stop_event(REPLY, session=session, active=True))
        self.assertIn("Your reply breaks", sent_back(first))
        second = run_hook("stop-guard.py", stop_event(REPLY, session=session, active=True))
        self.assertEqual(second.stdout, "")

    def test_the_fallback_folder_must_belong_to_the_user_and_be_closed_to_others(self):
        if not hasattr(os, "getuid"):
            self.skipTest("this system has no user IDs")
        temporary = temporary_folder(self)
        env = {key: value for key, value in os.environ.items() if key != "CLAUDE_PLUGIN_DATA"}
        env["TMPDIR"] = temporary
        base = os.path.join(temporary, f"plain-language-{os.getuid()}")
        safe = run_hook("stop-guard.py", stop_event(REPLY, session="s-fallback"), env=env)
        self.assertIn(f"Read {base}", sent_back(safe))
        os.chmod(base, 0o777)
        unsafe = run_hook("stop-guard.py", stop_event(REPLY, session="s-fallback-2"), env=env)
        self.assertIn("is not a folder that only this user can change", json.loads(unsafe.stdout)["systemMessage"])


class TheReadHook(unittest.TestCase):
    def output(self, path, tool="Read"):
        return run_hook("read-findings.py", {"tool_name": tool, "tool_input": {"file_path": path}}).stdout

    def test_lets_claude_read_a_findings_file_without_a_prompt(self):
        out = json.loads(self.output(findings_file("s-read.txt")))["hookSpecificOutput"]
        self.assertEqual((out["hookEventName"], out["permissionDecision"]), ("PreToolUse", "allow"))

    def test_leaves_every_other_file_to_claude_codes_own_permission_rules(self):
        folder = os.path.dirname(findings_file("s-read.txt"))
        outside = os.path.join(temporary_folder(self), "other.txt")
        write(outside, "secret\n")
        link = os.path.join(folder, "link.txt")
        os.symlink(outside, link)
        self.addCleanup(os.remove, link)
        inner = os.path.join(folder, "inner")
        os.makedirs(inner)
        self.addCleanup(shutil.rmtree, inner)
        write(os.path.join(inner, "x.txt"), "x\n")
        cases = {
            "a file outside the folder": outside,
            "a path that leaves the folder through ..": os.path.join(folder, *[".."] * folder.count(os.sep), os.path.relpath(outside, os.sep)),
            "a link to a file outside the folder": link,
            "a file in a folder inside it": os.path.join(inner, "x.txt"),
            "a file that does not exist": os.path.join(folder, "missing.txt"),
            "the folder itself": folder,
        }
        for name, path in cases.items():
            with self.subTest(name):
                self.assertEqual(self.output(path), "")
        self.assertEqual(self.output(findings_file("s-read.txt"), tool="Write"), "")


class HiddenDrafts(unittest.TestCase):
    def shown(self, delta, env=None, **event):
        """The text the hook shows in place of `delta`, or None when it prints nothing."""
        result = run_hook("message-display.py", display_event(delta, **event), env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["hookSpecificOutput"]["displayContent"] if result.stdout else None

    def test_hides_each_batch_and_shows_the_whole_reply_with_the_last(self):
        session = "s-batches"
        self.assertEqual(self.shown("It works.\n", final=False, session=session), "")
        self.assertEqual(self.shown("It runs.\n", final=False, session=session), "")
        self.assertEqual(self.shown("", session=session), "It works.\nIt runs.\n")

    def test_hides_a_reply_that_breaks_a_rule_and_shows_every_later_reply_until_the_next_message(self):
        session = "s-rewrite"
        self.assertEqual(self.shown(REPLY, session=session, message="draft"), "")
        self.assertEqual(self.shown(REPLY, session=session, message="rewrite"), REPLY)
        self.assertEqual(self.shown(REPLY, session=session, turn="turn-2", message="after-a-tool"), REPLY)
        run_hook("prompt-reminder.py", {"session_id": session})
        self.assertEqual(self.shown(REPLY, session=session, turn="turn-3", message="next"), "")

    def test_the_prompt_hook_adds_its_reminder_whatever_its_input(self):
        for text in ("", "not json", "[]", '{"session_id": "s-none"}'):
            with self.subTest(text=text):
                result = run([os.path.join(ROOT, "hooks", "prompt-reminder.py")], text)
                self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")

    def test_prints_nothing_when_the_setting_is_off(self):
        for value in ("false", "FALSE", "0", "off", "no"):
            with self.subTest(value=value):
                self.assertIsNone(self.shown(REPLY, env=with_settings(hide_drafts=value), session="s-off"))
        for value in ("true", "1"):
            with self.subTest(value=value):
                self.assertEqual(self.shown("It works.", env=with_settings(hide_drafts=value), session="s-on"), "It works.")

    def test_shows_the_whole_reply_when_the_check_fails(self):
        hook = os.path.join(broken_copy(self, "check.py", RAISES_IN_FINDINGS), "hooks", "message-display.py")
        run([hook], json.dumps(display_event(PROSE + "\n", final=False, session="s-broken")))
        out = json.loads(run([hook], json.dumps(display_event("It runs.", session="s-broken"))).stdout)
        self.assertEqual(out["hookSpecificOutput"]["displayContent"], PROSE + "\nIt runs.")

    def test_prints_nothing_for_an_event_without_text(self):
        self.assertEqual(run_hook("message-display.py", {}).stdout, "")

    # Claude Code labels additionalContext "Stop hook feedback" on screen, and shows no
    # "Stop hook error" notice, while still sending the turn back to Claude.
    def test_the_stop_hook_sends_a_reply_back_as_feedback_not_as_an_error(self):
        out = json.loads(run_hook("stop-guard.py", stop_event(REPLY, session="s-label")).stdout)
        self.addCleanup(run_hook, "stop-guard.py", stop_event(REPLY, session="s-label", active=True))
        self.assertEqual(list(out), ["hookSpecificOutput"])
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "Stop")
        self.assertIn("Your reply breaks", out["hookSpecificOutput"]["additionalContext"])

    def test_warns_when_the_reply_after_a_hidden_one_is_much_shorter(self):
        long_reply = " ".join([REPLY] * 4)
        cases = {
            "a short refusal": ("I will not rewrite it.", True),
            "a rewrite of the same length": (long_reply.replace(" and the tunnel are up.", ". The tunnel must be up too."), False),
            "a rewrite of just over half the length": (" ".join([REPLY] * 2) + " More.", False),
        }
        for name, (after, warned) in cases.items():
            with self.subTest(name):
                session = "s-warn-" + name.split()[1]
                run_hook("message-display.py", display_event(long_reply, session=session))
                self.assertIn("Your reply breaks", sent_back(run_hook("stop-guard.py", stop_event(long_reply, session=session))))
                out = run_hook("stop-guard.py", stop_event(after, session=session, active=True)).stdout
                self.assertEqual("Press ctrl+O to see the hidden reply" in out, warned)
                if warned:
                    self.assertEqual(list(json.loads(out)), ["systemMessage"])
                run_hook("prompt-reminder.py", {"session_id": session})

    def test_does_not_warn_when_no_reply_was_hidden(self):
        session = "s-no-warn"
        self.assertIn("Your reply breaks", sent_back(run_hook("stop-guard.py", stop_event(REPLY, session=session))))
        self.assertEqual(run_hook("stop-guard.py", stop_event("Short.", session=session, active=True)).stdout, "")


if __name__ == "__main__":
    unittest.main()
