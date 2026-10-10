import plistlib
import subprocess

import pytest

from apple_system_mcp.system_bridge import SystemBridge, SystemBridgeError


@pytest.mark.parametrize("domain", ["/tmp/fixture", "../fixture", "~/Library/test", "-currentHost", "com.apple/finder", "", "com.apple finder", r"C:\fixture"])
def test_preference_domain_rejects_paths_and_options_before_subprocess(monkeypatch, domain):
    def unexpected(*a, **kw):
        raise AssertionError("invalid domain reached defaults")
    monkeypatch.setattr(subprocess, "run", unexpected)
    with pytest.raises(SystemBridgeError) as error:
        SystemBridge().read_preference_domain(domain)
    assert error.value.error_code == "INVALID_INPUT"


@pytest.mark.parametrize("domain,normalized", [("com.apple.finder", "com.apple.finder"), ("custom-domain", "custom-domain"), ("-g", "NSGlobalDomain"), ("-globalDomain", "NSGlobalDomain")])
def test_named_preference_domains_and_global_aliases_remain_supported(monkeypatch, domain, normalized):
    def run(command, **kw):
        assert command == ["defaults", "-currentHost", "export", normalized, "-"]
        return subprocess.CompletedProcess(command, 0, stdout=plistlib.dumps({"fixture": True}))
    monkeypatch.setattr(subprocess, "run", run)
    assert SystemBridge().read_preference_domain(domain, current_host=True) == {"fixture": True}
