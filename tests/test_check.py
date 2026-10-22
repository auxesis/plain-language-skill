# Run with: python3 -m unittest, from the root of the repository.
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
SKILL = os.path.join(ROOT, "skills", "plain-language")
sys.path[:0] = [os.path.join(SKILL, "scripts"), os.path.join(ROOT, "hooks")]

from check import findings, load_rules  # noqa: E402
from prose import count_words, prose_units, sentences  # noqa: E402
from transcript import turn_text  # noqa: E402

rules = load_rules()


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

    # New in the Python version: rules.json holds JavaScript patterns.

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
        self.assertEqual(json.loads(first.stdout)["decision"], "block")
        second = run_hook("stop-guard.py", {"transcript_path": transcript, "stop_hook_active": True})
        self.assertEqual(second.stdout, "")

    def test_the_stop_hook_checks_last_assistant_message_which_the_transcript_may_not_have_yet(self):
        transcript = os.path.join(temporary_folder(self), "t.jsonl")
        write(transcript, entry("user", "q"))
        result = run_hook("stop-guard.py", {"transcript_path": transcript, "last_assistant_message": "Under the hood, it doesn't work."})
        self.assertEqual(json.loads(result.stdout)["decision"], "block")
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
        for name in ("json", "re", "check", "prose", "shared", "transcript"):
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
    def test_hooks_json_has_one_command_for_each_of_the_five_events(self):
        hooks = plugin_hooks()
        self.assertEqual(
            [(event, matcher) for event, matcher, _ in hooks],
            [("SessionStart", None), ("SubagentStart", None), ("UserPromptSubmit", None), ("Stop", None), ("PostToolUse", "Write|Edit|MultiEdit")],
        )
        for event, _, hook in hooks:
            with self.subTest(event=event):
                self.assertEqual(hook["type"], "command")
                self.assertEqual(hook["timeout"], 30)

    def test_each_hook_command_runs_a_file_that_exists_and_has_the_guard_and_exit_1_at_the_end(self):
        for event, _, hook in plugin_hooks():
            with self.subTest(event=event):
                command = hook["command"]
                self.assertTrue(command.startswith(GUARD), command)
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


if __name__ == "__main__":
    unittest.main()
