from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Literal, Protocol, cast

from narwhals._compliant.expr import LazyExpr
from narwhals._compliant.typing import (
    AliasNames,
    EvalNames,
    EvalSeries,
    NativeExprT,
    WindowFunction,
)
from narwhals._compliant.window import WindowInputs
from narwhals._expression_parsing import (
    combine_alias_output_names,
    combine_evaluate_output_names,
)
from narwhals._sql.typing import SQLLazyFrameT
from narwhals._utils import Implementation, Version, not_implemented

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from typing_extensions import Self, TypeIs

    from narwhals._compliant.typing import AliasNames, WindowFunction
    from narwhals._expression_parsing import ExprMetadata
    from narwhals._sql.namespace import SQLNamespace
    from narwhals.typing import NumericLiteral, PythonLiteral, RankMethod, TemporalLiteral


class SQLExpr(LazyExpr[SQLLazyFrameT, NativeExprT], Protocol[SQLLazyFrameT, NativeExprT]):
    _call: EvalSeries[SQLLazyFrameT, NativeExprT]
    _evaluate_output_names: EvalNames[SQLLazyFrameT]
    _alias_output_names: AliasNames | None
    _version: Version
    _implementation: Implementation
    _metadata: ExprMetadata | None
    _window_function: WindowFunction[SQLLazyFrameT, NativeExprT] | None

    def __init__(
        self,
        call: EvalSeries[SQLLazyFrameT, NativeExprT],
        window_function: WindowFunction[SQLLazyFrameT, NativeExprT] | None = None,
        *,
        evaluate_output_names: EvalNames[SQLLazyFrameT],
        alias_output_names: AliasNames | None,
        version: Version,
        implementation: Implementation = Implementation.DUCKDB,
    ) -> None: ...

    def __call__(self, df: SQLLazyFrameT) -> Sequence[NativeExprT]:
        return self._call(df)

    def __narwhals_namespace__(
        self,
    ) -> SQLNamespace[SQLLazyFrameT, Self, Any, NativeExprT]: ...

    def _callable_to_eval_series(
        self, call: Callable[..., NativeExprT], /, **expressifiable_args: Self | Any
    ) -> EvalSeries[SQLLazyFrameT, NativeExprT]:
        def func(df: SQLLazyFrameT) -> list[NativeExprT]:
            native_series_list = self(df)
            other_native_series = {
                key: df._evaluate_expr(value)
                if self._is_expr(value)
                else self._lit(value)
                for key, value in expressifiable_args.items()
            }
            return [
                call(native_series, **other_native_series)
                for native_series in native_series_list
            ]

        return func

    def _push_down_window_function(
        self, call: Callable[..., NativeExprT], /, **expressifiable_args: Self | Any
    ) -> WindowFunction[SQLLazyFrameT, NativeExprT]:
        def window_f(
            df: SQLLazyFrameT, window_inputs: WindowInputs[NativeExprT]
        ) -> Sequence[NativeExprT]:
            # If a function `f` is elementwise, and `g` is another function, then
            # - `f(g) over (window)`
            # - `f(g over (window))
            # are equivalent.
            # Make sure to only use with if `call` is elementwise!
            native_series_list = self.window_function(df, window_inputs)
            other_native_series = {
                key: df._evaluate_window_expr(value, window_inputs)
                if self._is_expr(value)
                else self._lit(value)
                for key, value in expressifiable_args.items()
            }
            return [
                call(native_series, **other_native_series)
                for native_series in native_series_list
            ]

        return window_f

    def _with_window_function(
        self, window_function: WindowFunction[SQLLazyFrameT, NativeExprT]
    ) -> Self:
        return self.__class__(
            self._call,
            window_function,
            evaluate_output_names=self._evaluate_output_names,
            alias_output_names=self._alias_output_names,
            version=self._version,
            implementation=self._implementation,
        )

    def _with_callable(
        self, call: Callable[..., NativeExprT], /, **expressifiable_args: Self | Any
    ) -> Self:
        return self.__class__(
            self._callable_to_eval_series(call, **expressifiable_args),
            evaluate_output_names=self._evaluate_output_names,
            alias_output_names=self._alias_output_names,
            version=self._version,
            implementation=self._implementation,
        )

    def _with_elementwise(
        self, call: Callable[..., NativeExprT], /, **expressifiable_args: Self | Any
    ) -> Self:
        return self.__class__(
            self._callable_to_eval_series(call, **expressifiable_args),
            self._push_down_window_function(call, **expressifiable_args),
            evaluate_output_names=self._evaluate_output_names,
            alias_output_names=self._alias_output_names,
            version=self._version,
            implementation=self._implementation,
        )

    def _with_binary(self, op: Callable[..., NativeExprT], other: Self | Any) -> Self:
        return self.__class__(
            self._callable_to_eval_series(op, other=other),
            self._push_down_window_function(op, other=other),
            evaluate_output_names=self._evaluate_output_names,
            alias_output_names=self._alias_output_names,
            version=self._version,
            implementation=self._implementation,
        )

    def _with_alias_output_names(self, func: AliasNames | None, /) -> Self:
        current_alias_output_names = self._alias_output_names
        alias_output_names = (
            None
            if func is None
            else func
            if current_alias_output_names is None
            else lambda output_names: func(current_alias_output_names(output_names))
        )
        return type(self)(
            self._call,
            self._window_function,
            evaluate_output_names=self._evaluate_output_names,
            alias_output_names=alias_output_names,
            version=self._version,
            implementation=self._implementation,
        )

    @property
    def window_function(self) -> WindowFunction[SQLLazyFrameT, NativeExprT]:
        def default_window_func(
            df: SQLLazyFrameT, inputs: WindowInputs[NativeExprT]
        ) -> Sequence[NativeExprT]:
            assert not inputs.order_by  # noqa: S101
            return [
                self._window_expression(expr, inputs.partition_by, inputs.order_by)
                for expr in self(df)
            ]

        return self._window_function or default_window_func

    def _function(self, name: str, *args: NativeExprT | PythonLiteral) -> NativeExprT:
        return self.__narwhals_namespace__()._function(name, *args)

    def _lit(self, value: Any) -> NativeExprT:
        return self.__narwhals_namespace__()._lit(value)

    def _coalesce(self, *expr: NativeExprT) -> NativeExprT:
        return self.__narwhals_namespace__()._coalesce(*expr)

    def _count_star(self) -> NativeExprT: ...

    def _when(
        self,
        condition: NativeExprT,
        value: NativeExprT,
        otherwise: NativeExprT | None = None,
    ) -> NativeExprT:
        return self.__narwhals_namespace__()._when(condition, value, otherwise)

    def _window_expression(
        self,
        expr: NativeExprT,
        partition_by: Sequence[str | NativeExprT] = (),
        order_by: Sequence[str | NativeExprT] = (),
        rows_start: int | None = None,
        rows_end: int | None = None,
        *,
        descending: Sequence[bool] | None = None,
        nulls_last: Sequence[bool] | None = None,
    ) -> NativeExprT: ...

    def _cum_window_func(
        self,
        func_name: Literal["sum", "max", "min", "count", "product"],
        *,
        reverse: bool,
    ) -> WindowFunction[SQLLazyFrameT, NativeExprT]:
        def func(
            df: SQLLazyFrameT, inputs: WindowInputs[NativeExprT]
        ) -> Sequence[NativeExprT]:
            return [
                self._window_expression(
                    self._function(func_name, expr),
                    inputs.partition_by,
                    inputs.order_by,
                    descending=[reverse] * len(inputs.order_by),
                    nulls_last=[reverse] * len(inputs.order_by),
                    rows_end=0,
                )
                for expr in self(df)
            ]

        return func

    def _rolling_window_func(
        self,
        func_name: Literal["sum", "mean", "std", "var"],
        window_size: int,
        min_samples: int,
        ddof: int | None = None,
        *,
        center: bool,
    ) -> WindowFunction[SQLLazyFrameT, NativeExprT]:
        supported_funcs = ["sum", "mean", "std", "var"]
        if center:
            half = (window_size - 1) // 2
            remainder = (window_size - 1) % 2
            start = -(half + remainder)
            end = half
        else:
            start = -(window_size - 1)
            end = 0

        def func(
            df: SQLLazyFrameT, inputs: WindowInputs[NativeExprT]
        ) -> Sequence[NativeExprT]:
            if func_name in {"sum", "mean"}:
                func_: str = func_name
            elif func_name == "var" and ddof == 0:
                func_ = "var_pop"
            elif func_name in "var" and ddof == 1:
                func_ = "var_samp"
            elif func_name == "std" and ddof == 0:
                func_ = "stddev_pop"
            elif func_name == "std" and ddof == 1:
                func_ = "stddev_samp"
            elif func_name in {"var", "std"}:  # pragma: no cover
                msg = f"Only ddof=0 and ddof=1 are currently supported for rolling_{func_name}."
                raise ValueError(msg)
            else:  # pragma: no cover
                msg = f"Only the following functions are supported: {supported_funcs}.\nGot: {func_name}."
                raise ValueError(msg)
            window_kwargs: Any = {
                "partition_by": inputs.partition_by,
                "order_by": inputs.order_by,
                "rows_start": start,
                "rows_end": end,
            }
            return [
                self._when(
                    self._window_expression(  # type: ignore[operator]
                        self._function("count", expr), **window_kwargs
                    )
                    >= self._lit(min_samples),
                    self._window_expression(self._function(func_, expr), **window_kwargs),
                )
                for expr in self(df)
            ]

        return func

    @classmethod
    def _is_expr(cls, obj: Self | Any) -> TypeIs[Self]:
        return hasattr(obj, "__narwhals_expr__")

    @property
    def _backend_version(self) -> tuple[int, ...]:
        return self._implementation._backend_version()

    @classmethod
    def _alias_native(cls, expr: NativeExprT, name: str, /) -> NativeExprT: ...

    @classmethod
    def _from_elementwise_horizontal_op(
        cls, func: Callable[[Iterable[NativeExprT]], NativeExprT], *exprs: Self
    ) -> Self:
        def call(df: SQLLazyFrameT) -> Sequence[NativeExprT]:
            cols = (col for _expr in exprs for col in _expr(df))
            return [func(cols)]

        def window_function(
            df: SQLLazyFrameT, window_inputs: WindowInputs[NativeExprT]
        ) -> Sequence[NativeExprT]:
            cols = (
                col for _expr in exprs for col in _expr.window_function(df, window_inputs)
            )
            return [func(cols)]

        context = exprs[0]
        return cls(
            call,
            window_function=window_function,
            evaluate_output_names=combine_evaluate_output_names(*exprs),
            alias_output_names=combine_alias_output_names(*exprs),
            version=context._version,
            implementation=context._implementation,
        )

    # Binary
    def __eq__(self, other: Self) -> Self:  # type: ignore[override]
        return self._with_binary(lambda expr, other: expr.__eq__(other), other)

    def __ne__(self, other: Self) -> Self:  # type: ignore[override]
        return self._with_binary(lambda expr, other: expr.__ne__(other), other)

    def __add__(self, other: Self) -> Self:
        return self._with_binary(lambda expr, other: expr.__add__(other), other)

    def __sub__(self, other: Self) -> Self:
        return self._with_binary(lambda expr, other: expr.__sub__(other), other)

    def __rsub__(self, other: Self) -> Self:
        return self._with_binary(lambda expr, other: other - expr, other).alias("literal")

    def __mul__(self, other: Self) -> Self:
        return self._with_binary(lambda expr, other: expr.__mul__(other), other)

    def __truediv__(self, other: Self) -> Self:
        return self._with_binary(lambda expr, other: expr.__truediv__(other), other)

    def __rtruediv__(self, other: Self) -> Self:
        return self._with_binary(lambda expr, other: other / expr, other).alias("literal")

    def __floordiv__(self, other: Self) -> Self:
        return self._with_binary(lambda expr, other: expr.__floordiv__(other), other)

    def __rfloordiv__(self, other: Self) -> Self:
        return self._with_binary(lambda expr, other: other // expr, other).alias(
            "literal"
        )

    def __pow__(self, other: Self) -> Self:
        return self._with_binary(lambda expr, other: expr.__pow__(other), other)

    def __rpow__(self, other: Self) -> Self:
        return self._with_binary(lambda expr, other: other**expr, other).alias("literal")

    def __mod__(self, other: Self) -> Self:
        return self._with_binary(lambda expr, other: expr.__mod__(other), other)

    def __rmod__(self, other: Self) -> Self:
        return self._with_binary(lambda expr, other: other % expr, other).alias("literal")

    def __ge__(self, other: Self) -> Self:
        return self._with_binary(lambda expr, other: expr.__ge__(other), other)

    def __gt__(self, other: Self) -> Self:
        return self._with_binary(lambda expr, other: expr.__gt__(other), other)

    def __le__(self, other: Self) -> Self:
        return self._with_binary(lambda expr, other: expr.__le__(other), other)

    def __lt__(self, other: Self) -> Self:
        return self._with_binary(lambda expr, other: expr.__lt__(other), other)

    def __and__(self, other: Self) -> Self:
        return self._with_binary(lambda expr, other: expr.__and__(other), other)

    def __or__(self, other: Self) -> Self:
        return self._with_binary(lambda expr, other: expr.__or__(other), other)

    # Aggregations
    def all(self) -> Self:
        def f(expr: NativeExprT) -> NativeExprT:
            return self._coalesce(self._function("bool_and", expr), self._lit(True))  # noqa: FBT003

        def window_f(
            df: SQLLazyFrameT, inputs: WindowInputs[NativeExprT]
        ) -> Sequence[NativeExprT]:
            return [
                self._coalesce(
                    self._window_expression(
                        self._function("bool_and", expr), inputs.partition_by
                    ),
                    self._lit(True),  # noqa: FBT003
                )
                for expr in self(df)
            ]

        return self._with_callable(f)._with_window_function(window_f)

    def any(self) -> Self:
        def f(expr: NativeExprT) -> NativeExprT:
            return self._coalesce(self._function("bool_or", expr), self._lit(False))  # noqa: FBT003

        def window_f(
            df: SQLLazyFrameT, inputs: WindowInputs[NativeExprT]
        ) -> Sequence[NativeExprT]:
            return [
                self._coalesce(
                    self._window_expression(
                        self._function("bool_or", expr), inputs.partition_by
                    ),
                    self._lit(False),  # noqa: FBT003
                )
                for expr in self(df)
            ]

        return self._with_callable(f)._with_window_function(window_f)

    def max(self) -> Self:
        return self._with_callable(lambda expr: self._function("max", expr))

    def mean(self) -> Self:
        return self._with_callable(lambda expr: self._function("mean", expr))

    def median(self) -> Self:
        return self._with_callable(lambda expr: self._function("median", expr))

    def min(self) -> Self:
        return self._with_callable(lambda expr: self._function("min", expr))

    def count(self) -> Self:
        return self._with_callable(lambda expr: self._function("count", expr))

    def sum(self) -> Self:
        def f(expr: NativeExprT) -> NativeExprT:
            return self._coalesce(self._function("sum", expr), self._lit(0))

        def window_f(
            df: SQLLazyFrameT, inputs: WindowInputs[NativeExprT]
        ) -> Sequence[NativeExprT]:
            return [
                self._coalesce(
                    self._window_expression(
                        self._function("sum", expr), inputs.partition_by
                    ),
                    self._lit(0),
                )
                for expr in self(df)
            ]

        return self._with_callable(f)._with_window_function(window_f)

    # Elementwise
    def abs(self) -> Self:
        return self._with_elementwise(lambda expr: self._function("abs", expr))

    def clip(
        self,
        lower_bound: Self | NumericLiteral | TemporalLiteral | None,
        upper_bound: Self | NumericLiteral | TemporalLiteral | None,
    ) -> Self:
        def _clip_lower(expr: NativeExprT, lower_bound: Any) -> NativeExprT:
            return self._function("greatest", expr, lower_bound)

        def _clip_upper(expr: NativeExprT, upper_bound: Any) -> NativeExprT:
            return self._function("least", expr, upper_bound)

        def _clip_both(
            expr: NativeExprT, lower_bound: Any, upper_bound: Any
        ) -> NativeExprT:
            return self._function(
                "greatest", self._function("least", expr, upper_bound), lower_bound
            )

        if lower_bound is None:
            return self._with_elementwise(_clip_upper, upper_bound=upper_bound)
        if upper_bound is None:
            return self._with_elementwise(_clip_lower, lower_bound=lower_bound)
        return self._with_elementwise(
            _clip_both, lower_bound=lower_bound, upper_bound=upper_bound
        )

    def is_null(self) -> Self:
        return self._with_elementwise(lambda expr: self._function("isnull", expr))

    def round(self, decimals: int) -> Self:
        return self._with_elementwise(
            lambda expr: self._function("round", expr, self._lit(decimals))
        )

    def sqrt(self) -> Self:
        def _sqrt(expr: NativeExprT) -> NativeExprT:
            return self._when(
                expr < self._lit(0),  # type: ignore[operator]
                self._lit(float("nan")),
                self._function("sqrt", expr),
            )

        return self._with_elementwise(_sqrt)

    def exp(self) -> Self:
        return self._with_elementwise(lambda expr: self._function("exp", expr))

    def log(self, base: float) -> Self:
        def _log(expr: NativeExprT) -> NativeExprT:
            return self._when(
                expr < self._lit(0),  # type: ignore[operator]
                self._lit(float("nan")),
                self._when(
                    cast("NativeExprT", expr == self._lit(0)),
                    self._lit(float("-inf")),
                    self._function("log", expr) / self._function("log", self._lit(base)),  # type: ignore[operator]
                ),
            )

        return self._with_elementwise(_log)

    # Cumulative
    def cum_sum(self, *, reverse: bool) -> Self:
        return self._with_window_function(self._cum_window_func("sum", reverse=reverse))

    def cum_max(self, *, reverse: bool) -> Self:
        return self._with_window_function(self._cum_window_func("max", reverse=reverse))

    def cum_min(self, *, reverse: bool) -> Self:
        return self._with_window_function(self._cum_window_func("min", reverse=reverse))

    def cum_count(self, *, reverse: bool) -> Self:
        return self._with_window_function(self._cum_window_func("count", reverse=reverse))

    def cum_prod(self, *, reverse: bool) -> Self:
        return self._with_window_function(
            self._cum_window_func("product", reverse=reverse)
        )

    # Rolling
    def rolling_sum(self, window_size: int, *, min_samples: int, center: bool) -> Self:
        return self._with_window_function(
            self._rolling_window_func("sum", window_size, min_samples, center=center)
        )

    def rolling_mean(self, window_size: int, *, min_samples: int, center: bool) -> Self:
        return self._with_window_function(
            self._rolling_window_func("mean", window_size, min_samples, center=center)
        )

    def rolling_var(
        self, window_size: int, *, min_samples: int, center: bool, ddof: int
    ) -> Self:
        return self._with_window_function(
            self._rolling_window_func(
                "var", window_size, min_samples, ddof=ddof, center=center
            )
        )

    def rolling_std(
        self, window_size: int, *, min_samples: int, center: bool, ddof: int
    ) -> Self:
        return self._with_window_function(
            self._rolling_window_func(
                "std", window_size, min_samples, ddof=ddof, center=center
            )
        )

    # Other window functions
    def diff(self) -> Self:
        def func(
            df: SQLLazyFrameT, inputs: WindowInputs[NativeExprT]
        ) -> Sequence[NativeExprT]:
            return [
                expr  # type: ignore[operator]
                - self._window_expression(
                    self._function("lag", expr), inputs.partition_by, inputs.order_by
                )
                for expr in self(df)
            ]

        return self._with_window_function(func)

    def shift(self, n: int) -> Self:
        def func(
            df: SQLLazyFrameT, inputs: WindowInputs[NativeExprT]
        ) -> Sequence[NativeExprT]:
            return [
                self._window_expression(
                    self._function("lag", expr, n), inputs.partition_by, inputs.order_by
                )
                for expr in self(df)
            ]

        return self._with_window_function(func)

    def is_first_distinct(self) -> Self:
        def func(
            df: SQLLazyFrameT, inputs: WindowInputs[NativeExprT]
        ) -> Sequence[NativeExprT]:
            # pyright checkers think the return type is `list[bool]` because of `==`
            return [
                cast(
                    "NativeExprT",
                    self._window_expression(
                        self._function("row_number"),
                        (*inputs.partition_by, expr),
                        inputs.order_by,
                    )
                    == self._lit(1),
                )
                for expr in self(df)
            ]

        return self._with_window_function(func)

    def is_last_distinct(self) -> Self:
        def func(
            df: SQLLazyFrameT, inputs: WindowInputs[NativeExprT]
        ) -> Sequence[NativeExprT]:
            return [
                cast(
                    "NativeExprT",
                    self._window_expression(
                        self._function("row_number"),
                        (*inputs.partition_by, expr),
                        inputs.order_by,
                        descending=[True] * len(inputs.order_by),
                        nulls_last=[True] * len(inputs.order_by),
                    )
                    == self._lit(1),
                )
                for expr in self(df)
            ]

        return self._with_window_function(func)

    def rank(self, method: RankMethod, *, descending: bool) -> Self:
        if method in {"min", "max", "average"}:
            func = self._function("rank")
        elif method == "dense":
            func = self._function("dense_rank")
        else:  # method == "ordinal"
            func = self._function("row_number")

        def _rank(
            expr: NativeExprT,
            partition_by: Sequence[str | NativeExprT] = (),
            order_by: Sequence[str | NativeExprT] = (),
            *,
            descending: Sequence[bool],
            nulls_last: Sequence[bool],
        ) -> NativeExprT:
            count_expr = self._count_star()
            window_kwargs: dict[str, Any] = {
                "partition_by": partition_by,
                "order_by": (expr, *order_by),
                "descending": descending,
                "nulls_last": nulls_last,
            }
            count_window_kwargs: dict[str, Any] = {"partition_by": (*partition_by, expr)}
            if method == "max":
                rank_expr = (
                    self._window_expression(func, **window_kwargs)  # type: ignore[operator]
                    + self._window_expression(count_expr, **count_window_kwargs)
                    - self._lit(1)
                )
            elif method == "average":
                rank_expr = self._window_expression(func, **window_kwargs) + (
                    self._window_expression(count_expr, **count_window_kwargs)  # type: ignore[operator]
                    - self._lit(1)
                ) / self._lit(2.0)
            else:
                rank_expr = self._window_expression(func, **window_kwargs)
            return self._when(~self._function("isnull", expr), rank_expr)  # type: ignore[operator]

        def _unpartitioned_rank(expr: NativeExprT) -> NativeExprT:
            return _rank(expr, descending=[descending], nulls_last=[True])

        def _partitioned_rank(
            df: SQLLazyFrameT, inputs: WindowInputs[NativeExprT]
        ) -> Sequence[NativeExprT]:
            # node: when `descending` / `nulls_last` are supported in `.over`, they should be respected here
            # https://github.com/narwhals-dev/narwhals/issues/2790
            return [
                _rank(
                    expr,
                    inputs.partition_by,
                    inputs.order_by,
                    descending=[descending] + [False] * len(inputs.order_by),
                    nulls_last=[True] + [False] * len(inputs.order_by),
                )
                for expr in self(df)
            ]

        return self._with_callable(_unpartitioned_rank)._with_window_function(
            _partitioned_rank
        )

    def is_unique(self) -> Self:
        def _is_unique(
            expr: NativeExprT, *partition_by: str | NativeExprT
        ) -> NativeExprT:
            return cast(
                "NativeExprT",
                self._window_expression(self._count_star(), (expr, *partition_by))
                == self._lit(1),
            )

        def _unpartitioned_is_unique(expr: NativeExprT) -> NativeExprT:
            return _is_unique(expr)

        def _partitioned_is_unique(
            df: SQLLazyFrameT, inputs: WindowInputs[NativeExprT]
        ) -> Sequence[NativeExprT]:
            assert not inputs.order_by  # noqa: S101
            return [_is_unique(expr, *inputs.partition_by) for expr in self(df)]

        return self._with_callable(_unpartitioned_is_unique)._with_window_function(
            _partitioned_is_unique
        )

    # Other
    def over(
        self, partition_by: Sequence[str | NativeExprT], order_by: Sequence[str]
    ) -> Self:
        def func(df: SQLLazyFrameT) -> Sequence[NativeExprT]:
            return self.window_function(df, WindowInputs(partition_by, order_by))

        return self.__class__(
            func,
            evaluate_output_names=self._evaluate_output_names,
            alias_output_names=self._alias_output_names,
            version=self._version,
            implementation=self._implementation,
        )

    arg_max: not_implemented = not_implemented()
    arg_min: not_implemented = not_implemented()
    arg_true: not_implemented = not_implemented()
    drop_nulls: not_implemented = not_implemented()
    ewm_mean: not_implemented = not_implemented()
    gather_every: not_implemented = not_implemented()
    head: not_implemented = not_implemented()
    map_batches: not_implemented = not_implemented()
    mode: not_implemented = not_implemented()
    replace_strict: not_implemented = not_implemented()
    sort: not_implemented = not_implemented()
    tail: not_implemented = not_implemented()
    sample: not_implemented = not_implemented()
    unique: not_implemented = not_implemented()

    # namespaces
    cat: not_implemented = not_implemented()  # type: ignore[assignment]
