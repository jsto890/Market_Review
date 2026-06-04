import pandas as pd

from stock_chatter.prices import _scalar_float


def test_scalar_float_accepts_single_element_series():
    assert _scalar_float(pd.Series([12.5])) == 12.5
