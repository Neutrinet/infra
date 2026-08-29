#!/bin/bash

if [[ -n ${CI_COMMIT_SHA} ]]; then
  FILES="playbooks roles"
else
  FILES="$@"
fi

ansible-lint -c .ansible-lint $FILES
