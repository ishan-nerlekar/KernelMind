from kernelmind.rescore import read_choice, read_grader_word


def test_read_choice_takes_last_answer_line_and_ignores_formatting():
    assert read_choice("x\nANSWER: C", "ABCD") == "C"
    assert read_choice("x\n**ANSWER:** C", "ABCD") == "C"
    assert read_choice("x\nANSWER: `C`", "ABCD") == "C"
    assert read_choice("x\nANSWER: (C) Paris", "ABCD") == "C"
    assert read_choice("ANSWER: B\nwait\n**ANSWER: C**", "ABCD") == "C"
    assert read_choice("Final answer: D", "ABCD") == "D"
    assert read_choice("x\n\n$$ANSWER: C$$", "ABCD") == "C"  # LaTeX display math
    assert read_choice("ANSWER: D 1900 kJ as misprinted as B", "ABCD") == "D"  # trailing comment


def test_read_choice_unreadable():
    assert read_choice("no verdict here", "ABCD") is None
    assert read_choice("ANSWER: E", "ABCD") is None  # not one of the choices
    assert read_choice("ANSWER: I think it's B", "ABCD") is None  # "I" is a word, not choice I


def test_read_choice_real_log_formats():
    L = "ABCD"
    assert read_choice("x\nANSWER: $D", L) == "D"  # template "$LETTER" copied literally
    assert read_choice("Therefore, ANSWER: C", L) == "C"  # mid-sentence
    assert read_choice("the answer is: 'ANSWER: C'", L) == "C"  # quoted
    assert read_choice("ANSWER: D chromatin methylation", L) == "D"  # letter, then words
    assert read_choice("ANSWER: None of the given choices (E)", L) is None  # a word, not a letter
    assert read_choice("ANSWER: No answer (incorrect options)", L) is None
    assert read_choice("ANSWER: A, B (for the two reactions)", L) is None  # hedge: two options
    assert read_choice("ANSWER: A and B.", L) is None
    assert read_choice("ANSWER: C13H12O2", L) is None  # a formula
    assert read_choice("ANSWER: C) 2.08 x 10^-6 m", L) == "C"


def test_read_grader_word():
    assert read_grader_word("CORRECT") == "CORRECT"
    assert read_grader_word("**CORRECT**") == "CORRECT"
    assert read_grader_word("correct.") == "CORRECT"
    assert read_grader_word("The answer is INCORRECT") == "INCORRECT"
    assert read_grader_word("Not INCORRECT at first glance... CORRECT") == "CORRECT"
    assert read_grader_word("") is None
