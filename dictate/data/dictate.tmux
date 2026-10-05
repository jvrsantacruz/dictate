#!/usr/bin/env bash
# dictate.tmux - the tmux plugin: #{dictate_status} in status-left or
# status-right becomes dictate's status segment.
#
# TPM runs it from the repository root; without TPM:
#   run-shell /usr/share/dictate/dictate.tmux
# The segment goes only where the placeholder is written: nothing is added.

set -euo pipefail

segment='#(dictate-status)'
# Without dictate the placeholder goes away rather than drawing an error.
command -v dictate-status >/dev/null || segment=''

for option in status-left status-right; do
  value=$(tmux show-option -gqv "$option")
  [[ $value == *'#{dictate_status}'* ]] || continue
  tmux set-option -g "$option" "${value//'#{dictate_status}'/"$segment"}"
done
