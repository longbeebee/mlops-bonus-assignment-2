#!/usr/bin/env bash

# Shared Telegram notification helper for shell-based tests.

_TEST_ALERT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${_TEST_ALERT_DIR}/../.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${_TEST_ALERT_DIR}/../.env"
    set +a
fi

notify_test_failure() {
    local test_name="${1:-unknown test}"
    local exit_code="${2:-1}"
    local failed_command="${3:-unknown command}"

    if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" ]]; then
        echo "Telegram test alert skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not configured." >&2
        return 0
    fi

    local message
    message="❌ Test failed
Test: ${test_name}
Exit code: ${exit_code}
Command: ${failed_command}"

    local response
    if ! response=$(curl --fail --silent --show-error --max-time 10 \
        --request POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
        --data-urlencode "text=${message}"); then
        echo "Failed to send Telegram test alert." >&2
        return 0
    fi

    if [[ "${response}" != *'"ok":true'* ]]; then
        echo "Telegram rejected the test alert." >&2
    fi
}

install_test_failure_alert() {
    _TEST_ALERT_NAME="$1"

    trap 'exit_code=$?; if (( exit_code != 0 )); then notify_test_failure "${_TEST_ALERT_NAME}" "${exit_code}" "${BASH_COMMAND}"; fi' EXIT
}
