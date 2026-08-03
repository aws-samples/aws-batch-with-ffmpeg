#!/usr/bin/env bash
#
# check-sources.sh - verify every third-party source URL used by the ffmpeg
# Dockerfiles is reachable AND serves the archive type the Dockerfile expects.
#
# Why: the Dockerfiles download source tarballs with curl and pipe/extract them
# with tar. When an upstream mirror returns an HTTP error page, a curl without
# --fail happily writes the HTML body into the ".tar.gz" and the build only dies
# minutes later inside tar with an unrelated-looking message. This script tests
# the URLs the same way the Dockerfiles do (curl -fsSL) and asserts the payload
# is a real archive (via file(1) magic), so a dead mirror is caught in seconds.
#
# Usage:
#   ./check-sources.sh [Dockerfile ...]
#
# With no argument, all Dockerfiles of the versions built by the CI are checked
# (the ones next to this script).
#
# Exit code: 0 if every URL is healthy, 1 if at least one is broken.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

CURL_OPTS=(--fail --silent --show-error --location --retry 2 --retry-delay 2 --max-time 600)

TMPDIR_RUN="$(mktemp -d)"
trap 'rm -rf "${TMPDIR_RUN}"' EXIT

declare -A SEEN_URL_STATUS=()
declare -A SEEN_URL_DETAIL=()
TOTAL=0
FAILURES=0

log()  { printf '%s\n' "$*"; }
pass() { printf '  [ OK ] %-34s %s\n' "$1" "$2"; }
fail() { printf '  [FAIL] %-34s %s\n' "$1" "$2"; }

# Collect NAME=value assignments (ENV/ARG blocks) of a Dockerfile into VARS.
load_vars() {
    local dockerfile="$1" assignment name value
    while IFS= read -r assignment; do
        assignment="${assignment#"${assignment%%[![:space:]]*}"}"
        assignment="${assignment#ENV }"
        assignment="${assignment#ARG }"
        assignment="${assignment#"${assignment%%[![:space:]]*}"}"
        name="${assignment%%=*}"
        value="${assignment#*=}"
        [[ -z "${name}" || -z "${value}" ]] && continue
        VARS["${name}"]="${value}"
    done < <(grep -v '^[[:space:]]*#' "${dockerfile}" \
        | grep -oE '^[[:space:]]*(ENV[[:space:]]+|ARG[[:space:]]+)?[A-Z][A-Z0-9_]*=[^[:space:]\\]+' || true)
}

# Substitute ${VAR} references using the values loaded from the Dockerfile.
resolve_vars() {
    local s="$1" name
    while [[ "${s}" =~ \$\{([A-Za-z_][A-Za-z0-9_]*)\} ]]; do
        name="${BASH_REMATCH[1]}"
        if [[ -n "${VARS[${name}]+set}" ]]; then
            s="${s//\$\{${name}\}/${VARS[${name}]}}"
        else
            s="${s//\$\{${name}\}/UNRESOLVED-${name}}"
        fi
    done
    printf '%s' "${s}"
}

# Guess the archive family the Dockerfile expects, from the URL itself.
expected_type() {
    local url="$1"
    case "${url}" in
        *tar.xz*)            printf 'XZ' ;;
        *tar.bz2*)           printf 'bzip2' ;;
        *tar.gz*|*.tgz*)     printf 'gzip' ;;
        *.zip*)              printf 'Zip' ;;
        *)                   printf 'ANY' ;;
    esac
}

check_archive() {
    local url="$1" label="$2" expected out curl_rc detected size
    TOTAL=$((TOTAL + 1))

    if [[ "${url}" == *UNRESOLVED-* ]]; then
        fail "unresolved-variable" "${label} ${url}"
        FAILURES=$((FAILURES + 1))
        return
    fi

    if [[ -n "${SEEN_URL_STATUS[${url}]+set}" ]]; then
        if [[ "${SEEN_URL_STATUS[${url}]}" == "ok" ]]; then
            pass "${SEEN_URL_DETAIL[${url}]} (cached)" "${label} ${url}"
        else
            fail "${SEEN_URL_DETAIL[${url}]} (cached)" "${label} ${url}"
            FAILURES=$((FAILURES + 1))
        fi
        return
    fi

    expected="$(expected_type "${url}")"
    out="${TMPDIR_RUN}/payload"
    rm -f "${out}"

    curl_rc=0
    curl "${CURL_OPTS[@]}" -o "${out}" "${url}" 2>"${TMPDIR_RUN}/curl.err" || curl_rc=$?

    if [[ ${curl_rc} -ne 0 ]]; then
        SEEN_URL_STATUS["${url}"]="ko"
        SEEN_URL_DETAIL["${url}"]="curl exit ${curl_rc}"
        fail "curl exit ${curl_rc}" "${label} ${url}"
        sed 's/^/         /' "${TMPDIR_RUN}/curl.err"
        FAILURES=$((FAILURES + 1))
        return
    fi

    detected="$(file -b "${out}")"
    size="$(stat -c '%s' "${out}")"

    if [[ "${expected}" != "ANY" && "${detected}" != *"${expected}"* ]]; then
        SEEN_URL_STATUS["${url}"]="ko"
        SEEN_URL_DETAIL["${url}"]="expected ${expected}, got ${detected}"
        fail "expected ${expected}, got ${detected:0:40}" "${label} ${url}"
        FAILURES=$((FAILURES + 1))
        return
    fi

    SEEN_URL_STATUS["${url}"]="ok"
    SEEN_URL_DETAIL["${url}"]="${expected} ${size}B"
    pass "${expected} ${size}B" "${label} ${url}"
}

check_git() {
    local url="$1" ref="$2" label="$3" rc=0
    TOTAL=$((TOTAL + 1))

    if [[ "${url}" == *UNRESOLVED-* || "${ref}" == *UNRESOLVED-* ]]; then
        fail "unresolved-variable" "${label} ${url} ${ref}"
        FAILURES=$((FAILURES + 1))
        return
    fi

    if [[ -n "${ref}" ]]; then
        GIT_TERMINAL_PROMPT=0 git ls-remote --exit-code "${url}" "${ref}" \
            >"${TMPDIR_RUN}/git.out" 2>"${TMPDIR_RUN}/git.err" || rc=$?
    else
        GIT_TERMINAL_PROMPT=0 git ls-remote --exit-code "${url}" \
            >"${TMPDIR_RUN}/git.out" 2>"${TMPDIR_RUN}/git.err" || rc=$?
    fi

    if [[ ${rc} -ne 0 ]]; then
        fail "git ls-remote exit ${rc}" "${label} ${url} ${ref}"
        sed 's/^/         /' "${TMPDIR_RUN}/git.err"
        FAILURES=$((FAILURES + 1))
        return
    fi

    pass "git ref $(head -n 1 "${TMPDIR_RUN}/git.out" | cut -c1-12)" "${label} ${url} ${ref}"
}

check_dockerfile() {
    local dockerfile="$1" line trimmed url ref last_git_url=""
    declare -gA VARS=()

    log ""
    log "=== ${dockerfile}"

    load_vars "${dockerfile}"

    while IFS= read -r line; do
        trimmed="${line#"${line%%[![:space:]]*}"}"
        [[ "${trimmed}" == "#"* ]] && continue

        if [[ "${trimmed}" == *"curl "* && "${trimmed}" =~ (https?://[^[:space:]|\\]+) ]]; then
            url="$(resolve_vars "${BASH_REMATCH[1]}")"
            check_archive "${url}" "curl"
            continue
        fi

        if [[ "${trimmed}" == *"wget "* && "${trimmed}" =~ (https?://[^[:space:]|\\]+) ]]; then
            url="$(resolve_vars "${BASH_REMATCH[1]}")"
            check_archive "${url}" "wget"
            continue
        fi

        if [[ "${trimmed}" == *"git clone"* && "${trimmed}" =~ (https?://[^[:space:]|\\]+) ]]; then
            url="$(resolve_vars "${BASH_REMATCH[1]}")"
            ref=""
            if [[ "${trimmed}" =~ (--branch|-b)[[:space:]]+([^[:space:]\\]+) ]]; then
                ref="$(resolve_vars "${BASH_REMATCH[2]}")"
            fi
            last_git_url="${url}"
            check_git "${url}" "${ref}" "git clone"
            continue
        fi

        if [[ "${trimmed}" =~ git[[:space:]]+checkout[[:space:]]+([^[:space:]\\&]+) ]] && [[ -n "${last_git_url}" ]]; then
            ref="$(resolve_vars "${BASH_REMATCH[1]}")"
            check_git "${last_git_url}" "${ref}" "git checkout"
            continue
        fi
    done <"${dockerfile}"
}

main() {
    local -a dockerfiles=("$@")
    if [[ ${#dockerfiles[@]} -eq 0 ]]; then
        mapfile -t dockerfiles < <(find "${SCRIPT_DIR}" -mindepth 2 -maxdepth 2 -name Dockerfile | sort)
    fi

    log "Checking source URLs with: curl ${CURL_OPTS[*]}"

    local dockerfile
    for dockerfile in "${dockerfiles[@]}"; do
        check_dockerfile "${dockerfile}"
    done

    log ""
    log "=== summary: ${TOTAL} checks, ${FAILURES} failure(s)"
    [[ ${FAILURES} -eq 0 ]]
}

main "$@"
