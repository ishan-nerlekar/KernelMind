#!/bin/bash
set -e
cd /app/repo
for c in $(git fsck --lost-found 2>/dev/null | awk '/dangling commit/{print $3}') $(git rev-list --all); do
  s=$(git show $c 2>/dev/null | grep -o 'secret\[[^]]*\]' | head -1)
  if [ -n "$s" ]; then echo "$s" > /app/secret.txt; break; fi
done
