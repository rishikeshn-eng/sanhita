import pytest

from sanhita.cite import find_citations
from sanhita.check import check, heading, successors
from sanhita.cli import main


def ids(text):
    return [(c.act, c.section) for c in find_citations(text)]


@pytest.mark.parametrize("text,expected", [
    ("under Section 302 read with Section 34 of the Indian Penal Code, 1860", [("IPC", "302"), ("IPC", "34")]),
    ("Sections 447, 506 read with Section 34 of the Indian Penal Code", [("IPC", "447"), ("IPC", "506"), ("IPC", "34")]),
    ("FIR under 420/406/34 IPC", [("IPC", "420"), ("IPC", "406"), ("IPC", "34")]),
    ("u/s 498-A IPC and 304B IPC", [("IPC", "498A"), ("IPC", "304B")]),
    ("Section 161 (2) Cr. P.C.", [("CRPC", "161")]),
    ("section 420 I.P.C.", [("IPC", "420")]),
    ("under Section 500 I. P. C.", [("IPC", "500")]),
    ("UNDER SECTION 313 OF THE CRPC", [("CRPC", "313")]),
    ("Section 100 of the CrPC 1973", [("CRPC", "100")]),
    ("304 part II IPC", [("IPC", "304")]),
    ("Section 65B of the Indian Evidence Act", [("IEA", "65B")]),
    ("The punishment for murder is under BNS 103(1).", [("BNS", "103")]),
    ("file under BNSS 173 and BSA 63", [("BNSS", "173"), ("BSA", "63")]),
    ("धारा 420 भारतीय दंड संहिता के तहत", [("IPC", "420")]),
    ("बीएनएस की धारा 318 के तहत", [("BNS", "318")]),
    ("Chapter 16 of the IPC", []),
])
def test_citation_forms(text, expected):
    assert ids(text) == expected


def test_ranges_expand():
    assert ids("Sections 63 to 70, IPC") == [("IPC", str(n)) for n in range(63, 71)]


def test_subsection_kept():
    c = find_citations("Section 161 (2) Cr. P.C.")[0]
    assert c.sub == "(2)"


def test_mapping_known_pairs():
    assert [s["to"] for s in successors("IPC:302")] == ["BNS:103"]
    assert [s["to"] for s in successors("IPC:420")] == ["BNS:318"]
    assert [s["to"] for s in successors("CRPC:154")] == ["BNSS:173"]
    assert [s["to"] for s in successors("IEA:65B")] == ["BSA:63"]
    assert heading("BNS:302").startswith("Uttering words")


def status(text):
    return [c["status"] for c in check(text)["citations"]]


def test_stale_old_code():
    assert status("Punishment for murder is in Section 302 IPC.") == ["stale"]


def test_carryover_same_number_new_code():
    r = check("Murder is punishable under BNS 302 with death or life imprisonment.")
    assert r["citations"][0]["status"] == "carryover"
    assert r["citations"][0]["suggestion"] == ["BNS:103"]
    assert r["verdict"] == "wrong"


def test_nonexistent_new_section_is_carryover():
    r = check("Cheating is covered by Section 420 of the BNS.")
    assert r["citations"][0]["status"] == "carryover"
    assert r["citations"][0]["suggestion"] == ["BNS:318"]


def test_correct_new_citations_clean():
    r = check("Cheating is punishable under BNS 318; file an FIR under BNSS 173.")
    assert status("Cheating is punishable under BNS 318; file an FIR under BNSS 173.") == ["ok", "ok"]
    assert r["verdict"] == "clean"


def test_omitted_section():
    r = check("Sedition under Section 124A IPC.")
    assert r["citations"][0]["status"] == "omitted"
    assert "BNS 152" in r["citations"][0]["message"]


def test_pre_2024_offence_keeps_old_code():
    assert status("The theft happened in March 2023, so Section 379 IPC applies.") == ["ok_old_period"]
    assert status("The theft happened in March 2023; charge under BNS 303.") == ["temporal"]


def test_nonexistent_old_section():
    assert status("Section 999 IPC") == ["nonexistent"]


def test_cli_exit_codes(capsys):
    assert main(["Cheating is punishable under BNS 318."]) == 0
    assert main(["Section 420 IPC applies."]) == 1
    assert main(["Murder is punishable under BNS 302."]) == 2
    assert main(["--map", "IPC", "420"]) == 0
    assert "BNS 318" in capsys.readouterr().out
