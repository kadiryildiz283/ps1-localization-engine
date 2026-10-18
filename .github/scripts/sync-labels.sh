#!/usr/bin/env bash
# .github/labels.yml içeriğini GitHub etiketlerine senkronlar.
# Kullanım: .github/scripts/sync-labels.sh [owner/repo]
set -euo pipefail

REPO="${1:-kadiryildiz283/ps1-localization-engine}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FILE="${ROOT}/.github/labels.yml"

if [[ ! -f "${FILE}" ]]; then
  echo "labels.yml bulunamadı: ${FILE}" >&2
  exit 1
fi

created=0
updated=0

while IFS='|' read -r name description color; do
  [[ -z "${name}" || "${name}" == \#* ]] && continue
  color="${color#\#}"
  if gh label list --repo "${REPO}" --limit 200 --json name --jq '.[].name' | grep -Fxq "${name}"; then
    gh label edit "${name}" --repo "${REPO}" --description "${description}" --color "${color}" >/dev/null
    updated=$((updated + 1))
  else
    gh label create "${name}" --repo "${REPO}" --description "${description}" --color "${color}" >/dev/null
    created=$((created + 1))
  fi
done < <(grep -v '^[[:space:]]*$' "${FILE}")

echo "Etiket senkronu tamam: ${created} oluşturuldu, ${updated} güncellendi."
