# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Module to build a image from a specific commit, branch or pull request

This module is allows each of the OSS Fuzz projects fuzzers to be built
from a specific point in time. This feature can be used for implementations
like continuious integration fuzzing and bisection to find errors
"""
import os
import re
import subprocess

import helper


class DockerExecutionError(Exception):
  """An error that occurs when running a docker command."""


def build_fuzzers_from_commit(project_name,
                              commit,
                              build_repo_manager,
                              engine='libfuzzer',
                              sanitizer='address',
                              architecture='x86_64'):
  """Builds a OSS-Fuzz fuzzer at a  specific commit SHA.

  Args:
    project_name: The OSS-Fuzz project name.
    commit: The commit SHA to build the fuzzers at.
    build_repo_manager: The OSS-Fuzz project's repo manager to be built at.
    engine: The fuzzing engine to be used.
    sanitizer: The fuzzing sanitizer to be used.
    architecture: The system architiecture to be used for fuzzing.

  Returns:
    0 on successful build 1 on failure
  """
  build_repo_manager.checkout_commit(commit)
  return helper.build_fuzzers_impl(project_name=project_name,
                                   clean=True,
                                   engine=engine,
                                   sanitizer=sanitizer,
                                   architecture=architecture,
                                   env_to_add=None,
                                   source_path=build_repo_manager.repo_dir,
                                   mount_location=os.path.join(
                                       '/src', build_repo_manager.repo_name))


def detect_main_repo(project_name, repo_name=None, commit=None, src_dir='/src'):
  """Checks a docker image for the main repo of an OSS-Fuzz project.

  Note: The default is to use the repo name to detect the main repo.

  Args:
    project_name: The name of the oss-fuzz project.
    repo_name: The name of the main repo in an OSS-Fuzz project.
    commit: A commit SHA that is associated with the main repo.
    src_dir: The location of the projects source on the docker image.

  Returns:
    The repo's origin, the repo's name.
  """
  # TODO: Add infra for non hardcoded '/src'
  if not repo_name and not commit:
    print('Error: can not detect main repo without a repo_name or a commit.')
    return None, None
  if repo_name and commit:
    print(
        'Both repo name and commit specific. Using repo name for detection.'
    )

  # Base builder needs to be built when repo_name is specific for caching
  # problems on github actions
  helper.build_image_impl(project_name)
  docker_image_name = 'gcr.io/oss-fuzz/' + project_name
  command_to_run = [
      'docker', 'run', '--rm', '-t', docker_image_name, 'python3',
      os.path.join(src_dir, 'detect_repo.py'), '--src_dir', src_dir
  ]
  if repo_name:
    command_to_run.extend(['--repo_name', repo_name])
  else:
    command_to_run.extend(['--example_commit', commit])
  out, _ = execute(command_to_run)
  match = re.search(r'\bDetected repo: ([^ ]+) ([^ ]+)', out.rstrip())
  if match and match.group(1) and match.group(2):
    return match.group(1), match.group(2)
  return None, None


def execute(command, location=None, check_result=False):
  """ Runs a shell command in the specified directory location.

  Args:
    command: The command as a list to be run.
    location: The directory the command is run in.
    check_result: Should an exception be thrown on failed command.

  Returns:
    The stdout of the command, the error code.

  Raises:
    RuntimeError: running a command resulted in an error.
  """

  if not location:
    location = os.getcwd()
  process = subprocess.Popen(command, stdout=subprocess.PIPE, cwd=location)
  out, err = process.communicate()
  if check_result and (process.returncode or err):
    raise RuntimeError('Error: %s\n Command: %s\n Return code: %s\n Out: %s' %
                       (err, command, process.returncode, out))
  if out is not None:
    out = out.decode('ascii')
  return out, process.returncode
