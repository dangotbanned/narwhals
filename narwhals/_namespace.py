"""Narwhals-level equivalent of `CompliantNamespace`."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Literal,
    Protocol,
    TypeVar,
    overload,
)

from narwhals._compliant.typing import CompliantNamespaceAny, CompliantNamespaceT_co
from narwhals._utils import Implementation, Version
from narwhals.dependencies import (
    get_cudf,
    get_modin,
    get_pandas,
    get_polars,
    get_pyarrow,
    is_dask_dataframe,
    is_duckdb_relation,
    is_ibis_table,
    is_pyspark_connect_dataframe,
    is_pyspark_dataframe,
    is_sqlframe_dataframe,
)

if TYPE_CHECKING:
    from collections.abc import Collection, Sized
    from types import ModuleType
    from typing import ClassVar

    import duckdb
    import pandas as pd
    import polars as pl
    import pyarrow as pa
    import pyspark.sql as pyspark_sql
    from pyspark.sql.connect.dataframe import DataFrame as PySparkConnectDataFrame
    from typing_extensions import Self, TypeAlias, TypeIs

    from narwhals._arrow.namespace import ArrowNamespace
    from narwhals._dask.namespace import DaskNamespace
    from narwhals._duckdb.namespace import DuckDBNamespace
    from narwhals._ibis.namespace import IbisNamespace
    from narwhals._pandas_like.namespace import PandasLikeNamespace
    from narwhals._polars.namespace import PolarsNamespace
    from narwhals._spark_like.dataframe import SQLFrameDataFrame
    from narwhals._spark_like.namespace import SparkLikeNamespace
    from narwhals.typing import DataFrameLike, NativeFrame, NativeLazyFrame, NativeSeries

    T = TypeVar("T")

    _Guard: TypeAlias = "Callable[[Any], TypeIs[T]]"

    _Polars: TypeAlias = Literal["polars"]
    _Arrow: TypeAlias = Literal["pyarrow"]
    _Dask: TypeAlias = Literal["dask"]
    _DuckDB: TypeAlias = Literal["duckdb"]
    _PandasLike: TypeAlias = Literal["pandas", "cudf", "modin"]
    _Ibis: TypeAlias = Literal["ibis"]
    _SparkLike: TypeAlias = Literal["pyspark", "sqlframe", "pyspark[connect]"]
    _EagerOnly: TypeAlias = "_PandasLike | _Arrow"
    _EagerAllowed: TypeAlias = "_Polars | _EagerOnly"
    _LazyOnly: TypeAlias = "_SparkLike | _Dask | _DuckDB | _Ibis"
    _LazyAllowed: TypeAlias = "_Polars | _LazyOnly"

    Polars: TypeAlias = Literal[_Polars, Implementation.POLARS]
    Arrow: TypeAlias = Literal[_Arrow, Implementation.PYARROW]
    Dask: TypeAlias = Literal[_Dask, Implementation.DASK]
    DuckDB: TypeAlias = Literal[_DuckDB, Implementation.DUCKDB]
    Ibis: TypeAlias = Literal[_Ibis, Implementation.IBIS]
    PandasLike: TypeAlias = Literal[
        _PandasLike, Implementation.PANDAS, Implementation.CUDF, Implementation.MODIN
    ]
    SparkLike: TypeAlias = Literal[
        _SparkLike,
        Implementation.PYSPARK,
        Implementation.SQLFRAME,
        Implementation.PYSPARK_CONNECT,
    ]
    EagerOnly: TypeAlias = "PandasLike | Arrow"
    EagerAllowed: TypeAlias = "EagerOnly | Polars"
    LazyOnly: TypeAlias = "SparkLike | Dask | DuckDB | Ibis"
    LazyAllowed: TypeAlias = "LazyOnly | Polars"

    BackendName: TypeAlias = "_EagerAllowed | _LazyAllowed"
    IntoBackend: TypeAlias = "BackendName | Implementation | ModuleType"

    EagerAllowedNamespace: TypeAlias = "Namespace[PandasLikeNamespace] | Namespace[ArrowNamespace] | Namespace[PolarsNamespace]"
    EagerAllowedImplementation: TypeAlias = Literal[
        Implementation.PANDAS,
        Implementation.CUDF,
        Implementation.MODIN,
        Implementation.PYARROW,
        Implementation.POLARS,
    ]

    class _BasePandasLike(Sized, Protocol):
        index: Any
        """`mypy` doesn't like the asymmetric `property` setter in `pandas`."""

        def __getitem__(self, key: Any, /) -> Any: ...
        def __mul__(self, other: float | Collection[float] | Self) -> Self: ...
        def __floordiv__(self, other: float | Collection[float] | Self) -> Self: ...
        @property
        def loc(self) -> Any: ...
        @property
        def shape(self) -> tuple[int, ...]: ...
        def set_axis(self, labels: Any, *, axis: Any = ..., copy: bool = ...) -> Self: ...
        def copy(self, deep: bool = ...) -> Self: ...  # noqa: FBT001
        def rename(self, *args: Any, inplace: Literal[False], **kwds: Any) -> Self:
            """`inplace=False` is required to avoid (incorrect?) default overloads."""
            ...

    class _BasePandasLikeFrame(NativeFrame, _BasePandasLike, Protocol): ...

    class _BasePandasLikeSeries(NativeSeries, _BasePandasLike, Protocol):
        def where(self, cond: Any, other: Any = ..., **kwds: Any) -> Any: ...

    class _NativeDask(Protocol):
        _partition_type: type[pd.DataFrame]

    class _CuDFDataFrame(_BasePandasLikeFrame, Protocol):
        def to_pylibcudf(self, *args: Any, **kwds: Any) -> Any: ...

    class _CuDFSeries(_BasePandasLikeSeries, Protocol):
        def to_pylibcudf(self, *args: Any, **kwds: Any) -> Any: ...

    class _NativeIbis(Protocol):
        def sql(self, *args: Any, **kwds: Any) -> Any: ...
        def __pyarrow_result__(self, *args: Any, **kwds: Any) -> Any: ...
        def __pandas_result__(self, *args: Any, **kwds: Any) -> Any: ...
        def __polars_result__(self, *args: Any, **kwds: Any) -> Any: ...

    class _ModinDataFrame(_BasePandasLikeFrame, Protocol):
        _pandas_class: type[pd.DataFrame]

    class _ModinSeries(_BasePandasLikeSeries, Protocol):
        _pandas_class: type[pd.Series[Any]]

    _NativePolars: TypeAlias = "pl.DataFrame | pl.LazyFrame | pl.Series"
    _NativeArrow: TypeAlias = "pa.Table | pa.ChunkedArray[Any]"
    _NativeDuckDB: TypeAlias = "duckdb.DuckDBPyRelation"
    _NativePandas: TypeAlias = "pd.DataFrame | pd.Series[Any]"
    _NativeModin: TypeAlias = "_ModinDataFrame | _ModinSeries"
    _NativeCuDF: TypeAlias = "_CuDFDataFrame | _CuDFSeries"
    _NativePandasLikeSeries: TypeAlias = "pd.Series[Any] | _CuDFSeries | _ModinSeries"
    _NativePandasLikeDataFrame: TypeAlias = (
        "pd.DataFrame | _CuDFDataFrame | _ModinDataFrame"
    )
    _NativePandasLike: TypeAlias = "_NativePandasLikeDataFrame |_NativePandasLikeSeries"
    _NativeSQLFrame: TypeAlias = "SQLFrameDataFrame"
    _NativePySpark: TypeAlias = "pyspark_sql.DataFrame"
    _NativePySparkConnect: TypeAlias = "PySparkConnectDataFrame"
    _NativeSparkLike: TypeAlias = (
        "_NativeSQLFrame | _NativePySpark | _NativePySparkConnect"
    )

    NativeKnown: TypeAlias = "_NativePolars | _NativeArrow | _NativePandasLike | _NativeSparkLike | _NativeDuckDB | _NativeDask | _NativeIbis"
    NativeUnknown: TypeAlias = (
        "NativeFrame | NativeSeries | NativeLazyFrame | DataFrameLike"
    )
    NativeAny: TypeAlias = "NativeKnown | NativeUnknown"

__all__ = ["Namespace"]


class Namespace(Generic[CompliantNamespaceT_co]):
    _compliant_namespace: CompliantNamespaceT_co
    _version: ClassVar[Version] = Version.MAIN

    def __init__(self, namespace: CompliantNamespaceT_co, /) -> None:
        self._compliant_namespace = namespace

    def __init_subclass__(cls, *args: Any, version: Version, **kwds: Any) -> None:
        super().__init_subclass__(*args, **kwds)

        if isinstance(version, Version):
            cls._version = version
        else:
            msg = f"Expected {Version} but got {type(version).__name__!r}"
            raise TypeError(msg)

    def __repr__(self) -> str:
        return f"Namespace[{type(self.compliant).__name__}]"

    @property
    def compliant(self) -> CompliantNamespaceT_co:
        return self._compliant_namespace

    @property
    def implementation(self) -> Implementation:
        return self.compliant._implementation

    @property
    def version(self) -> Version:
        return self._version

    @overload
    @classmethod
    def from_backend(cls, backend: PandasLike, /) -> Namespace[PandasLikeNamespace]: ...

    @overload
    @classmethod
    def from_backend(cls, backend: Polars, /) -> Namespace[PolarsNamespace]: ...

    @overload
    @classmethod
    def from_backend(cls, backend: Arrow, /) -> Namespace[ArrowNamespace]: ...

    @overload
    @classmethod
    def from_backend(cls, backend: SparkLike, /) -> Namespace[SparkLikeNamespace]: ...

    @overload
    @classmethod
    def from_backend(cls, backend: DuckDB, /) -> Namespace[DuckDBNamespace]: ...

    @overload
    @classmethod
    def from_backend(cls, backend: Dask, /) -> Namespace[DaskNamespace]: ...

    @overload
    @classmethod
    def from_backend(cls, backend: Ibis, /) -> Namespace[IbisNamespace]: ...

    @overload
    @classmethod
    def from_backend(cls, backend: EagerAllowed, /) -> EagerAllowedNamespace: ...

    @overload
    @classmethod
    def from_backend(
        cls, backend: IntoBackend, /
    ) -> Namespace[CompliantNamespaceAny]: ...

    @classmethod
    def from_backend(
        cls: type[Namespace[Any]], backend: IntoBackend, /
    ) -> Namespace[Any]:
        """Instantiate from native namespace module, string, or Implementation.

        Arguments:
            backend: native namespace module, string, or Implementation.

        Returns:
            Namespace.

        Examples:
            >>> from narwhals._namespace import Namespace
            >>> Namespace.from_backend("polars")
            Namespace[PolarsNamespace]
        """
        impl = Implementation.from_backend(backend)
        backend_version = impl._backend_version()  # noqa: F841
        version = cls._version
        ns: CompliantNamespaceAny
        if impl.is_pandas_like():
            from narwhals._pandas_like.namespace import PandasLikeNamespace

            ns = PandasLikeNamespace(implementation=impl, version=version)

        elif impl.is_polars():
            from narwhals._polars.namespace import PolarsNamespace

            ns = PolarsNamespace(version=version)
        elif impl.is_pyarrow():
            from narwhals._arrow.namespace import ArrowNamespace

            ns = ArrowNamespace(version=version)
        elif impl.is_spark_like():
            from narwhals._spark_like.namespace import SparkLikeNamespace

            ns = SparkLikeNamespace(implementation=impl, version=version)
        elif impl.is_duckdb():
            from narwhals._duckdb.namespace import DuckDBNamespace

            ns = DuckDBNamespace(version=version)
        elif impl.is_dask():
            from narwhals._dask.namespace import DaskNamespace

            ns = DaskNamespace(version=version)
        elif impl.is_ibis():
            from narwhals._ibis.namespace import IbisNamespace

            ns = IbisNamespace(version=version)
        else:
            msg = "Not supported Implementation"  # pragma: no cover
            raise AssertionError(msg)
        return cls(ns)

    @overload
    @classmethod
    def from_native_object(
        cls, native: _NativePolars, /
    ) -> Namespace[PolarsNamespace]: ...

    @overload
    @classmethod
    def from_native_object(
        cls, native: _NativePandas, /
    ) -> Namespace[PandasLikeNamespace[pd.DataFrame, pd.Series[Any]]]: ...

    @overload
    @classmethod
    def from_native_object(cls, native: _NativeArrow, /) -> Namespace[ArrowNamespace]: ...

    @overload
    @classmethod
    def from_native_object(
        cls, native: _NativeSparkLike, /
    ) -> Namespace[SparkLikeNamespace]: ...

    @overload
    @classmethod
    def from_native_object(
        cls, native: _NativeDuckDB, /
    ) -> Namespace[DuckDBNamespace]: ...

    @overload
    @classmethod
    def from_native_object(cls, native: _NativeDask, /) -> Namespace[DaskNamespace]: ...

    @overload
    @classmethod
    def from_native_object(cls, native: _NativeIbis, /) -> Namespace[IbisNamespace]: ...

    @overload
    @classmethod
    def from_native_object(
        cls, native: _NativeModin, /
    ) -> Namespace[PandasLikeNamespace[_ModinDataFrame, _ModinSeries]]: ...

    @overload
    @classmethod
    def from_native_object(
        cls, native: _NativeCuDF, /
    ) -> Namespace[PandasLikeNamespace[_CuDFDataFrame, _CuDFSeries]]: ...

    @overload
    @classmethod
    def from_native_object(
        cls, native: _NativePandasLike, /
    ) -> Namespace[PandasLikeNamespace[Any, Any]]: ...

    @overload
    @classmethod
    def from_native_object(
        cls, native: NativeUnknown, /
    ) -> Namespace[CompliantNamespaceAny]: ...

    @classmethod
    def from_native_object(
        cls: type[Namespace[Any]], native: NativeAny, /
    ) -> Namespace[Any]:
        if is_native_polars(native):
            impl = Implementation.POLARS
        elif is_native_pandas(native):
            impl = Implementation.PANDAS
        elif is_native_arrow(native):
            impl = Implementation.PYARROW
        elif is_native_spark_like(native):
            impl = (
                Implementation.SQLFRAME
                if is_native_sqlframe(native)
                else Implementation.PYSPARK_CONNECT
                if is_native_pyspark_connect(native)
                else Implementation.PYSPARK
            )
        elif is_native_dask(native):  # pragma: no cover
            impl = Implementation.DASK
        elif is_native_duckdb(native):
            impl = Implementation.DUCKDB
        elif is_native_cudf(native):  # pragma: no cover
            impl = Implementation.CUDF
        elif is_native_modin(native):  # pragma: no cover
            impl = Implementation.MODIN
        elif is_native_ibis(native):
            impl = Implementation.IBIS
        else:
            msg = f"Unsupported type: {type(native).__qualname__!r}"
            raise TypeError(msg)
        return cls.from_backend(impl)


def is_native_polars(obj: Any) -> TypeIs[_NativePolars]:
    return (pl := get_polars()) is not None and isinstance(
        obj, (pl.DataFrame, pl.Series, pl.LazyFrame)
    )


def is_native_arrow(obj: Any) -> TypeIs[_NativeArrow]:
    return (pa := get_pyarrow()) is not None and isinstance(
        obj, (pa.Table, pa.ChunkedArray)
    )


def is_native_dask(obj: Any) -> TypeIs[_NativeDask]:
    return is_dask_dataframe(obj)


is_native_duckdb: _Guard[_NativeDuckDB] = is_duckdb_relation
is_native_sqlframe: _Guard[_NativeSQLFrame] = is_sqlframe_dataframe
is_native_pyspark: _Guard[_NativePySpark] = is_pyspark_dataframe
is_native_pyspark_connect: _Guard[_NativePySparkConnect] = is_pyspark_connect_dataframe


def is_native_pandas(obj: Any) -> TypeIs[_NativePandas]:
    return (pd := get_pandas()) is not None and isinstance(obj, (pd.DataFrame, pd.Series))


def is_native_modin(obj: Any) -> TypeIs[_NativeModin]:
    return (mpd := get_modin()) is not None and isinstance(
        obj, (mpd.DataFrame, mpd.Series)
    )  # pragma: no cover


def is_native_cudf(obj: Any) -> TypeIs[_NativeCuDF]:
    return (cudf := get_cudf()) is not None and isinstance(
        obj, (cudf.DataFrame, cudf.Series)
    )  # pragma: no cover


def is_native_pandas_like(obj: Any) -> TypeIs[_NativePandasLike]:
    return (
        is_native_pandas(obj) or is_native_cudf(obj) or is_native_modin(obj)
    )  # pragma: no cover


def is_native_spark_like(obj: Any) -> TypeIs[_NativeSparkLike]:
    return (
        is_native_sqlframe(obj)
        or is_native_pyspark(obj)
        or is_native_pyspark_connect(obj)
    )


def is_native_ibis(obj: Any) -> TypeIs[_NativeIbis]:
    return is_ibis_table(obj)
