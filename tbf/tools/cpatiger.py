from tbf.input_generation import BaseInputGenerator
from tbf.testcase_validation import TestValidator
import tbf.utils as utils
import os
import json

module_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.join(module_dir, 'cpatiger')
binary_dir = os.path.join(base_dir, 'scripts')
binary = os.path.join(binary_dir, 'cpa.sh')
tests_dir = os.path.join(utils.tmp, 'output')
input_var_prefix = '__inputVar'
input_method_prefix = '_inp_'
name = 'cpatiger'


class InputGenerator(BaseInputGenerator):

    def __init__(self,
                 timelimit=None,
                 log_verbose=False,
                 additional_cli_options='',
                 machine_model=utils.MACHINE_MODEL_32):
        super().__init__(machine_model, log_verbose, additional_cli_options)

        self._run_env = utils.get_env_with_path_added(binary_dir)
        # Make sure that timelimit is never None
        self.timelimit = timelimit if timelimit else 0

        self._current_input_vars = set()

    def get_run_env(self):
        return self._run_env

    def get_name(self):
        return name

    def prepare(self, filecontent, nondet_methods_used):
        content = filecontent
        content += '\n'
        for method in nondet_methods_used:  # append method definition at end of file content
            nondet_method_definition = self._get_nondet_method(method)
            content += nondet_method_definition
        return content

    def _get_nondet_method(self, method_information):
        method_name = method_information['name']
        m_type = method_information['type']
        param_types = method_information['params']
        return self._create_nondet_method(method_name, m_type, param_types)

    def _create_nondet_method(self, method_name, method_type, param_types):
        input_method_name = input_method_prefix + method_name
        input_method_declaration = 'extern {0} {1}();'.format(method_type, input_method_name)

        input_var = input_var_prefix + method_name
        self._current_input_vars.add(input_var)

        method_head = utils.get_method_head(method_name, 'int', param_types)
        method_body = ['{']
        if method_type != 'void':
            method_body += [
                '{0} {1} = {2}();'.format(method_type, input_var, input_method_name),
                'return {0};'.format(input_var)
            ]
        method_body = '\n    '.join(method_body)
        method_body += '\n}\n'

        return input_method_declaration + "\n" + method_head + method_body

    def create_input_generation_cmds(self, filename, cli_options):
        import shutil
        config_copy_dir = utils.get_file_path('config', temp_dir=True)
        if not os.path.exists(config_copy_dir):
            copy_dir = os.path.join(base_dir, 'config')
            shutil.copytree(copy_dir, config_copy_dir)

        input_var_list = ','.join(self._current_input_vars)

        input_generation_cmd = [binary]
        if self.timelimit > 0:
            input_generation_cmd += ['-timelimit', str(self.timelimit)]
        if not cli_options or all('-tiger-variants' not in c for c in cli_options):
            input_generation_cmd += ['-tiger-variants-noOmega']
        input_generation_cmd += ['-outputpath', tests_dir, '-spec',
                                 utils.spec_file,
                                 '-setprop', 'tiger.inputInterface=' + input_var_list
                                 ]
        if cli_options:
            input_generation_cmd += cli_options
        if self.machine_model.is_64:
            input_generation_cmd.append("-64")
        else:
            assert self.machine_model.is_32, "Unknown machine model: %s" % self.machine_model
            input_generation_cmd.append("-32")
        input_generation_cmd.append(filename)

        return [input_generation_cmd]

    def get_test_cases(self, exclude=(), directory=tests_dir):
        tests_file = os.path.join(directory, 'testsuite.json')
        if os.path.exists(tests_file):
            with open(tests_file, 'r') as inp:
                test_suite = json.loads(inp.read())

            test_cases = test_suite['testCases']
            tests = [t['inputs'] for t in test_cases]
            tests = [t for i, t in enumerate(tests) if str(i) not in exclude]
            tcs = list()
            for i, t in enumerate(tests):
                tcs.append(utils.TestCase(str(i), tests_file, t))
            return tcs
        else:
            return []


class CpaTigerTestValidator(TestValidator):

    def _get_test_vector(self, test, nondet_methods):
        assert type(test.content) is dict, "Type of test: %s" % type(test.content)
        test_vector = utils.TestVector(test.name, test.origin)
        test_pairs = test.content.items()
        for variable, value in test_pairs:
            test_vector.add(value)
        return test_vector

    def get_name(self):
        return name
