#!/usr/bin/env python

# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

#
# This script will install the promptflow into a directory and create an executable
# at a specified file path that is the entry point into the promptflow.
#
# The latest versions of all promptflow command packages will be installed.
#

import os
import sys
import platform
import stat
import tempfile
import shutil
import subprocess
import hashlib


PF_DISPATCH_TEMPLATE = """#!/usr/bin/env bash
export PF_INSTALLER=Script
{install_dir}/bin/python -m promptflow._cli._pf.entry "$@"
"""

PFAZURE_DISPATCH_TEMPLATE = """#!/usr/bin/env bash
{install_dir}/bin/python -m promptflow._cli._pf_azure.entry "$@"
"""

PFS_DISPATCH_TEMPLATE = """#!/usr/bin/env bash
{install_dir}/bin/python -m promptflow._sdk._service.entry "$@"
"""

DEFAULT_INSTALL_DIR = os.path.expanduser(os.path.join('~', 'lib', 'promptflow'))
DEFAULT_EXEC_DIR = os.path.expanduser(os.path.join('~', 'bin'))
PF_EXECUTABLE_NAME = 'pf'
PFAZURE_EXECUTABLE_NAME = 'pfazure'
PFS_EXECUTABLE_NAME = 'pfs'


USER_BASH_RC = os.path.expanduser(os.path.join('~', '.bashrc'))
USER_BASH_PROFILE = os.path.expanduser(os.path.join('~', '.bash_profile'))


class CLIInstallError(Exception):
    pass


def print_status(msg=''):
    print('-- '+msg)


def prompt_input(msg):
    return input('\n===> '+msg)


def prompt_input_with_default(msg, default):
    if default:
        return prompt_input("{} (leave blank to use '{}'): ".format(msg, default)) or default
    else:
        return prompt_input('{}: '.format(msg))


def prompt_y_n(msg, default=None):
    if default not in [None, 'y', 'n']:
        raise ValueError("Valid values for default are 'y', 'n' or None")
    y = 'Y' if default == 'y' else 'y'
    n = 'N' if default == 'n' else 'n'
    while True:
        ans = prompt_input('{} ({}/{}): '.format(msg, y, n))
        if ans.lower() == n.lower():
            return False
        if ans.lower() == y.lower():
            return True
        if default and not ans:
            return default == y.lower()


def exec_command(command_list, cwd=None, env=None):
    print_status('Executing: '+str(command_list))
    subprocess.check_call(command_list, cwd=cwd, env=env)


def create_tmp_dir():
    tmp_dir = tempfile.mkdtemp()
    return tmp_dir


def create_dir(dir):
    if not os.path.isdir(dir):
        print_status("Creating directory '{}'.".format(dir))
        os.makedirs(dir)


def is_valid_sha256sum(a_file, expected_sum):
    sha256 = hashlib.sha256()
    with open(a_file, 'rb') as f:
        sha256.update(f.read())
    computed_hash = sha256.hexdigest()
    return expected_sum == computed_hash


def create_virtualenv(install_dir):
    cmd = [sys.executable, '-m', 'venv', install_dir]
    exec_command(cmd)


def install_cli(install_dir, tmp_dir):
    path_to_pip = os.path.join(install_dir, 'bin', 'pip')
    cmd = [path_to_pip, 'install', '--cache-dir', tmp_dir, 'promptflow[azure,executable,azureml-serving]',
           '--upgrade']
    exec_command(cmd)
    cmd = [path_to_pip, 'install', '--cache-dir', tmp_dir, 'promptflow-tools', '--upgrade']
    exec_command(cmd)
    cmd = [path_to_pip, 'install', '--cache-dir', tmp_dir, 'keyrings.alt', '--upgrade']
    exec_command(cmd)


def create_executable(exec_dir, install_dir):
    create_dir(exec_dir)
    exec_filepaths = []
    for filename, template in [(PF_EXECUTABLE_NAME, PF_DISPATCH_TEMPLATE),
                               (PFAZURE_EXECUTABLE_NAME, PFAZURE_DISPATCH_TEMPLATE),
                               (PFS_EXECUTABLE_NAME, PFS_DISPATCH_TEMPLATE)]:
        exec_filepath = os.path.join(exec_dir, filename)
        with open(exec_filepath, 'w') as exec_file:
            exec_file.write(template.format(install_dir=install_dir))
        cur_stat = os.stat(exec_filepath)
        os.chmod(exec_filepath, cur_stat.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print_status("The executable is available at '{}'.".format(exec_filepath))
        exec_filepaths.append(exec_filepath)
    return exec_filepaths


def get_install_dir():
    install_dir = None
    while not install_dir:
        prompt_message = 'In what directory would you like to place the install?'
        install_dir = prompt_input_with_default(prompt_message, DEFAULT_INSTALL_DIR)
        install_dir = os.path.realpath(os.path.expanduser(install_dir))
        if ' ' in install_dir:
            print_status("The install directory '{}' cannot contain spaces.".format(install_dir))
            install_dir = None
        else:
            create_dir(install_dir)
            if os.listdir(install_dir):
                print_status("'{}' is not empty and may contain a previous installation.".format(install_dir))
                ans_yes = prompt_y_n('Remove this directory?', 'n')
                if ans_yes:
                    shutil.rmtree(install_dir)
                    print_status("Deleted '{}'.".format(install_dir))
                    create_dir(install_dir)
                else:
                    # User opted to not delete the directory so ask for install directory again
                    install_dir = None
    print_status("We will install at '{}'.".format(install_dir))
    return install_dir


def get_exec_dir():
    exec_dir = None
    while not exec_dir:
        prompt_message = (f"In what directory would you like to place the "
                          f"'{PFS_EXECUTABLE_NAME}/{PFS_EXECUTABLE_NAME}/{PFAZURE_EXECUTABLE_NAME}' executable?")
        exec_dir = prompt_input_with_default(prompt_message, DEFAULT_EXEC_DIR)
        exec_dir = os.path.realpath(os.path.expanduser(exec_dir))
        if ' ' in exec_dir:
            print_status("The executable directory '{}' cannot contain spaces.".format(exec_dir))
            exec_dir = None
    create_dir(exec_dir)
    print_status("The executable will be in '{}'.".format(exec_dir))
    return exec_dir


def _backup_rc(rc_file):
    try:
        shutil.copyfile(rc_file, rc_file+'.backup')
        print_status("Backed up '{}' to '{}'".format(rc_file, rc_file+'.backup'))
    except (OSError, IOError):
        pass


def _get_default_rc_file():
    bashrc_exists = os.path.isfile(USER_BASH_RC)
    bash_profile_exists = os.path.isfile(USER_BASH_PROFILE)
    if not bashrc_exists and bash_profile_exists:
        return USER_BASH_PROFILE
    if bashrc_exists and bash_profile_exists and platform.system().lower() == 'darwin':
        return USER_BASH_PROFILE
    return USER_BASH_RC if bashrc_exists else None


def _default_rc_file_creation_step():
    rcfile = USER_BASH_PROFILE if platform.system().lower() == 'darwin' else USER_BASH_RC
    ans_yes = prompt_y_n('Could not automatically find a suitable file to use. Create {} now?'.format(rcfile),
                         default='y')
    if ans_yes:
        open(rcfile, 'a').close()
        return rcfile
    return None


def _find_line_in_file(file_path, search_pattern):
    try:
        with open(file_path, 'r', encoding="utf-8") as search_file:
            for line in search_file:
                if search_pattern in line:
                    return True
    except (OSError, IOError):
        pass
    return False


def _modify_rc(rc_file_path, line_to_add):
    if not _find_line_in_file(rc_file_path, line_to_add):
        with open(rc_file_path, 'a', encoding="utf-8") as rc_file:
            rc_file.write('\n'+line_to_add+'\n')


def get_rc_file_path():
    rc_file = None
    default_rc_file = _get_default_rc_file()
    if not default_rc_file:
        rc_file = _default_rc_file_creation_step()
    rc_file = rc_file or prompt_input_with_default('Enter a path to an rc file to update', default_rc_file)
    if rc_file:
        rc_file_path = os.path.realpath(os.path.expanduser(rc_file))
        if os.path.isfile(rc_file_path):
            return rc_file_path
        print_status("The file '{}' could not be found.".format(rc_file_path))
    return None


def warn_other_azs_on_path(exec_dir, exec_filepath):
    env_path = os.environ.get('PATH')
    conflicting_paths = []
    if env_path:
        for p in env_path.split(':'):
            for file in [PF_EXECUTABLE_NAME, PFAZURE_EXECUTABLE_NAME, PFS_EXECUTABLE_NAME]:
                p_to_pf = os.path.join(p, file)
                if p != exec_dir and os.path.isfile(p_to_pf):
                    conflicting_paths.append(p_to_pf)
    if conflicting_paths:
        print_status()
        print_status(f"** WARNING: Other '{PFS_EXECUTABLE_NAME}/{PFS_EXECUTABLE_NAME}/{PFAZURE_EXECUTABLE_NAME}' "
                     f"executables are on your $PATH. **")
        print_status("Conflicting paths: {}".format(', '.join(conflicting_paths)))
        print_status("You can run this installation of the promptflow with '{}'.".format(exec_filepath))


def handle_path_and_tab_completion(exec_filepath, exec_dir):
    ans_yes = prompt_y_n('Modify profile to update your $PATH now?', 'y')
    if ans_yes:
        rc_file_path = get_rc_file_path()
        if not rc_file_path:
            raise CLIInstallError('No suitable profile file found.')
        _backup_rc(rc_file_path)
        line_to_add = "export PATH=$PATH:{}".format(exec_dir)
        _modify_rc(rc_file_path, line_to_add)
        warn_other_azs_on_path(exec_dir, exec_filepath)
        print_status()
        print_status('** Run `exec -l $SHELL` to restart your shell. **')
        print_status()
    else:
        print_status("You can run the promptflow with '{}'.".format(exec_filepath))


def verify_python_version():
    print_status('Verifying Python version.')
    v = sys.version_info
    if v < (3, 8):
        raise CLIInstallError('The promptflow does not support Python versions less than 3.8.')
    if 'conda' in sys.version:
        raise CLIInstallError("This script does not support the Python Anaconda environment. "
                              "Create an Anaconda virtual environment and install with 'pip'")
    print_status('Python version {}.{}.{} okay.'.format(v.major, v.minor, v.micro))


def _native_dependencies_for_dist(verify_cmd_args, install_cmd_args, dep_list):
    try:
        print_status("Executing: '{} {}'".format(' '.join(verify_cmd_args), ' '.join(dep_list)))
        subprocess.check_output(verify_cmd_args + dep_list, stderr=subprocess.STDOUT)
        print_status('Native dependencies okay.')
    except subprocess.CalledProcessError:
        err_msg = 'One or more of the following native dependencies are not currently installed and may be required.\n'
        err_msg += '"{}"'.format(' '.join(install_cmd_args + dep_list))
        print_status(err_msg)
        ans_yes = prompt_y_n('Missing native dependencies. Attempt to continue anyway?', 'n')
        if not ans_yes:
            raise CLIInstallError('Please install the native dependencies and try again.')


def _get_linux_distro():
    if platform.system() != 'Linux':
        return None, None

    try:
        with open('/etc/os-release') as lines:
            tokens = [line.strip() for line in lines]
    except Exception:
        return None, None

    release_info = {}
    for token in tokens:
        if '=' in token:
            k, v = token.split('=', 1)
            release_info[k.lower()] = v.strip('"')

    return release_info.get('name', None), release_info.get('version_id', None)


def verify_install_dir_exec_path_conflict(install_dir, exec_dir):
    for exec_name in [PF_EXECUTABLE_NAME, PFAZURE_EXECUTABLE_NAME, PFS_EXECUTABLE_NAME]:
        exec_path = os.path.join(exec_dir, exec_name)
        if install_dir == exec_path:
            raise CLIInstallError("The executable file '{}' would clash with the install directory of '{}'. Choose "
                                  "either a different install directory or directory to place the "
                                  "executable.".format(exec_path, install_dir))


def main():
    verify_python_version()
    tmp_dir = create_tmp_dir()
    install_dir = get_install_dir()
    exec_dir = get_exec_dir()
    verify_install_dir_exec_path_conflict(install_dir, exec_dir)
    create_virtualenv(install_dir)
    install_cli(install_dir, tmp_dir)
    exec_filepath = create_executable(exec_dir, install_dir)
    try:
        handle_path_and_tab_completion(exec_filepath, exec_dir)
    except Exception as e:
        print_status("Unable to set up PATH. ERROR: {}".format(str(e)))
    shutil.rmtree(tmp_dir)
    print_status("Installation successful.")
    print_status("Run the CLI with {} --help".format(exec_filepath))


if __name__ == '__main__':
    try:
        main()
    except CLIInstallError as cie:
        print('ERROR: '+str(cie), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print('\n\nExiting...')
        sys.exit(1)

# SIG # Begin signature block
# Z1F07ShfIJ7kejST2NXwW1QcFPEya4xaO2xZz6vLT847zaMzbc/PaEa1RKFlD881
# 4J+i6Au2wtbHzOXDisyH6WeLQ3gh0X2gxFRa4EzW7Nzjcvwm4+WogiTcnPVVxlk3
# qafM/oyVqs3695K7W5XttOiq2guv/yedsf/TW2BKSEKruFQh9IwDfIiBoi9Zv3wa
# iuzQulRR8KyrCtjEPDV0t4WnZVB/edQea6xJZeTlMG+uLR/miBTbPhUb/VZkVjBf
# qHBv623oLXICzoTNuaPTln9OWvL2NZpisGYvNzebKO7/Ho6AOWZNs5XOVnjs0Ax2
# aeXvlwBzIQyfyxd25487/Q==
# SIG # End signature block
