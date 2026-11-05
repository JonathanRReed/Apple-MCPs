import platform
import subprocess
import time
from pathlib import Path

import pytest

from apple_messages_mcp import messages_automation_bridge
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


class FakeMessages:
    """Stands in for osascript: records sends and reports transfers in the given order."""

    def __init__(self, *statuses, service='iMessage', known='', registers=True):
        self.statuses = list(statuses)
        self.service = service
        self.known = known
        self.registers = registers
        self.calls = []
        self.sent_name = None

    def __call__(self, command, **kwargs):
        script = command[-1]
        if 'every file transfer' in script:
            output = self.known
            if self.sent_name is not None and self.registers:
                status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
                output += f'new-id\t{self.sent_name}\t{status}\n'
            return subprocess.CompletedProcess(command, 0, output, '')
        self.calls.append(script)
        for line in script.split('\n'):
            if 'send POSIX file' in line:
                self.sent_name = line.split('"')[1].rsplit('/', 1)[1]
        return subprocess.CompletedProcess(command, 0, self.service, '')

    def sent_path(self):
        return next(line.split('"')[1] for script in self.calls for line in script.split('\n') if 'send POSIX file' in line)


@pytest.fixture
def messages_home(monkeypatch, tmp_path):
    home = tmp_path / 'home'
    (home / 'Library' / 'Messages' / 'Attachments').mkdir(parents=True)
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setattr(time, 'sleep', lambda seconds: None)
    file = tmp_path.resolve() / 'files' / 'a.png'
    file.parent.mkdir()
    file.write_text('image')
    return home.resolve(), file


def _send(monkeypatch, fake, file, **kwargs):
    monkeypatch.setattr(subprocess, 'run', fake)
    return MessagesAutomationBridge((file.parent,)).send_attachment('+61400000000', str(file), **kwargs)


def test_send_attachment_honours_service(monkeypatch, messages_home):
    _, file = messages_home
    fake = FakeMessages('finished', service='SMS')
    result = _send(monkeypatch, fake, file, service_name='SMS')
    assert 'service type = SMS' in fake.calls[0]
    assert result['service_name'] == 'SMS' and result['file_path'] == str(file)


def test_send_attachment_sends_a_private_copy_from_the_messages_folder(monkeypatch, messages_home):
    home, file = messages_home
    fake = FakeMessages('waiting', 'finished')
    _send(monkeypatch, fake, file)
    staged = fake.sent_path()
    assert staged.startswith(str(home / 'Library' / 'Messages' / 'Attachments' / 'apple-mcp'))
    assert staged.endswith('/a.png')
    assert Path(staged).read_text() == 'image'


def test_send_attachment_sends_the_text_only_after_the_file_is_confirmed(monkeypatch, messages_home):
    _, file = messages_home
    fake = FakeMessages('finished')
    _send(monkeypatch, fake, file, text='caption')
    assert len(fake.calls) == 2
    assert 'send POSIX file' in fake.calls[0] and 'send "caption"' in fake.calls[1]


def test_failed_transfer_is_reported_and_sends_no_text(monkeypatch, messages_home):
    home, file = messages_home
    fake = FakeMessages('waiting', 'failed')
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        _send(monkeypatch, fake, file, text='caption')
    assert raised.value.error_code == 'ATTACHMENT_NOT_DELIVERED'
    assert len(fake.calls) == 1
    assert not any((home / 'Library' / 'Messages' / 'Attachments' / 'apple-mcp').iterdir())


def test_unconfirmed_transfer_says_not_to_retry_and_sends_no_text(monkeypatch, messages_home):
    _, file = messages_home
    monkeypatch.setattr(messages_automation_bridge, '_TRANSFER_WAIT_SECONDS', 0)
    fake = FakeMessages('waiting')
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        _send(monkeypatch, fake, file, text='caption')
    assert raised.value.error_code == 'SEND_STATUS_UNKNOWN'
    assert 'before sending again' in raised.value.suggestion
    assert len(fake.calls) == 1


def test_an_older_transfer_of_the_same_name_is_not_taken_as_this_send(monkeypatch, messages_home):
    _, file = messages_home
    monkeypatch.setattr(messages_automation_bridge, '_TRANSFER_WAIT_SECONDS', 0)
    fake = FakeMessages('finished', known='old-id\ta.png\tfinished\n', registers=False)
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        _send(monkeypatch, fake, file)
    assert raised.value.error_code == 'SEND_STATUS_UNKNOWN'


def test_a_failed_status_read_while_waiting_does_not_end_the_wait(monkeypatch, messages_home):
    _, file = messages_home
    fake = FakeMessages('finished')
    reads = []

    def run(command, **kwargs):
        if 'every file transfer' in command[-1]:
            reads.append(1)
            if len(reads) == 2:
                return subprocess.CompletedProcess(command, 1, '', 'boom')
        return fake(command, **kwargs)

    monkeypatch.setattr(subprocess, 'run', run)
    assert MessagesAutomationBridge((file.parent,)).send_attachment('+61400000000', str(file))['sent'] is True
    assert len(reads) == 3


def test_the_text_uses_the_service_the_file_went_over(monkeypatch, messages_home):
    _, file = messages_home
    fake = FakeMessages('finished', service='SMS')
    _send(monkeypatch, fake, file, service_name='SMS', text='caption')
    assert 'service type = SMS' in fake.calls[1]


def test_a_nul_character_fails_before_anything_is_sent(monkeypatch, messages_home):
    _, file = messages_home
    fake = FakeMessages('finished')
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        _send(monkeypatch, fake, file, text='cap\0tion')
    assert raised.value.error_code == 'INVALID_INPUT'
    assert fake.calls == []


def test_a_timeout_before_sending_says_nothing_was_sent(monkeypatch, messages_home):
    _, file = messages_home

    def run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 30)

    monkeypatch.setattr(subprocess, 'run', run)
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge((file.parent,)).send_attachment('+61400000000', str(file))
    assert raised.value.message.startswith('Nothing was sent')
    assert raised.value.suggestion == 'It is safe to retry.'


def test_a_text_failure_message_does_not_also_say_nothing_was_sent(monkeypatch, messages_home):
    _, file = messages_home
    fake = FakeMessages('finished')

    def run(command, **kwargs):
        if 'send "caption"' in command[-1]:
            return subprocess.CompletedProcess(command, 1, '', 'execution error: No enabled Messages account for this service (9001)')
        return fake(command, **kwargs)

    monkeypatch.setattr(subprocess, 'run', run)
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge((file.parent,)).send_attachment('+61400000000', str(file), text='caption')
    assert raised.value.message.startswith('The file was sent')
    assert 'Nothing was sent' not in raised.value.message


def test_a_failed_copy_leaves_nothing_behind(monkeypatch, messages_home):
    home, file = messages_home
    monkeypatch.setattr(messages_automation_bridge.shutil, 'copyfile', lambda source, target: (_ for _ in ()).throw(OSError('disk full')))
    fake = FakeMessages('finished')
    _send(monkeypatch, fake, file)
    assert fake.sent_path() == str(file)
    assert not any((home / 'Library' / 'Messages' / 'Attachments' / 'apple-mcp').iterdir())


def test_a_file_name_with_a_line_separator_is_still_confirmed(monkeypatch, messages_home):
    _, file = messages_home
    odd = file.with_name('a\u2028b.png')
    odd.write_text('image')
    assert _send(monkeypatch, FakeMessages('finished'), odd)['sent'] is True


def test_two_new_transfers_of_the_same_name_are_treated_as_unknown(monkeypatch, messages_home):
    home, file = messages_home
    fake = FakeMessages('finished')
    real = fake.__call__

    def run(command, **kwargs):
        result = real(command, **kwargs)
        if 'every file transfer' in command[-1] and fake.sent_name is not None:
            result = subprocess.CompletedProcess(command, 0, result.stdout + f'other-id\t{fake.sent_name}\tfailed\n', '')
        return result

    monkeypatch.setattr(subprocess, 'run', run)
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge((file.parent,)).send_attachment('+61400000000', str(file), text='caption')
    assert raised.value.error_code == 'SEND_STATUS_UNKNOWN'
    assert len(fake.calls) == 1
    assert any((home / 'Library' / 'Messages' / 'Attachments' / 'apple-mcp').iterdir())


def test_a_send_timeout_keeps_the_staged_file(monkeypatch, messages_home):
    home, file = messages_home
    fake = FakeMessages('finished')

    def run(command, **kwargs):
        if 'send POSIX file' in command[-1]:
            raise subprocess.TimeoutExpired(command, 30)
        return fake(command, **kwargs)

    monkeypatch.setattr(subprocess, 'run', run)
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge((file.parent,)).send_attachment('+61400000000', str(file))
    assert raised.value.error_code == 'AUTOMATION_TIMEOUT'
    assert any((home / 'Library' / 'Messages' / 'Attachments' / 'apple-mcp').iterdir())


def test_a_definite_send_failure_removes_the_staged_file(monkeypatch, messages_home):
    home, file = messages_home
    fake = FakeMessages('finished')

    def run(command, **kwargs):
        if 'send POSIX file' in command[-1]:
            return subprocess.CompletedProcess(command, 1, '', 'boom')
        return fake(command, **kwargs)

    monkeypatch.setattr(subprocess, 'run', run)
    with pytest.raises(MessagesAutomationBridgeError):
        MessagesAutomationBridge((file.parent,)).send_attachment('+61400000000', str(file))
    assert not any((home / 'Library' / 'Messages' / 'Attachments' / 'apple-mcp').iterdir())


def test_a_failed_status_read_before_sending_stages_nothing(monkeypatch, messages_home):
    home, file = messages_home
    monkeypatch.setattr(subprocess, 'run', lambda command, **kwargs: subprocess.CompletedProcess(command, 1, '', 'boom'))
    with pytest.raises(MessagesAutomationBridgeError):
        MessagesAutomationBridge((file.parent,)).send_attachment('+61400000000', str(file))
    assert not (home / 'Library' / 'Messages' / 'Attachments' / 'apple-mcp').exists()


def test_without_the_messages_folder_the_file_is_sent_directly_and_still_checked(monkeypatch, messages_home, tmp_path):
    _, file = messages_home
    monkeypatch.setenv('HOME', str(tmp_path / 'no-such-home'))
    fake = FakeMessages('failed')
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        _send(monkeypatch, fake, file)
    assert fake.sent_path() == str(file)
    assert raised.value.error_code == 'ATTACHMENT_NOT_DELIVERED'
    assert 'Full Disk Access' in raised.value.suggestion and 'disk space' in raised.value.suggestion
    assert file.exists()


def test_a_text_timeout_after_the_file_says_to_check_before_resending_the_text(monkeypatch, messages_home):
    _, file = messages_home
    fake = FakeMessages('finished')

    def run(command, **kwargs):
        if 'send "caption"' in command[-1]:
            raise subprocess.TimeoutExpired(command, 30)
        return fake(command, **kwargs)

    monkeypatch.setattr(subprocess, 'run', run)
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge((file.parent,)).send_attachment('+61400000000', str(file), text='caption')
    assert raised.value.error_code == 'AUTOMATION_TIMEOUT'
    assert 'did not confirm the text' in raised.value.message
    assert 'the text was not' not in raised.value.message
    assert 'Check the conversation before sending the text again' in raised.value.suggestion
    assert 'Do not send the file again' in raised.value.suggestion


def test_a_text_failure_after_the_file_says_not_to_resend_the_file(monkeypatch, messages_home):
    _, file = messages_home
    fake = FakeMessages('finished')

    def run(command, **kwargs):
        if 'send "caption"' in command[-1]:
            return subprocess.CompletedProcess(command, 1, '', 'boom')
        return fake(command, **kwargs)

    monkeypatch.setattr(subprocess, 'run', run)
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge((file.parent,)).send_attachment('+61400000000', str(file), text='caption')
    assert 'The file was sent' in raised.value.message
    assert 'Do not send the file again' in raised.value.suggestion


@pytest.fixture
def attachment_folders(monkeypatch, tmp_path):
    def must_not_run(command, **kwargs):
        raise AssertionError('Messages must not be reached for a refused attachment')

    monkeypatch.setattr(subprocess, 'run', must_not_run)
    root = (tmp_path / 'root').resolve()
    outside = (tmp_path / 'outside').resolve()
    root.mkdir()
    outside.mkdir()
    (outside / 'secret.txt').write_text('private')
    (root / 'link.txt').symlink_to(outside / 'secret.txt')
    (root / 'folder').mkdir()
    return root, outside


@pytest.mark.parametrize('spelling', ('{outside}/secret.txt', '{root}/../outside/secret.txt', '{root}/link.txt', '{root}'))
def test_attachment_outside_the_allowed_folders_is_refused(attachment_folders, spelling):
    root, outside = attachment_folders
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge((root,)).send_attachment('+61400000000', spelling.format(root=root, outside=outside))
    assert raised.value.error_code == 'PATH_NOT_ALLOWED'
    assert str(root) in raised.value.suggestion and 'APPLE_MESSAGES_MCP_ALLOWED_ROOTS' in raised.value.suggestion


def test_attachment_is_refused_when_no_folders_are_allowed(attachment_folders):
    _, outside = attachment_folders
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge().send_attachment('+61400000000', str(outside / 'secret.txt'))
    assert raised.value.error_code == 'PATH_NOT_ALLOWED'


@pytest.mark.parametrize('name', ('missing.txt', 'folder'))
def test_attachment_must_be_an_existing_file(attachment_folders, name):
    root, _ = attachment_folders
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge((root,)).send_attachment('+61400000000', str(root / name))
    assert raised.value.error_code == 'FILE_NOT_FOUND'


def test_an_unknown_home_folder_is_a_coded_error(attachment_folders):
    root, _ = attachment_folders
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge((root,)).send_attachment('+61400000000', '~no_such_user_here/a.txt')
    assert raised.value.error_code == 'INVALID_INPUT'


def test_a_file_that_cannot_be_checked_is_a_coded_error(monkeypatch, attachment_folders):
    root, _ = attachment_folders
    monkeypatch.setattr(Path, 'is_file', lambda self: (_ for _ in ()).throw(PermissionError(13, 'Permission denied')))
    with pytest.raises(MessagesAutomationBridgeError) as raised:
        MessagesAutomationBridge((root,)).send_attachment('+61400000000', str(root / 'locked.txt'))
    assert raised.value.error_code == 'FILE_NOT_FOUND'


def test_attachment_under_a_root_reached_by_a_link_is_sent(monkeypatch, messages_home, tmp_path):
    real = tmp_path.resolve() / 'real'
    real.mkdir()
    (real / 'a.png').write_text('image')
    link = tmp_path / 'link'
    link.symlink_to(real)
    monkeypatch.setattr(subprocess, 'run', FakeMessages('finished'))
    assert MessagesAutomationBridge((link,)).send_attachment('+61400000000', str(link / 'a.png'))['file_path'] == str(real / 'a.png')


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
