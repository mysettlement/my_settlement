"""
Convenience functions for accessing the file path information of a script and allowing files to be imported
from paths relative to the caller.
"""

import inspect
import os
import sys
from pathlib import Path
from typing import Union, List, Any
import uuid
import warnings


class StringWithId(str):
    def __init__(self, arg: str) -> None:
        super().__init__()
        self.unique_id = uuid.uuid4()


def _this_dir(stack: List[inspect.FrameInfo]) -> Path:
    caller_info = stack[1]
    caller_globals = caller_info.frame.f_globals

    # Use os.path.abspath rather than Path.resolve, since Path.resolve will resolve symlinks to their sources
    if "__file__" in caller_globals:
        return Path(os.path.abspath(caller_globals["__file__"])).parent
    else:
        return Path(os.path.abspath(os.getcwd()))


def this_dir() -> Path:
    """
    This function mimics the @__DIR__ macro from Julia: https://docs.julialang.org/en/v1/base/file/#Base.@__DIR__
    Get a directory location associated with the caller of this function. If the caller is calling from a source
    code file, return the full path of the directory of that file, otherwise return the full path of the current
    working directory.
    """
    return _this_dir(inspect.stack())


class append_sys_path:
    """
    Resolve `relative_path` relative to the caller's directory path, and add it to sys.path. This will allow you to
    import files and modules directly from that directory. Note that previously defined import paths (such as the
    internal site-packages directory) will take importing preference; for inverse behaviour, use
    `prepend_sys_path`. This can be used as a context manager `with append_sys_path()` for temporary effect.
    """

    def __init__(self, relative_path: Union[str, Path] = ".") -> None:
        # Use os.path.abspath rather than Path.resolve, since Path.resolve will resolve symlinks to their sources
        self.added_path = StringWithId(
            os.path.abspath(Path(_this_dir(inspect.stack()), relative_path))
        )
        sys.path.append(self.added_path)

    def __enter__(self) -> None:
        pass

    def __exit__(self, *args: Any) -> None:
        i = len(sys.path) - 1
        while i >= 0:
            if (
                hasattr(sys.path[i], "unique_id")
                and getattr(sys.path[i], "unique_id") == self.added_path.unique_id
            ):
                sys.path.pop(i)
            i -= 1


class prepend_sys_path:
    """
    Resolve `relative_path` relative to the caller's directory path, and add it to sys.path. This will allow you to
    import files and modules directly from that directory. Note that this path takes preference over previously defined
    import paths (such as the internal site-packages directory); for inverse behaviour, use
    `append_sys_path`. This can be used as a context manager `with append_sys_path()` for temporary effect.
    """

    def __init__(self, relative_path: Union[str, Path] = ".") -> None:
        # Use os.path.abspath rather than Path.resolve, since Path.resolve will resolve symlinks to their sources
        self.added_path = StringWithId(
            os.path.abspath(Path(_this_dir(inspect.stack()), relative_path))
        )
        sys.path.insert(0, self.added_path)

    def __enter__(self) -> None:
        pass

    def __exit__(self, *args: Any) -> None:
        i = 0
        while i < len(sys.path):
            if (
                hasattr(sys.path[i], "unique_id")
                and getattr(sys.path[i], "unique_id") == self.added_path.unique_id
            ):
                sys.path.pop(i)
                i -= 1
            i += 1


def allow_relative_location_imports(relative_path: Union[str, Path] = ".") -> None:
    """
    Deprecated deprecated in favor of `append_sys_path`
    """
    warnings.warn(
        "`allow_relative_location_imports` is deprecated in favor of `append_sys_path` and will be removed locate "
        "2.0.0",
        category=DeprecationWarning,
    )
    sys.path.append(os.path.abspath(Path(_this_dir(inspect.stack()), relative_path)))


def force_relative_location_imports(relative_path: Union[str, Path] = ".") -> None:
    """
    Deprecated in favor of `prepend_sys_path`
    """
    warnings.warn(
        "`force_relative_location_imports` is deprecated in favor of `prepend_sys_path` and will be removed in locate "
        "2.0.0",
        category=DeprecationWarning,
    )
    sys.path.insert(0, os.path.abspath(Path(_this_dir(inspect.stack()), relative_path)))
