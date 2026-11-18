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


def test_read_grader_word():
    assert read_grader_word("CORRECT") == "CORRECT"
    assert read_grader_word("**CORRECT**") == "CORRECT"
    assert read_grader_word("correct.") == "CORRECT"
    assert read_grader_word("The answer is INCORRECT") == "INCORRECT"
    assert read_grader_word("Not INCORRECT at first glance... CORRECT") == "CORRECT"
    assert read_grader_word("") is None
