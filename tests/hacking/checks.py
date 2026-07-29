# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""
Guidelines for writing new hacking checks

 - Use only for Rally specific tests. OpenStack general tests
   should be submitted to the common 'hacking' module.
 - Pick numbers in the range N3xx. Find the current test with
   the highest allocated number and then pick the next value.
 - Keep the test method code in the source file ordered based
   on the N3xx value.
 - List the new rule in the top level HACKING.rst file
 - Add test cases for each new rule to tests/unit/test_hacking.py

 Only Rally-specific checks that have no equivalent in ``hacking`` or
 ``ruff`` live here. Style, import ordering, quotes, builtins, naming and
 the generic ``assert*`` rewrites are handled by ruff (see pyproject.toml)
 or by hacking's own H-checks.

"""

import re
import tokenize

from hacking import core


re_str_format = re.compile(r"""
%            # start of specifier
\(([^)]+)\)  # mapping key, in group 1
[#0 +\-]?    # optional conversion flag
(?:-?\d*)?   # optional minimum field width
(?:\.\d*)?   # optional precision
[hLl]?       # optional length modifier
[A-z%]       # conversion modifier
""", re.X)
re_raises = re.compile(
    r"\s:raise[^s] *.*$|\s:raises *:.*$|\s:raises *[^:]+$")
re_log_warn = re.compile(r"(.)*LOG\.(warn)\(\s*('|\"|_)")


def _parse_assert_mock_str(line):
    point = line.find(".assert_")

    if point == -1:
        point = line.find(".called_once_with(")

    if point != -1:
        end_pos = line[point:].find("(") + point
        return point, line[point + 1: end_pos], line[: point]
    else:
        return None, None, None


@core.flake8ext
def check_assert_methods_from_mock(logical_line, filename, noqa=False):
    """Ensure that ``assert_*`` methods from ``mock`` library is used correctly

    ``mock`` silently accepts any ``assert_*`` attribute access as a no-op,
    so a typo (or a method that does not exist) turns an assertion into a
    check that always passes.

    N301 - unknown ``assert_*`` method
    N304 - related to nonexistent "called_once_with"
    """
    if noqa:
        return

    correct_names = ["assert_any_call", "assert_called", "assert_called_once",
                     "assert_called_once_with", "assert_called_with",
                     "assert_has_calls", "assert_not_called"]
    ignored_files = ["./tests/unit/test_hacking.py"]

    if filename.startswith("./tests") and filename not in ignored_files:
        pos, method_name, obj_name = _parse_assert_mock_str(logical_line)

        if pos:
            if method_name not in correct_names:
                error_number = "N301"
                msg = ("%(error_number)s:'%(method)s' is not present in `mock`"
                       " library. %(custom_msg)s For more details, visit "
                       "http://www.voidspace.org.uk/python/mock/ .")

                if method_name == "called_once_with":
                    error_number = "N304"
                    custom_msg = ("Maybe, you should try to use "
                                  "'%s.assert_called_once_with()'"
                                  " instead." % obj_name)
                else:
                    custom_msg = ("Correct 'assert_*' methods: '%s'."
                                  % "', '".join(correct_names))

                yield (pos, msg % {
                    "error_number": error_number,
                    "method": method_name,
                    "custom_msg": custom_msg})


@core.flake8ext
def no_use_conf_debug_check(logical_line, noqa=False):
    """Check for "cfg.CONF.debug"

    Rally has two DEBUG level:
     - Full DEBUG, which include all debug-messages from all OpenStack services
     - Rally DEBUG, which include only Rally debug-messages
    so we should use custom check to know debug-mode, instead of CONF.debug

    N312
    """
    if noqa:
        return

    point = logical_line.find("CONF.debug")
    if point != -1:
        yield (point, "N312 Don't use `CONF.debug`. "
                      "Function `rally.common.logging.is_debug` "
                      "should be used instead.")


@core.flake8ext
def check_log_warn(logical_line):
    """Check for LOG.warn, which is deprecated

    N313
    """
    if re_log_warn.search(logical_line):
        yield 0, "N313 LOG.warn is deprecated, please use LOG.warning"


@core.flake8ext
def check_opts_import_path(logical_line, noqa=False):
    """Ensure that we load opts from correct paths only

    N342
    """
    if noqa:
        return
    forbidden_methods = [".register_opts("]

    for forbidden_method in forbidden_methods:
        if logical_line.find(forbidden_method) != -1:
            yield (0, "N342 All options should be loaded from correct "
                      "paths only: rally_openstack/common/cfg")


@core.flake8ext
def check_dict_formatting_in_string(logical_line, tokens, noqa=False):
    """Check that strings do not use dict-formatting with a single replacement

    N352
    """
    if noqa:
        return

    current_string = ""
    in_string = False
    for token_type, text, start, end, line in tokens:
        if token_type == tokenize.STRING:
            if not in_string:
                current_string = ""
                in_string = True
            current_string += text.strip('"')
        elif token_type == tokenize.OP:
            if not current_string:
                continue
            # NOTE(stpierre): The string formatting operator % has
            # lower precedence than +, so we assume that the logical
            # string has concluded whenever we hit an operator of any
            # sort. (Most operators don't work for strings anyway.)
            # Some string operators do have higher precedence than %,
            # though, so you can technically trick this check by doing
            # things like:
            #
            #     "%(foo)s" * 1 % {"foo": 1}
            #     "%(foo)s"[:] % {"foo": 1}
            #
            # It also will produce false positives if you use explicit
            # parenthesized addition for two strings instead of
            # concatenation by juxtaposition, e.g.:
            #
            #     ("%(foo)s" + "%(bar)s") % vals
            #
            # But if you do any of those things, then you deserve all
            # of the horrible things that happen to you, and probably
            # many more.
            in_string = False
            if text == "%":
                format_keys = set()
                for match in re_str_format.finditer(current_string):
                    format_keys.add(match.group(1))
                if len(format_keys) == 1:
                    yield (0,
                           "N352 Do not use mapping key string formatting "
                           "with a single key")
            if text != ")":
                # NOTE(stpierre): You can have a parenthesized string
                # followed by %, so a closing paren doesn't obviate
                # the possibility for a substitution operator like
                # every other operator does.
                current_string = ""
        elif token_type in (tokenize.NL, tokenize.COMMENT):
            continue
        else:
            in_string = False
            if token_type == tokenize.NEWLINE:
                current_string = ""


@core.flake8ext
def check_raises(logical_line, filename, noqa=False):
    """Check raises usage

    N354
    """
    if noqa:
        return

    ignored_files = ["./tests/unit/test_hacking.py",
                     "./tests/hacking/checks.py"]
    if filename not in ignored_files:
        if re_raises.search(logical_line):
            yield (0, "N354 ':Please use ':raises Exception: conditions' "
                      "in docstrings.")
