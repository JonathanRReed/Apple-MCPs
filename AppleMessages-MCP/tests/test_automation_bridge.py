import platform
import subprocess

import pytest

from apple_messages_mcp.messages_automation_bridge import MessagesAutomationBridge, MessagesAutomationBridgeError


@pytest.mark.parametrize('running,code', [('false', 'NOT_PROBED'), ('true', 'AUTHORIZATION_UNKNOWN')])
def test_diagnostic_checks_running_state_without_sending_apple_events(monkeypatch, running, code):
    def run(command, **kwargs):
        assert command[:3] == ['osascript', '-l', 'JavaScript']
        assert 'NSRunningApplication' in command[-1]
        assert 'System Events' not in command[-1]
        assert 'tell application' not in command[-1]
        assert kwargs['timeout'] == 5
        return subprocess.CompletedProcess(command, 0, running, '')

    monkeypatch.setattr(subprocess, 'run', run)
    accessible, error = MessagesAutomationBridge().automation_access_diagnostic()
    assert accessible is False
    assert error.error_code == code


@pytest.mark.parametrize('failure,code', [('timeout', 'AUTOMATION_TIMEOUT'), ('missing', 'OSASCRIPT_UNAVAILABLE'), ('command', 'AUTOMATION_FAILED')])
def test_diagnostic_reports_command_failures(monkeypatch, failure, code):
    def run(command, **kwargs):
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(command, kwargs['timeout'])
        if failure == 'missing':
            raise FileNotFoundError('osascript')
        return subprocess.CompletedProcess(command, 1, '', 'execution failed')

    monkeypatch.setattr(subprocess, 'run', run)
    accessible, error = MessagesAutomationBridge().automation_access_diagnostic()
    assert accessible is False
    assert error.error_code == code


def test_explicit_send_keeps_automation_and_bounds_execution(monkeypatch):
    def run(command, **kwargs):
        assert 'send "hello" to targetParticipant' in command[-1]
        assert 'service type = iMessage' in command[-1]  # default stays iMessage
        assert 'service type = SMS' not in command[-1]
        assert kwargs['timeout'] == 30
        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(subprocess, 'run', run)
    assert MessagesAutomationBridge().send_message('alice@example.com', 'hello')['sent'] is True


@pytest.mark.parametrize('stderr,code', [('Not authorized to send Apple events. (-1743)', 'PERMISSION_DENIED'), ('Automation command failed. (-1728)', 'AUTOMATION_FAILED')])
def test_send_distinguishes_denial_from_command_failure(monkeypatch, stderr, code):
    monkeypatch.setattr(subprocess, 'run', lambda command, **kwargs: subprocess.CompletedProcess(command, 1, '', stderr))
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge().send_message('alice@example.com', 'hello')
    assert raised.value.error_code == code


@pytest.mark.parametrize('code,status', [('NOT_PROBED', 'not_probed'), ('AUTHORIZATION_UNKNOWN', 'unknown'), ('PERMISSION_DENIED', 'denied'), ('AUTOMATION_FAILED', 'failed'), ('AUTOMATION_TIMEOUT', 'failed')])
def test_health_preserves_boolean_and_reports_diagnostic_status(monkeypatch, code, status):
    from apple_messages_mcp import tools
    class DB:
        def history_access_diagnostic(self):
            return False, None
    class Automation:
        def automation_access_diagnostic(self):
            return False, MessagesAutomationBridgeError(code, 'diagnostic')
    monkeypatch.setattr(tools, '_db_bridge', DB)
    monkeypatch.setattr(tools, '_automation_bridge', Automation)
    result = tools.messages_health()
    assert result.automation_access is False
    assert result.automation_access_status == status
    assert result.automation_access_error_code == code
    assert result.capabilities.can_send_messages is False


def test_diagnostic_rejects_unrecognized_running_state(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', lambda command, **kwargs: subprocess.CompletedProcess(command, 0, 'unexpected', ''))
    accessible, error = MessagesAutomationBridge().automation_access_diagnostic()
    assert accessible is False
    assert error.error_code == 'AUTOMATION_FAILED'


def test_send_timeout_does_not_retry(monkeypatch):
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        raise subprocess.TimeoutExpired(command, kwargs['timeout'])
    monkeypatch.setattr(subprocess, 'run', run)
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge().send_message('alice@example.com', 'hello')
    assert raised.value.error_code == 'AUTOMATION_TIMEOUT'
    assert len(calls) == 1


def test_send_with_sms_service_selects_sms_account_and_reports_it(monkeypatch):
    def run(command, **kwargs):
        assert 'service type = SMS and enabled is true' in command[-1]
        assert 'service type = iMessage' not in command[-1]
        return subprocess.CompletedProcess(command, 0, 'SMS\n', '')

    monkeypatch.setattr(subprocess, 'run', run)
    result = MessagesAutomationBridge().send_message('+61400000000', 'hi', service_name='sms')
    assert result['service_name'] == 'SMS'


def test_send_prefers_services_in_order(monkeypatch):
    def run(command, **kwargs):
        script = command[-1]
        assert script.index('service type = RCS') < script.index('service type = SMS')
        return subprocess.CompletedProcess(command, 0, 'SMS', '')

    monkeypatch.setattr(subprocess, 'run', run)
    assert MessagesAutomationBridge().send_message('+61400000000', 'hi', services=['RCS', 'SMS'])['service_name'] == 'SMS'


def test_send_rejects_unknown_service():
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge().send_message('+61400000000', 'hi', service_name='fax')
    assert raised.value.error_code == 'INVALID_INPUT'


def test_send_without_matching_account_reports_service_unavailable(monkeypatch):
    stderr = 'execution error: No enabled Messages account for this service (9001)'
    monkeypatch.setattr(subprocess, 'run', lambda command, **kwargs: subprocess.CompletedProcess(command, 1, '', stderr))
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge().send_message('+61400000000', 'hi', service_name='SMS')
    assert raised.value.error_code == 'SERVICE_UNAVAILABLE'
    assert 'Text Message Forwarding' in raised.value.suggestion


def test_send_attachment_honours_service(monkeypatch):
    def run(command, **kwargs):
        assert 'service type = SMS' in command[-1]
        assert 'send POSIX file "/tmp/a.png" to targetParticipant' in command[-1]
        return subprocess.CompletedProcess(command, 0, 'SMS', '')

    monkeypatch.setattr(subprocess, 'run', run)
    assert MessagesAutomationBridge().send_attachment('+61400000000', '/tmp/a.png', service_name='SMS')['service_name'] == 'SMS'


_NO_ACCOUNT = 'execution error: No enabled Messages account for this service (9001)'


def _fail_with(monkeypatch, stderr):
    monkeypatch.setattr(subprocess, 'run', lambda command, **kwargs: subprocess.CompletedProcess(command, 1, '', stderr))


def test_inferred_sms_without_account_names_the_thread_and_the_retry(monkeypatch):
    _fail_with(monkeypatch, _NO_ACCOUNT)
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge().send_message('+61400000000', 'hi', services=['SMS'])
    error = raised.value
    assert error.error_code == 'SERVICE_UNAVAILABLE'
    assert "This thread's last message used SMS" in error.message
    assert 'Text Message Forwarding is off' in error.message
    assert "Retry with service_name='iMessage'" in error.suggestion
    assert 'Text Message Forwarding' in error.suggestion


def test_inferred_rcs_without_account_lists_the_fallback_it_tried(monkeypatch):
    _fail_with(monkeypatch, _NO_ACCOUNT)
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge().send_message('+61400000000', 'hi', services=['RCS', 'SMS'])
    assert "This thread's last message used RCS" in raised.value.message
    assert 'no enabled RCS or SMS account' in raised.value.message


def test_explicit_sms_without_account_says_it_was_requested(monkeypatch):
    _fail_with(monkeypatch, _NO_ACCOUNT)
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge().send_message('+61400000000', 'hi', service_name='SMS', services=['RCS'])
    assert "service_name='SMS' was requested" in raised.value.message
    assert 'thread' not in raised.value.message
    assert "Retry with service_name='iMessage'" in raised.value.suggestion


def test_default_imessage_without_account_suggests_signing_in(monkeypatch):
    _fail_with(monkeypatch, _NO_ACCOUNT)
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge().send_message('alice@example.com', 'hi')
    assert raised.value.message.startswith('This Mac has no enabled iMessage account')
    assert 'Sign in to iMessage' in raised.value.suggestion


@pytest.mark.parametrize('kwargs', [{'service_name': 'RCS'}, {'services': ['RCS']}])
def test_rcs_on_pre_sequoia_mac_is_refused_before_running_applescript(monkeypatch, kwargs):
    monkeypatch.setattr(platform, 'mac_ver', lambda: ('14.6.1', ('', '', ''), 'arm64'))
    monkeypatch.setattr(subprocess, 'run', lambda *args, **kw: pytest.fail('osascript must not run'))
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge().send_message('+61400000000', 'hi', **kwargs)
    assert raised.value.error_code == 'SERVICE_UNAVAILABLE'
    assert 'macOS 15 or later' in raised.value.message
    assert '14.6.1' in raised.value.message
    assert "service_name='SMS'" in raised.value.suggestion


def test_inferred_rcs_on_pre_sequoia_mac_falls_back_to_sms_only(monkeypatch):
    monkeypatch.setattr(platform, 'mac_ver', lambda: ('14.6.1', ('', '', ''), 'arm64'))

    def run(command, **kwargs):
        assert 'RCS' not in command[-1]
        assert 'service type = SMS' in command[-1]
        return subprocess.CompletedProcess(command, 0, 'SMS', '')

    monkeypatch.setattr(subprocess, 'run', run)
    assert MessagesAutomationBridge().send_message('+61400000000', 'hi', services=['RCS', 'SMS'])['service_name'] == 'SMS'


@pytest.mark.parametrize('release', ['15.0', '26.6.2', '10.16', ''])
def test_rcs_is_kept_on_sequoia_or_when_the_version_is_unknown(monkeypatch, release):
    monkeypatch.setattr(platform, 'mac_ver', lambda: (release, ('', '', ''), 'arm64'))

    def run(command, **kwargs):
        assert 'service type = RCS' in command[-1]
        return subprocess.CompletedProcess(command, 0, 'RCS', '')

    monkeypatch.setattr(subprocess, 'run', run)
    assert MessagesAutomationBridge().send_message('+61400000000', 'hi', service_name='RCS')['service_name'] == 'RCS'


def test_undefined_rcs_enumerator_maps_to_service_unavailable(monkeypatch):
    monkeypatch.setattr(platform, 'mac_ver', lambda: ('10.16', ('', '', ''), 'x86_64'))
    _fail_with(monkeypatch, 'execution error: The variable RCS is not defined. (-2753)')
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge().send_message('+61400000000', 'hi', service_name='RCS')
    assert raised.value.error_code == 'SERVICE_UNAVAILABLE'
    assert 'no RCS service' in raised.value.message
    assert "service_name='SMS'" in raised.value.suggestion
