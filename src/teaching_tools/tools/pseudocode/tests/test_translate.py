"""Per-construct emission in both dialects, parse-back, and round trips."""

import ast

import pytest

from teaching_tools.tools.pseudocode import logic

PROGRAM = """# totals
total = 0
count = 1
limit = int(input("How many? "))
while count <= limit:
    total = total + count
    count += 1
if total > 10 and count != 0:
    print("big", total)
elif total == 10:
    print("ten")
else:
    print("small")
for i in range(0, 5):
    print(i * 2)
for j in range(3):
    print(j)
name = "bob"
print(name.upper(), len(name), name[0:2], 7 // 2, 7 % 2, 2 ** 3)


def area(w, h):
    return w * h


def shout(msg):
    print(msg + "!")


print(area(3, 4))
shout("hi")
"""


same_program = logic.same_program


def test_python_to_ocr_constructs() -> None:
    t = logic.translate(PROGRAM, "python", "ocr")
    assert t.clean, t.dropped
    out = t.text
    assert "// totals" in out
    assert 'limit = int(input("How many? "))' in out
    assert "while count <= limit" in out and "endwhile" in out
    assert "count = count + 1" in out
    assert "if total > 10 AND count != 0 then" in out and "elseif total == 10 then" in out
    assert out.count("endif") == 1
    assert "for i = 0 to 4" in out and "next i" in out
    assert "for j = 0 to 2" in out
    assert "name.upper, name.length, name.substring(0, 2), 7 DIV 2, 7 MOD 2, 2 ^ 3" in out
    assert "function area(w, h)" in out and "endfunction" in out
    assert "procedure shout(msg)" in out and "endprocedure" in out


def test_python_to_aqa_constructs() -> None:
    t = logic.translate(PROGRAM, "python", "aqa")
    assert t.clean, t.dropped
    out = t.text
    assert "total ← 0" in out
    assert "limit ← STRING_TO_INT(USERINPUT)" in out
    assert "WHILE count ≤ limit" in out and "ENDWHILE" in out
    assert (
        "IF total > 10 AND count ≠ 0 THEN" in out
        and "ELSE IF total = 10 THEN" in out
        and "ENDIF" in out
    )
    assert "FOR i ← 0 TO 4" in out and "ENDFOR" in out
    assert 'OUTPUT "big", total' in out
    assert "LEN(name)" in out and "SUBSTRING(0, 1, name)" in out
    assert "SUBROUTINE area(w, h)" in out and "RETURN w * h" in out and "ENDSUBROUTINE" in out
    assert any("input prompt" in n for n in t.notes)


@pytest.mark.parametrize("dialect", ["ocr", "aqa"])
def test_round_trip_through_pseudocode(dialect: str) -> None:
    pseudo = logic.translate(PROGRAM, "python", dialect)  # type: ignore[arg-type]
    assert pseudo.clean
    back = logic.translate(pseudo.text, dialect, "python")  # type: ignore[arg-type]
    assert back.clean, back.dropped
    if dialect == "ocr":
        assert same_program(back.text, PROGRAM), back.text
    else:
        # AQA loses the input prompt (USERINPUT has none) and .upper(); everything else survives.
        expected = PROGRAM.replace('int(input("How many? "))', "int(input())")
        assert same_program(back.text, expected), back.text


def test_pseudocode_to_python_from_scratch() -> None:
    ocr = """// guess the number
target = random(1, 10)
guess = 0
do
    guess = int(input("Guess: "))
    if guess < target then
        print("Higher")
    elseif guess > target then
        print("Lower")
    endif
until guess == target
print("Got it in " + str(guess))
array marks[5]
marks[0] = 7
for i = 0 to 4 step 2
    print(marks[i])
next i
"""
    t = logic.translate(ocr, "ocr", "python")
    assert t.clean, t.dropped
    code = t.text
    assert code.startswith("import random\n")
    assert "target = random.randint(1, 10)" in code
    assert "while True:" in code and "if guess == target:" in code and "break" in code
    assert "marks = [0] * 5" in code and "for i in range(0, 5, 2):" in code
    ast.parse(code)

    aqa = """total ← 0
FOR i ← 1 TO 3
    total ← total + i
ENDFOR
OUTPUT total
REPEAT
    answer ← USERINPUT
UNTIL answer = "yes"
IF NOT (total ≥ 6) THEN
    OUTPUT "odd"
ENDIF
word ← SUBSTRING(0, 2, "hello")
n ← LEN(word) MOD 2
"""
    t = logic.translate(aqa, "aqa", "python")
    assert t.clean, t.dropped
    assert "for i in range(1, 4):" in t.text and "answer = input()" in t.text
    assert "if not total >= 6:" in t.text or "if not (total >= 6):" in t.text
    assert 'word = "hello"[:3]' in t.text and "n = len(word) % 2" in t.text
    ast.parse(t.text)


def test_untranslatable_is_listed_and_kept_as_comment() -> None:
    src = "import os\nx = [1, 2]\nx.append(3)\nwhile True:\n    break\nprint(x)\n"
    t = logic.translate(src, "python", "ocr")
    assert any("imports" in d for d in t.dropped)
    assert any("break" in d for d in t.dropped)
    assert "// could not translate: import os" in t.text
    assert "// could not translate: break" in t.text
    assert any("fixed size" in n for n in t.notes)
    assert "Could not translate:" in t.report()
    bad = logic.translate("if x then\n    print(x)\nendwhile\n", "ocr", "python")
    assert bad.dropped and "# could not translate" in bad.text


def test_invalid_python_raises() -> None:
    with pytest.raises(SyntaxError):
        logic.translate("while True\n    pass\n", "python", "ocr")
    with pytest.raises(ValueError, match="unknown direction"):
        logic.split_direction("python_to_python")
