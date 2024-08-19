from typing import Any

import pandas as pd
import pytest

import narwhals.stable.v1 as nw
from tests.utils import compare_dicts


def test_new_series(constructor_eager: Any) -> None:
    s = nw.from_native(constructor_eager({"a": [1, 2, 3]}), eager_only=True)["a"]
    result = nw.new_series("b", [4, 1, 2], native_namespace=nw.get_native_namespace(s))
    expected = {"b": [4, 1, 2]}
    # all supported libraries auto-infer this to be int64, we can always special-case
    # something different if necessary
    assert result.dtype == nw.Int64
    compare_dicts(result.to_frame(), expected)

    result = nw.new_series(
        "b", [4, 1, 2], nw.Int32, native_namespace=nw.get_native_namespace(s)
    )
    expected = {"b": [4, 1, 2]}
    assert result.dtype == nw.Int32
    compare_dicts(result.to_frame(), expected)


def test_new_series_dask() -> None:
    pytest.importorskip("dask")
    pytest.importorskip("dask_expr", exc_type=ImportError)
    import dask.dataframe as dd

    df = nw.from_native(dd.from_pandas(pd.DataFrame({"a": [1, 2, 3]})))
    with pytest.raises(
        NotImplementedError, match="Dask support in Narwhals is lazy-only"
    ):
        nw.new_series("a", [1, 2, 3], native_namespace=nw.get_native_namespace(df))