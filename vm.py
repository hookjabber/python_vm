"""
Simplified VM code which works for some cases.
You need extend/rewrite code to pass all cases.
"""

import builtins
import dis
import types
import typing as tp


class Frame:
    """
    Frame header in cpython with description
        https://github.com/python/cpython/blob/3.11/Include/frameobject.h

    Text description of frame parameters
        https://docs.python.org/3/library/inspect.html?highlight=frame#types-and-members
    """
    ERR_TOO_MANY_POS_ARGS = 'Too many positional arguments'
    ERR_TOO_MANY_KW_ARGS = 'Too many keyword arguments'
    ERR_MULT_VALUES_FOR_ARG = 'Multiple values for arguments'
    ERR_MISSING_POS_ARGS = 'Missing positional arguments'
    ERR_MISSING_KWONLY_ARGS = 'Missing keyword-only arguments'
    ERR_POSONLY_PASSED_AS_KW = 'Positional-only argument passed as keyword argument'

    def __init__(self,
                 frame_code: types.CodeType,
                 frame_builtins: dict[str, tp.Any],
                 frame_globals: dict[str, tp.Any],
                 frame_locals: dict[str, tp.Any]) -> None:
        self.code = frame_code
        self.builtins = frame_builtins
        self.globals = frame_globals
        self.locals = frame_locals
        self.data_stack: tp.Any = []
        self.return_value = None
        self.index: dict[int, int] = dict()
        self._BINARIES = \
            {0: lambda x, y: x + y,
             10: lambda x, y: x - y,
             5: lambda x, y: x * y,
             11: lambda x, y: x / y,
             2: lambda x, y: x // y,
             6: lambda x, y: x % y,
             4: lambda x, y: x @ y,
             8: lambda x, y: x ** y,
             3: lambda x, y: x << y,
             9: lambda x, y: x >> y,
             1: lambda x, y: x & y,
             7: lambda x, y: x | y,
             12: lambda x, y: x ^ y,
             13: lambda x, y: x.__add__(y),
             23: lambda x, y: x.__sub__(y),
             18: lambda x, y: x.__mul__(y),
             24: lambda x, y: x.__truediv__(y),
             15: lambda x, y: x.__floordiv__(y),
             19: lambda x, y: x.__mod__(y),
             17: lambda x, y: x.__matmul__(y),
             21: lambda x, y: x.__pow__(y),
             16: lambda x, y: x.__lshift__(y),
             22: lambda x, y: x.__rshift__(y),
             14: lambda x, y: x.__and__(y),
             20: lambda x, y: x.__or__(y),
             25: lambda x, y: x.__xor__(y)
             }

        self._COMPARE = {
            0: lambda x, y: x.__lt__(y),
            1: lambda x, y: x.__le__(y),
            2: lambda x, y: x.__eq__(y),
            3: lambda x, y: x.__ne__(y),
            4: lambda x, y: x.__gt__(y),
            5: lambda x, y: x.__ge__(y)
        }
        self._ARG = {"binary_op_op", "compare_op_op", "format_value_op", "kw_names_op"}
        self._TWO_PARAMS_FUNC = {"load_global_op"}
        self.counter = 0
        self.last_raised_exception = None
        self.kw_names: tuple[tp.Any, ...] = tuple()

    def top(self) -> tp.Any:
        return self.data_stack[-1]

    def pop(self) -> tp.Any:
        return self.data_stack.pop()

    def push(self, *values: tp.Any) -> None:
        self.data_stack.extend(values)

    def popn(self, n: int) -> tp.Any:
        """
        Pop a number of values from the value stack.
        A list of n values is returned, the deepest value first.
        """
        if n > 0:
            returned = self.data_stack[-n:]
            self.data_stack[-n:] = []
            return returned
        else:
            return []

    def run(self) -> tp.Any:
        ins_lst = list(dis.get_instructions(self.code))
        for i in range(len(ins_lst)):
            self.index[ins_lst[i].offset] = i
        while True:
            if self.counter >= len(ins_lst):
                break

            func_name = ins_lst[self.counter].opname.lower() + "_op"

            if func_name in self._TWO_PARAMS_FUNC:
                getattr(self, func_name)(ins_lst[self.counter].arg, ins_lst[self.counter].argval)
            elif func_name in self._ARG:
                getattr(self, func_name)(ins_lst[self.counter].arg)
            else:
                getattr(self, func_name)(ins_lst[self.counter].argval)
                if func_name == "return_value_op":
                    break

            self.counter += 1

        return self.return_value

    def resume_op(self, nothing: tp.Any) -> tp.Any:
        pass

    def push_null_op(self, nothing: tp.Any) -> tp.Any:
        self.push(None)

    def precall_op(self, nothing: tp.Any) -> tp.Any:
        pass

    def call_op(self, argc: int) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.11.5/library/dis.html#opcode-CALL
        """
        all_args = self.popn(argc)
        args = all_args
        kwargs: dict[str, tp.Any] = dict()

        if self.kw_names:
            args = all_args[:len(all_args) - len(self.kw_names)]
            kwargs = dict(zip(self.kw_names, all_args[-len(self.kw_names):]))

        func = self.pop()
        if self.top() is None:
            self.pop()
            result = func(*args, **kwargs)
            self.push(result)
        else:
            obj = func
            func = self.pop()
            result = func(obj, *args, **kwargs)
            self.push(result)

    def load_name_op(self, namei: str) -> None:
        """
        Partial realization

        Operation description:
            https://docs.python.org/release/3.11.5/library/dis.html#opcode-LOAD_NAME
        """
        if namei in self.locals:
            self.push(self.locals[namei])
        elif namei in self.globals:
            self.push(self.globals[namei])
        elif namei in self.builtins:
            self.push(self.builtins[namei])
        else:
            raise NameError

    def load_global_op(self, namei: int, val: str) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.11.5/library/dis.html#opcode-LOAD_GLOBAL
        """
        if (namei & 1) == 1:
            self.push_null_op(0)
        if val in self.globals:
            self.push(self.globals[val])
        elif val in self.builtins:
            self.push(self.builtins[val])
        else:
            raise NameError

    def load_const_op(self, consti: tp.Any) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.11.5/library/dis.html#opcode-LOAD_CONST
        """
        self.push(consti)

    def return_value_op(self, nothing: tp.Any) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.11.5/library/dis.html#opcode-RETURN_VALUE
        """
        self.return_value = self.pop()

    def pop_top_op(self, nothing: tp.Any) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.11.5/library/dis.html#opcode-POP_TOP
        """
        self.pop()

    def make_function_op(self, flags: int) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.11.5/library/dis.html#opcode-MAKE_FUNCTION
        """
        code = self.pop()  # the code associated with the function (at TOS1)

        args_default: tuple[tp.Any, ...] = tuple()
        kwargs_default: dict[tp.Any, tp.Any] = dict()

        if flags & 1:
            args_default = self.pop()
        if flags & 2:
            kwargs_default = self.pop()

        def f(*args: tp.Any, **kwargs: tp.Any) -> tp.Any:
            # from arg_binding :P

            parsed_args: dict[str, tp.Any] = {}
            names = code.co_varnames
            arg_count = code.co_argcount
            pos_only_count = code.co_posonlyargcount
            kw_only_count = code.co_kwonlyargcount
            default_values: tuple[tp.Any, ...] = args_default
            local_variables = code.co_nlocals
            kw_default_values = kwargs_default
            has_varargs: bool = bool(code.co_flags & 4)
            has_varkw: bool = bool(code.co_flags & 8)
            shift = arg_count + kw_only_count - local_variables

            if has_varargs:
                vararg_name = names[shift]
                parsed_args[vararg_name] = ()
                shift += 1

            if has_varkw:
                varkw_name = names[shift]
                parsed_args[varkw_name] = {}
                shift += 1

            if len(args) > arg_count:
                if not has_varargs:
                    raise TypeError(Frame.ERR_TOO_MANY_POS_ARGS)
                else:
                    parsed_args[vararg_name] = args[arg_count:]

            if kw_default_values:
                for key, val in kw_default_values.items():
                    if key not in names:
                        raise TypeError(Frame.ERR_TOO_MANY_KW_ARGS)
                    else:
                        parsed_args[key] = val

            for key, val in kwargs.items():
                if key not in names:
                    if not has_varkw:
                        raise TypeError(Frame.ERR_TOO_MANY_KW_ARGS)
                    else:
                        parsed_args[varkw_name][key] = val
                        continue
                if names.index(key) < pos_only_count:
                    if not has_varkw:
                        raise TypeError(Frame.ERR_POSONLY_PASSED_AS_KW)
                    else:
                        parsed_args[varkw_name][key] = val
                        continue
                parsed_args[key] = val

            for i, arg_val in enumerate(args):
                if has_varargs and i >= len(args) - len(parsed_args[vararg_name]):
                    break

                if names[i] in parsed_args:
                    raise TypeError(Frame.ERR_MULT_VALUES_FOR_ARG)

                parsed_args[names[i]] = arg_val

            for i in range(len(args), arg_count):
                if names[i] in kwargs:
                    continue

                shifted_i = i - arg_count + len(default_values)

                if shifted_i < 0 or shifted_i >= len(default_values):
                    raise TypeError(Frame.ERR_MISSING_POS_ARGS)

                parsed_args[names[i]] = default_values[shifted_i]

            for i in range(pos_only_count):
                if names[i] not in parsed_args:
                    raise TypeError(Frame.ERR_MISSING_POS_ARGS)

            for i in range(arg_count, arg_count + kw_only_count):
                if names[i] not in parsed_args:
                    raise TypeError(Frame.ERR_MISSING_KWONLY_ARGS)

            f_locals = dict(self.locals)
            f_locals.update(parsed_args)

            frame = Frame(code, self.builtins, self.globals, f_locals)
            return frame.run()

        self.push(f)

    def store_name_op(self, namei: str) -> None:
        """
        Operation description:
            https://docs.python.org/release/3.11.5/library/dis.html#opcode-STORE_NAME
        """
        const = self.pop()
        self.locals[namei] = const

    def store_global_op(self, namei: str) -> None:
        value = self.pop()
        self.globals[namei] = value

    def store_fast_op(self, var_num: str) -> None:
        const = self.pop()
        self.locals[var_num] = const

    def binary_op_op(self, op: int) -> None:
        right = self.pop()
        left = self.pop()
        self.push(self._BINARIES[op](left, right))

    def compare_op_op(self, op: int) -> None:
        left, right = self.popn(2)
        self.push(self._COMPARE[op](left, right))

    def unpack_sequence_op(self, count: int) -> None:
        if len(self.top()) != count:
            raise ValueError
        iterable = self.pop()
        iterator = iter(iterable)
        items = []
        while True:
            try:
                items.append(next(iterator))
            except StopIteration:
                break

        for i in items[::-1]:
            self.push(i)

    def get_iter_op(self, nothing: tp.Any) -> None:
        iterable = self.pop()
        self.push(iterable.__iter__())

    def jump_forward_op(self, to: int) -> None:
        self.counter = self.index[to] - 1

    def jump_backward_op(self, to: int) -> None:
        self.counter = self.index[to] - 1

    def for_iter_op(self, to: int) -> None:
        try:
            value = self.top().__next__()
            self.push(value)
        except StopIteration:
            self.pop()
            self.jump_forward_op(to)

    def pop_jump_forward_if_true_op(self, to: int) -> None:
        cond = self.pop()
        if cond:
            self.jump_forward_op(to)

    def pop_jump_forward_if_false_op(self, to: int) -> None:
        cond = self.pop()
        if not cond:
            self.jump_forward_op(to)

    def pop_jump_backward_if_true_op(self, to: int) -> None:
        cond = self.pop()
        if cond:
            self.jump_forward_op(to)

    def pop_jump_backward_if_false_op(self, to: int) -> None:
        cond = self.pop()
        if not cond:
            self.jump_forward_op(to)

    def jump_if_true_or_pop_op(self, to: int) -> None:
        cond = self.top()
        if cond:
            self.jump_forward_op(to)
        else:
            self.pop()

    def jump_if_false_or_pop_op(self, to: int) -> None:
        cond = self.top()
        if not cond:
            self.jump_forward_op(to)
        else:
            self.pop()

    def load_fast_op(self, var_num: str) -> None:
        self.load_name_op(var_num)

    def pop_jump_forward_if_none_op(self, to: int) -> None:
        item = self.pop()
        if item is None:
            self.jump_forward_op(to)

    def build_slice_op(self, argc: int) -> None:
        if argc == 2:
            a, b = self.popn(2)
            self.push(slice(a, b))
        elif argc == 3:
            a, b, step = self.popn(3)
            self.push(slice(a, b, step))
        else:
            raise ValueError

    def binary_subscr_op(self, nothing: tp.Any) -> None:
        key = self.pop()
        container = self.pop()
        self.push(container[key])

    def build_list_op(self, count: int) -> None:
        values = self.popn(count)
        self.push(list(values))

    def store_subscr_op(self, nothing: tp.Any) -> None:
        value, collection, key = self.popn(3)
        collection[key] = value

    def delete_subscr_op(self, nothing: tp.Any) -> None:
        collection, key = self.popn(2)
        del collection[key]

    def list_extend_op(self, i: int) -> None:
        iterable = self.pop()
        list.extend(self.data_stack[-i], iterable)

    def build_const_key_map_op(self, count: int) -> None:
        data = self.popn(count + 1)
        key_tuple = data[-1]
        item_map = dict()
        for i in range(count):
            item_map[key_tuple[i]] = data[i]
        self.push(item_map)

    def build_set_op(self, count: int) -> None:
        values = self.popn(count)
        self.push(set(values))

    def set_update_op(self, i: int) -> None:
        iterable = self.pop()
        set.update(self.data_stack[-i], iterable)

    def format_value_op(self, flags: int) -> None:
        if (flags & 4) == 1:
            format_spec = self.pop()
            obj = self.pop()
            self.push(format_spec(obj))
        else:
            obj = self.pop()
            if (flags & 3) == 1:
                self.push(str(obj))
            elif (flags & 3) == 2:
                self.push(repr(obj))
            elif (flags & 3) == 3:
                self.push(ascii(obj))

    def build_string_op(self, count: int) -> None:
        strings = self.popn(count)
        self.push("".join(strings))

    def unary_negative_op(self, nothing: tp.Any) -> None:
        self.push(-self.pop())

    def unary_invert_op(self, nothing: tp.Any) -> None:
        self.push(~self.pop())

    def unary_not_op(self, nothing: tp.Any) -> None:
        self.data_stack[-1] = not self.top()

    def is_op_op(self, invert: int) -> None:
        left, right = self.popn(2)
        if invert:
            self.push(left is not right)
        else:
            self.push(left is right)

    def load_assertion_error_op(self, nothing: tp.Any) -> None:
        self.push(AssertionError)

    # def _raise_exception(self, exception) -> None:
    #     self.last_raised_exception = exception
    #     raise exception

    def raise_varargs_op(self, argc: int) -> None:
        if argc == 0:
            if isinstance(self.last_raised_exception, BaseException):
                raise self.last_raised_exception
            else:
                raise ValueError("Invalid last_raised_exception")
        elif argc == 1:
            exception = self.pop()
            if isinstance(exception, type) and issubclass(exception, Exception):
                exception = exception()
            self.last_raised_exception = exception
            raise exception
        elif argc == 2:
            exception, cause = self.popn(2)
            if isinstance(exception, type) and issubclass(exception, Exception):
                exception = exception()
            exception.__cause__ = cause
            self.last_raised_exception = exception
            raise exception
        else:
            raise ValueError

    def nop_op(self, nothing: tp.Any) -> None:
        pass

    def list_append_op(self, i: int) -> None:
        value = self.pop()
        list.append(self.data_stack[-i], value)

    def build_map_op(self, count: int) -> None:
        data = self.popn(2 * count)
        item_map = dict()
        for i in range(0, 2 * count, 2):
            item_map[data[i]] = data[i + 1]
        self.push(item_map)

    def map_add_op(self, i: int) -> None:
        key, value = self.popn(2)
        dict.update(self.data_stack[-i], {key: value})

    def set_add_op(self, i: int) -> None:
        value = self.pop()
        set.add(self.data_stack[-i], value)

    def copy_op(self, i: int) -> None:
        self.push(self.data_stack[-i])

    def load_method_op(self, namei: str) -> None:
        value = self.pop()
        self.push_null_op(0)
        self.push(getattr(value, namei))

    def build_tuple_op(self, count: int) -> None:
        values = self.popn(count)
        self.push(values)

    def contains_op_op(self, invert: int) -> None:
        query, container = self.popn(2)
        if hasattr(container, '__contains__'):
            result = bool(container.__contains__(query))
        else:
            iterator = iter(container)

            query_found = False

            try:
                while True:
                    item = next(iterator)
                    if item == query:
                        query_found = True
                        break
            except StopIteration:
                pass

            result = query_found

        if invert:
            result = not result

        self.push(result)

    def kw_names_op(self, consti: int) -> None:
        self.kw_names = self.code.co_consts[consti]

    def load_attr_op(self, namei: str) -> None:
        obj = self.pop()
        obj.__getattribute__(namei)
        self.push(obj)

    def list_to_tuple_op(self, nothing: tp.Any) -> None:
        lst = self.pop()
        self.push(tuple(lst))

    def dict_update_op(self, i: int) -> None:
        mapping = self.pop()
        dict.update(self.data_stack[-i], mapping)

    def swap_op(self, i: int) -> None:
        item_i = self.data_stack[-i]
        self.data_stack[-i], self.data_stack[-1] = self.top(), item_i


class VirtualMachine:
    def run(self, code_obj: types.CodeType) -> None:
        """
        :param code_obj: code for interpreting
        """
        globals_context: dict[str, tp.Any] = {}
        frame = Frame(code_obj, builtins.globals()['__builtins__'], globals_context, globals_context)
        return frame.run()
