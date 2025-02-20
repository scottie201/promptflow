import functools
import inspect
import os
from pathlib import Path

from promptflow._core.tool import STREAMING_OPTION_PARAMETER_ATTR, ToolType
from promptflow._core.tracer import TraceType, _create_trace_from_function_call
from promptflow._utils.utils import is_in_ci_pipeline

from .record_storage import (
    Counter,
    RecordFileMissingException,
    RecordItemMissingException,
    RecordStorage,
    is_live,
    is_record,
    is_replay,
)

COUNT_RECORD = (Path(__file__) / "../../count.json").resolve()

# recording array is a global variable to store the function names that need to be recorded
recording_array = ["fetch_text_content_from_url", "my_python_tool"]


def recording_array_extend(items):
    global recording_array
    recording_array.extend(items)


def recording_array_reset():
    global recording_array
    recording_array = ["fetch_text_content_from_url", "my_python_tool"]


def _prepare_input_dict(func, args, kwargs):
    """Prepare input dict for record storage"""
    if func.__name__ == "partial":
        func_wo_partial = func.func
    else:
        func_wo_partial = func
    input_dict = {}
    for key in kwargs:
        input_dict[key] = kwargs[key]
    if type(func).__name__ == "partial":
        input_dict["_args"] = func.args
        for key in func.keywords:
            input_dict[key] = func.keywords[key]
    else:
        input_dict["_args"] = []
    input_dict["_func"] = func_wo_partial.__qualname__
    return input_dict


def _replace_tool_rule(func):
    """Replace tool with the following rules."""
    global recording_array
    if func.__name__ == "partial":
        func_wo_partial = func.func
    else:
        func_wo_partial = func

    if func_wo_partial.__qualname__ in recording_array:
        return True
    else:
        return False


def call_func(func, args, kwargs):
    input_dict = _prepare_input_dict(func, args, kwargs)
    if is_replay():
        return RecordStorage.get_instance().get_record(input_dict)
    # Record mode will record item to record file
    elif is_record():
        try:
            # prevent recording the same item twice
            obj = RecordStorage.get_instance().get_record(input_dict)
        except (RecordItemMissingException, RecordFileMissingException):
            # recording the item
            obj = RecordStorage.get_instance().set_record(input_dict, func(*args, **kwargs))
    elif is_live() and is_in_ci_pipeline():
        obj = Counter.get_instance().set_file_record_count(COUNT_RECORD, func(*args, **kwargs))
    else:
        obj = func(*args, **kwargs)
    return obj


async def call_func_async(func, args, kwargs):
    input_dict = _prepare_input_dict(func, args, kwargs)
    if is_replay():
        return RecordStorage.get_instance().get_record(input_dict)
    # Record mode will record item to record file
    elif is_record():
        try:
            # prevent recording the same item twice
            obj = RecordStorage.get_instance().get_record(input_dict)
        except (RecordItemMissingException, RecordFileMissingException):
            # recording the item
            obj = RecordStorage.get_instance().set_record(input_dict, await func(*args, **kwargs))
    elif is_live() and is_in_ci_pipeline():
        obj = Counter.get_instance().set_file_record_count(COUNT_RECORD, await func(*args, **kwargs))
    else:
        obj = await func(*args, **kwargs)
    return obj


def delete_count_lock_file():
    lock_file = str(COUNT_RECORD) + ".lock"
    if os.path.isfile(lock_file):
        os.remove(lock_file)


def mock_tool(original_tool):
    """
    Basically this is the original tool decorator.

    The key modification is, at every func(*args, **argv) call. There is a surrounding record/replay logic:
        if replay:
            return replay:
        elif record:
            if recorded:
                return recorded
            call func(*args, **argv) and record the result

    Actually it needn't to be such a long function, but tool decorator should not trigger a long stack trace.
    """

    def tool(
        func=None,
        *args_mock,
        name: str = None,
        description: str = None,
        type: str = None,
        input_settings=None,
        streaming_option_parameter=None,
        **kwargs_mock,
    ):
        def tool_decorator(func):
            from promptflow.exceptions import UserErrorException

            def create_trace(func, args, kwargs):
                return _create_trace_from_function_call(func, args=args, kwargs=kwargs, trace_type=TraceType.TOOL)

            if inspect.iscoroutinefunction(func):

                @functools.wraps(func)
                async def decorated_tool(*args, **kwargs):
                    from promptflow._core.tracer import Tracer

                    if Tracer.active_instance() is None:
                        return await call_func_async(func, args, kwargs)
                    try:
                        Tracer.push(create_trace(func, args, kwargs))
                        output = await call_func_async(func, args, kwargs)
                        return Tracer.pop(output)
                    except Exception as e:
                        Tracer.pop(None, e)
                        raise

                new_f = decorated_tool
            else:

                @functools.wraps(func)
                def decorated_tool(*args, **kwargs):
                    from promptflow._core.tracer import Tracer

                    if Tracer.active_instance() is None:
                        return call_func(func, args, kwargs)
                    try:
                        Tracer.push(create_trace(func, args, kwargs))
                        output = call_func(func, args, kwargs)
                        return Tracer.pop(output)
                    except Exception as e:
                        Tracer.pop(None, e)
                        raise

                new_f = decorated_tool

            if type is not None and type not in [k.value for k in ToolType]:
                raise UserErrorException(f"Tool type {type} is not supported yet.")

            new_f.__original_function = func
            new_f.__tool = None  # This will be set when generating the tool definition.
            new_f.__name = name
            new_f.__description = description
            new_f.__type = type
            new_f.__input_settings = input_settings
            new_f.__extra_info = kwargs_mock
            if streaming_option_parameter and isinstance(streaming_option_parameter, str):
                setattr(new_f, STREAMING_OPTION_PARAMETER_ATTR, streaming_option_parameter)

            return new_f

        # tool replacements.
        if func is not None:
            if _replace_tool_rule(func):
                return tool_decorator(func)
            else:
                return original_tool(
                    func,
                    *args_mock,
                    name=name,
                    description=description,
                    type=type,
                    input_settings=input_settings,
                    **kwargs_mock,
                )
        return original_tool(  # no recording for @tool(name="func_name")
            func,
            *args_mock,
            name=name,
            description=description,
            type=type,
            input_settings=input_settings,
            **kwargs_mock,
        )

    return tool
