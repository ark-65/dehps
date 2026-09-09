"""Real kernel-denied writes from a non-root, offline, read-only container."""
import json
import os
from pathlib import Path
import subprocess


def test_domains_cannot_write_read_only_formal_or_peer_mounts(tmp_path):
    image = os.environ["DEHPS_EXECUTION_OS_IMAGE"]
    assert image.startswith("sha256:") or "@sha256:" in image, "pin the test image identity"
    formal = tmp_path / "formal"
    formal.mkdir(mode=0o700)
    sentinel = formal / "sentinel"
    sentinel.write_text("preserved")
    before = (sentinel.read_bytes(), sentinel.stat().st_mtime_ns)
    sources = Path(__file__).resolve().parents[1] / "dehps/execution"
    domains = {name: tmp_path / name for name in ("observer", "learning")}
    for root in domains.values():
        root.mkdir(mode=0o700)
        (root / "sentinel").write_text("peer")
    script = r'''
import errno, json, os
from pathlib import Path
from dehps.execution.context import RunContext
domain=os.environ['TEST_DOMAIN']
context=RunContext(Path('/runtime'), domain)
for state in ('starting','waiting','running','completed','failed'):
    for area in ('state','status','logs'):
        context.write_projection(area, 'latest.json', {'state':state})
        assert context.read_projection(area,'latest.json') == {'state':state}
    # Bypass the application API deliberately: the kernel still has to refuse.
    for path in ('/formal/sentinel','/peer/sentinel'):
        try:
            with open(path,'w') as stream: stream.write('illegal')
        except OSError as error:
            assert error.errno in (errno.EROFS, errno.EACCES), error
        else: raise AssertionError('cross-domain write succeeded')
    try: RunContext(Path('/formal'),domain).write_projection('status','wrong.json',{})
    except OSError as error: assert error.errno in (errno.EROFS,errno.EACCES), error
    else: raise AssertionError('wrong runtime root was writable')
assert not Path('/home/ark/workspace/dehps/.env').exists()
print(json.dumps({'domain':domain,'states':5,'kernel_denials':15}))
'''
    for domain, peer in (("observer", "learning"), ("learning", "observer")):
        result = subprocess.run([
            "docker", "run", "--rm", "--network=none", "--read-only",
            "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--user", f"{os.getuid()}:{os.getgid()}",
            "--mount", f"type=bind,src={sources},dst=/code/dehps/execution,readonly",
            "--mount", f"type=bind,src={formal},dst=/formal,readonly",
            "--mount", f"type=bind,src={domains[peer]},dst=/peer,readonly",
            "--mount", f"type=bind,src={domains[domain]},dst=/runtime",
            "--env", "PYTHONPATH=/code", "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--env", f"TEST_DOMAIN={domain}", image, "python", "-c", script,
        ], check=False, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == {"domain": domain, "states": 5, "kernel_denials": 15}
    assert (sentinel.read_bytes(), sentinel.stat().st_mtime_ns) == before
    assert all((root / "sentinel").read_text() == "peer" for root in domains.values())
