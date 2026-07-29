#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import inspect
import io
import tokenize

from tests.hacking import checks
from tests.unit import test


class HackingTestCase(test.TestCase):

    def _assert_good_samples(self, checker, samples, module_file="f"):
        spec = inspect.getfullargspec(checker)
        base_args = {}
        if "filename" in spec.args:
            base_args["filename"] = module_file
        for s in samples:
            args = {"logical_line": s, **base_args}
            self.assertEqual([], list(checker(*args)), s)

    def _assert_bad_samples(self, checker, samples, module_file="f"):
        spec = inspect.getfullargspec(checker)
        base_args = {}
        if "filename" in spec.args:
            base_args["filename"] = module_file

        for s in samples:
            args = {"logical_line": s, **base_args}
            self.assertEqual(1, len(list(checker(**args))), s)

    def test__parse_assert_mock_str(self):
        pos, method, obj = checks._parse_assert_mock_str(
            "mock_clients.fake().quotas.delete.assert_called_once()")
        self.assertEqual("assert_called_once", method)
        self.assertEqual("mock_clients.fake().quotas.delete", obj)

    def test__parse_assert_mock_str_no_assert(self):
        pos, method, obj = checks._parse_assert_mock_str(
            "mock_clients.fake().quotas.delete.")
        self.assertIsNone(pos)
        self.assertIsNone(method)
        self.assertIsNone(obj)

    def test_correct_usage_of_assert_from_mock(self):
        correct_method_names = ["assert_any_call", "assert_called",
                                "assert_called_once",
                                "assert_called_once_with",
                                "assert_called_with", "assert_has_calls",
                                "assert_not_called"]
        for name in correct_method_names:
            line = "some_mock.%s(asd)" % name
            self.assertEqual(0, len(
                list(checks.check_assert_methods_from_mock(
                    line, line, "./tests/fake/test"))))

    def test_wrong_usage_of_broad_assert_from_mock(self):
        fake_method = "rtfm.assert_something()"

        actual_number, actual_msg = next(checks.check_assert_methods_from_mock(
            fake_method, "./tests/fake/test"))
        self.assertEqual(4, actual_number)
        self.assertTrue(actual_msg.startswith("N301"))

    def test_wrong_usage_of_called_once_with_from_mock(self):
        fake_method = "rtfm.called_once_with()"

        actual_number, actual_msg = next(checks.check_assert_methods_from_mock(
            fake_method, "./tests/fake/test", False))
        self.assertEqual(4, actual_number)
        self.assertTrue(actual_msg.startswith("N304"))

    def test_no_use_conf_debug_check(self):
        bad_samples = [
            "if CONF.debug:",
            "if cfg.CONF.debug"
        ]
        self._assert_bad_samples(checks.no_use_conf_debug_check, bad_samples)

        good_samples = ["if logging.is_debug()"]
        self._assert_good_samples(checks.no_use_conf_debug_check, good_samples)

    def test_check_dict_formatting_in_string(self):
        bad = [
            '"%(a)s" % d',
            '"Split across "\n"multiple lines: %(a)f" % d',
            '"%(a)X split across "\n"multiple lines" % d',
            '"%(a)-5.2f: Split %("\n"a)#Lu stupidly" % d',
            '"Comment between "  # wtf\n"split lines: %(a) -6.2f" % d',
            '"Two strings" + " added: %(a)-6.2f" % d',
            '"half legit (%(a)s %(b)s)" % d + " half bogus: %(a)s" % d',
            '("Parenthesized: %(a)s") % d',
            '("Parenthesized "\n"concatenation: %(a)s") % d',
            '("Parenthesized " + "addition: %(a)s") % d',
            '"Complete %s" % ("foolisness: %(a)s%(a)s" % d)',
            '"Modulus %(a)s" % {"a": (5 % 3)}'
        ]
        for sample in bad:
            sample = "print(%s)" % sample
            tokens = tokenize.generate_tokens(
                io.StringIO(sample).readline)
            self.assertEqual(
                1,
                len(list(checks.check_dict_formatting_in_string(sample,
                                                                tokens))))

        sample = 'print("%(a)05.2lF" % d + " added: %(a)s" % d)'
        tokens = tokenize.generate_tokens(io.StringIO(sample).readline)
        self.assertEqual(
            2,
            len(list(checks.check_dict_formatting_in_string(sample, tokens))))

        good = [
            '"This one is okay: %(a)s %(b)s" % d',
            '"So is %(a)s"\n"this one: %(b)s" % d'
        ]
        for sample in good:
            sample = "print(%s)" % sample
            tokens = tokenize.generate_tokens(
                io.StringIO(sample).readline)
            self.assertEqual(
                [],
                list(checks.check_dict_formatting_in_string(sample, tokens)))

    def test_check_raises(self):
        self._assert_bad_samples(
            checks.check_raises,
            ["text = :raises: Exception if conditions"])

        self._assert_good_samples(
            checks.check_raises,
            ["text = :raises Exception: if conditions"]
        )

    def test_check_log_warn(self):
        bad_samples = ["LOG.warn('foo')", "LOG.warn(_('bar'))"]
        self._assert_bad_samples(checks.check_log_warn, bad_samples)
        good_samples = ["LOG.warning('foo')", "LOG.warning(_('bar'))"]
        self._assert_good_samples(checks.check_log_warn, good_samples)
