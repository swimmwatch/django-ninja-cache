import typing

HeaderType = typing.Dict[str, typing.Any]
PathParamsType = typing.Dict[str, typing.Any]
URLParamsType = typing.Dict[str, typing.Sequence[str]]


class SupportsStr(typing.Protocol):
    def __str__(self) -> str: ...
