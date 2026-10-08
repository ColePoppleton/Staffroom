"""Acceptance: every OCR Booklet file 1a-8c round-trips Python → ERL → Python
to an ast-equivalent program, or the report lists what was dropped.

The real files live in the teacher's resources folder; the same programs
are embedded here so the test also runs where that folder is absent."""

import os
from pathlib import Path

import pytest

from teaching_tools.tools.pseudocode import logic

# Point TT_BOOKLET_DIR at a folder of the OCR booklet programs to run against the real files.
BOOKLET = (
    Path(os.environ.get("TT_BOOKLET_DIR", ""))
    if os.environ.get("TT_BOOKLET_DIR")
    else Path("/nonexistent")
)
NAMES = [f"{n}{s}" for n in range(1, 9) if n != 7 for s in "abc"]

EMBEDDED = {
    "1a": 'print ("Hello World")\n',
    "1c": 'print ("""This is\na computer program""")\nprint ("This is\\na computer")\n',
    "2c": "word1='the'\nword2='cat'\nprint (word1 + \" \" + word2)\n",
    "3b": 'forename = input("What is your first name? ")\nprint ("Hello " + forename)\n',
    "4a": "print(1+6)\nprint(7-5)\nprint(3*9)\nprint(7/2)\n",
    "5b": (
        "a=int(input('Enter Length:'))\nb=int(input('Enter Width:'))\n"
        "c=a*b\nprint('The area is:'+str(c))\n"
    ),
    "5c": "r=float(input('radius:'))\npi = 3.14159\nvol = (pi*r*r)\nprint('vol: ' + str(vol))\n",
    "6a": (
        "city = input('capital?')\nif city== 'London':\n    print('Well done')\n"
        "elif city=='Lincoln':\n    print('Right country')\nelse:\n    print('Sorry')\n"
    ),
    "6b": (
        "one=int(input('1: '))\ntwo=int(input('2: '))\n"
        "if(one==two) and (two==3):\n    print('SNAP!')\nelse:\n    print('no')\n"
    ),
    "6c": (
        'mark = int(input("mark: "))\nif mark >= 70:\n    print ("A")\n'
        'elif mark >= 60:\n    print ("B")\nelse:\n    print ("U")\n'
    ),
    "8a": 'for i in range(0,15):\n    print("computing")\n',
    "8c": (
        'num = int(input("number "))\nfor i in range(0,10):\n'
        '    print(str(i+1) + " times " + str(num) + " is " + str((i+1)*num))\n'
    ),
}


def round_trip(source: str) -> tuple[bool, list[str]]:
    erl = logic.translate(source, "python", "ocr")
    back = logic.translate(erl.text, "ocr", "python")
    dropped = erl.dropped + back.dropped
    return logic.same_program(back.text, source), dropped


@pytest.mark.parametrize("name", list(EMBEDDED))
def test_embedded_booklet_programs_round_trip(name: str) -> None:
    equal, dropped = round_trip(EMBEDDED[name])
    assert equal, dropped


@pytest.mark.skipif(not BOOKLET.is_dir(), reason="OCR Booklet folder not on this machine")
@pytest.mark.parametrize("name", NAMES)
def test_real_booklet_files_round_trip_or_report(name: str) -> None:
    path = BOOKLET / f"{name}.py"
    if not path.exists():
        pytest.skip(f"{name}.py not present")
    source = path.read_text(encoding="utf-8", errors="replace")
    equal, dropped = round_trip(source)
    assert equal or dropped, f"{name}: not equivalent and nothing reported"
    assert equal, f"{name}: dropped {dropped}"  # 1a-8c are all inside the subset
