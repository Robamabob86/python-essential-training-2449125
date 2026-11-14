from commentator.numbers import gap_words, laptime_words, ordinal_words, speakify


def test_ordinals():
    assert [ordinal_words(n) for n in (1, 2, 3, 5, 12, 21, 30)] == [
        "first", "second", "third", "fifth", "twelfth", "twenty-first", "thirtieth"]


def test_gaps_are_rounded_like_a_human():
    assert gap_words(0.48) == "half a second"
    assert gap_words(1.02) == "about a second"
    assert gap_words(3.4) == "about three seconds"


def test_lap_times():
    assert laptime_words(92.456) == "one thirty-two point five"
    assert laptime_words(65.04) == "one oh five point zero"


def test_speakify_removes_robot_numbers():
    out = speakify("Up to P5! Gap 0.5s, lap 1:32.456 and 3rd")
    assert "P5" not in out and not any(ch.isdigit() for ch in out)
    assert "fifth" in out and "half a second" in out and "third" in out
