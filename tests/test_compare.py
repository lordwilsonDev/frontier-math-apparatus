from fma.compare import compare_textual, Comparison

def test_exact_match():
    assert compare_textual("x=2", "x=2") == Comparison.EXACT_MATCH

def test_nonidentical_is_not_called_wrong():
    assert compare_textual("x=2", "2=x") == Comparison.UNRESOLVED
