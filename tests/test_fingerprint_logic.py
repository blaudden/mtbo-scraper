from src.utils.fingerprint import Fingerprinter, Participant


def test_fingerprint_normalization() -> None:
    p: Participant = {
        "name": " Magnus Blåudd ",
        "club": " OK Skogsstjärnan ",
        "class_name": "H40",
        "start_number": "1",
    }
    f1 = Fingerprinter.generate_fingerprint_for_participant(p)

    p2: Participant = {
        "name": "magnus blåudd",
        "club": "ok skogsstjärnan",
        "class_name": "Other",
        "start_number": None,
    }
    f2 = Fingerprinter.generate_fingerprint_for_participant(p2)

    assert f1 == f2


def test_fingerprint_name_reversal() -> None:
    p_normal: Participant = {
        "name": "Magnus Blåudd",
        "club": "OK Skogsstjärnan",
        "class_name": "H40",
        "start_number": "1",
    }
    p_reversed: Participant = {
        "name": "Blåudd Magnus",
        "club": "OK Skogsstjärnan",
        "class_name": "H40",
        "start_number": "2",
    }

    # Without known hashes, they should be different
    f_normal = Fingerprinter.generate_fingerprint_for_participant(p_normal)
    f_reversed = Fingerprinter.generate_fingerprint_for_participant(p_reversed)
    assert f_normal != f_reversed

    # With known normal hash, reversed should match normal
    f_reversed_matched = Fingerprinter.generate_fingerprint_for_participant(
        p_reversed, known_hashes={f_normal}
    )
    assert f_reversed_matched == f_normal

    # With known reversed hash, normal should match reversed
    f_normal_matched = Fingerprinter.generate_fingerprint_for_participant(
        p_normal, known_hashes={f_reversed}
    )
    assert f_normal_matched == f_reversed


def test_fingerprint_name_reversal_multiple_words() -> None:
    p1: Participant = {
        "name": "Magnus von Blåudd",
        "club": "TEST",
        "class_name": "H",
        "start_number": "1",
    }
    p2: Participant = {
        "name": "Blåudd von Magnus",
        "club": "TEST",
        "class_name": "H",
        "start_number": "1",
    }

    f1 = Fingerprinter.generate_fingerprint_for_participant(p1)
    # Reversed words: "blåudd von magnus" -> reversed -> "magnus von blåudd"
    f2 = Fingerprinter.generate_fingerprint_for_participant(p2, known_hashes={f1})

    assert f1 == f2


def test_fingerprint_no_match_different_club() -> None:
    p1: Participant = {
        "name": "Magnus Blåudd",
        "club": "Club A",
        "class_name": "H",
        "start_number": "1",
    }
    p2: Participant = {
        "name": "Blåudd Magnus",
        "club": "Club B",
        "class_name": "H",
        "start_number": "1",
    }

    f1 = Fingerprinter.generate_fingerprint_for_participant(p1)
    f2 = Fingerprinter.generate_fingerprint_for_participant(p2, known_hashes={f1})

    # Even if name is reversed, different club means different fingerprint
    assert f1 != f2


def test_generate_fingerprints_with_known_hashes() -> None:
    participants: list[Participant] = [
        {
            "name": "Blåudd Magnus",
            "club": "OK Skogsstjärnan",
            "class_name": "H40",
            "start_number": None,
        },
        {
            "name": "Other Runner",
            "club": "Club X",
            "class_name": "H21",
            "start_number": None,
        },
    ]

    # Pre-calculated hash for "magnus blåudd|ok skogsstjärnan"
    import hashlib

    known_hash = hashlib.sha256("magnus blåudd|ok skogsstjärnan".encode()).hexdigest()

    fingerprints = Fingerprinter.generate_fingerprints(
        participants, known_hashes={known_hash}
    )

    assert known_hash in fingerprints
    assert len(fingerprints) == 2
