#!/bin/bash
# Builds the five review-case bases (public GitNexus commits) with setup_review_base.sh.
B=$(cd "$(dirname "$0")" && pwd)
while read -r sha name; do
  echo "== $name $sha $(date -u +%H:%MZ)"; "$B/setup_review_base.sh" "$sha" "$name" 2>&1 | tail -4
done <<'LIST'
ff86ccf1e79cd7e4175da437ae8aeaf67b64aaa1 rv-2718
911151e2304f298a995fcc69c738ad2c6db9393a rv-2794
3a4247ec36b5ad86b1123d3bbce8183a643f7434 rv-2108
78b4077d8acc86f1b0c32e41012174d484e81f12 rv-2258
84f584449de02376a8ffc096dceac2e8f732cab5 rv-2773
LIST
