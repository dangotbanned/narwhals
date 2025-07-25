# Boolean columns

## Null preservation

Generally speaking, Narwhals operations preserve null values.
For example, if you do `nw.col('a')*2`, then:

- Values which were non-null get multiplied by 2.
- Null values stay null.

```python exec="1" source="above" session="boolean"
import narwhals as nw
from narwhals.typing import IntoFrameT

data = {"a": [1.4, None, 4.2]}


def multiplication(df: IntoFrameT) -> IntoFrameT:
    return nw.from_native(df).with_columns((nw.col("a") * 2).alias("a*2")).to_native()
```

=== "pandas"
    ```python exec="true" source="material-block" result="python" session="boolean"
    import pandas as pd

    df = pd.DataFrame(data)
    print(multiplication(df))
    ```

=== "Polars (eager)"
    ```python exec="true" source="material-block" result="python" session="boolean"
    import polars as pl

    df = pl.DataFrame(data)
    print(multiplication(df))
    ```

=== "PyArrow"
    ```python exec="true" source="material-block" result="python" session="boolean"
    import pyarrow as pa

    table = pa.table(data)
    print(multiplication(table))
    ```

What do we do, however, when the result column is boolean? For
example, `nw.col('a') > 0`?
Unfortunately, this is backend-dependent:

- for all backends except pandas, null values are preserved
- for pandas, this depends on the dtype backend:
    - for PyArrow dtypes and pandas nullable dtypes, null values are preserved
    - for the classic NumPy dtypes, null values are typically filled in with `False`.

pandas is generally moving towards nullable dtypes, and they
[may become the default in the future](https://github.com/pandas-dev/pandas/pull/58988),
so we hope that the classical NumPy dtypes not supporting null values will just
be a temporary legacy pandas issue which will eventually go
away anyway.

```python exec="1" source="above" session="boolean"
from narwhals.typing import FrameT


def comparison(df: FrameT) -> FrameT:
    return nw.from_native(df).with_columns((nw.col("a") > 2).alias("a>2")).to_native()
```

=== "pandas"
    ```python exec="true" source="material-block" result="python" session="boolean"
    import pandas as pd

    df = pd.DataFrame(data)
    print(comparison(df))
    ```

=== "Polars (eager)"
    ```python exec="true" source="material-block" result="python" session="boolean"
    import polars as pl

    df = pl.DataFrame(data)
    print(comparison(df))
    ```

=== "PyArrow"
    ```python exec="true" source="material-block" result="python" session="boolean"
    import pyarrow as pa

    table = pa.table(data)
    print(comparison(table))
    ```

## Kleene logic

Generally speaking, if we have two boolean columns `'a'` and `'b'`, then `nw.col('a') | nw.col('b')` and
`nw.col('a') & nw.col('b')` follow Kleene logic. That is to say:

| `nw.col('a')` | `nw.col('b')` | `nw.col('a') | nw.col('b')` | `nw.col('a') & nw.col('b')` |
|---------------|---------------|-----------------------------|-----------------------------|
| True          | True          | True                        | True                        |
| True          | False         | True                        | False                       |
| True          | None          | True                        | None                        |
| False         | True          | True                        | False                       |
| False         | False         | False                       | False                       |
| False         | None          | None                        | False                       |
| None          | True          | True                        | None                        |
| None          | False         | None                        | False                       |
| None          | None          | None                        | None                        |

Here, too, pandas backed by NumPy types differs, as its boolean columns cannot store null values:

- For `nw.col('a') | nw.col('b')`, pandas returns `True` if at least one column contains a `True` value, and `False` otherwise.
- For `nw.col('a') & nw.col('b')`, pandas returns `True` if both columns contain `True` values, and `False` otherwise.

In `any_horizontal` and `all_horizontal` there is an `ignore_nulls` argument, which behaves as follows:

- If `True`, then null values are ignored and contribute nothing to the final result. If there are
    no values, the result is:

    - `False` for `any_horizontal`.
    - `True` for `all_horizontal`.
- If `False`, then Kleene logic is followed. If using pandas backed by classical NumPy types, then this option is not supported.
