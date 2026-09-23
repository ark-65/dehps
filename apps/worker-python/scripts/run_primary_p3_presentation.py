"""The retained primary CLI prepares facts; this downstream consumer styles them."""
import argparse
from contextlib import contextmanager
import fcntl
import importlib.util
import json
from pathlib import Path
import sys

# This script is loaded by the retained namespace bootstrap. Dependencies stay
# on its frozen path; only this additive package is imported from the release.
package = Path(__file__).resolve().parents[1] / 'dehps/notifications/primary_style'
spec = importlib.util.spec_from_file_location('dehps_primary_style', package / '__init__.py', submodule_search_locations=[str(package)])
module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
from dehps_primary_style import mainline as style
from dehps_primary_style.render import require
from dehps.agents.repository import AgentRequestRepository
from dehps.config import ROOT_DIR
from dehps.notifications import p3_top100 as original
from dehps.notifications.mail import QqMailConfig
from dehps.research_os.repository import PostgresResearchOSRepository
import run_m4_p3_top100_notification as canonical


@contextmanager
def exclusive():
    path = ROOT_DIR / 'runtime/notifications/primary-p3-presentation.lock'
    with path.open('a+') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def authorize(release):
    repo = AgentRequestRepository()
    for role in ('engineering', 'operator'):
        binding = release[role]; request = repo.get_request(binding['key'])
        require(request.id == binding['id'] and style.digest(request.payload) == binding['payload_sha256']
                and request.status.value in ('executing', 'completed'), role + ' admission changed')
        decisions = repo.list_decisions(binding['key'])
        require(any(d.decision_code == 'request_approved' and d.decided_by == release['reviewer_principal'] for d in decisions), 'actual reviewer binding missing')
    original.load_source_contract(); original.verify_governance(repo)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['pre', 'post', 'acceptance', 'replay'])
    parser.add_argument('--release', required=True, type=Path)
    parser.add_argument('--deliver', action='store_true')
    args = parser.parse_args()
    require(not args.deliver or args.mode in ('pre', 'post'), 'acceptance/replay cannot send')
    release = json.loads(args.release.read_bytes()); authorize(release)
    require(release['style_source_sha256'] == style.source_identity(), 'release style source changed')
    repository = PostgresResearchOSRepository(); config = QqMailConfig.from_environment()
    require(original._recipient_digest(config.destination) == release['recipient_digest'], 'recipient differs')
    with exclusive():
        if args.mode in ('acceptance', 'replay'):
            reports = []
            for issue, kind in release['acceptance_targets']:
                if args.mode == 'acceptance':
                    email, proofs = style.prepare(repository, ROOT_DIR, config.destination, issue, kind, git_commit=release['commit'])
                    style.publish_readable(ROOT_DIR, email)
                else:
                    supervisor = style.PresentationSupervisor(repository=repository, root_dir=ROOT_DIR, recipient=config.destination, git_commit=release['commit'])
                    email = style.consume(supervisor, issue, kind)
                    proofs = [supervisor.replay(task_key=k) for k in style.keys(issue, kind).values()]
                reports.append({'issue': issue, 'kind': kind, 'delivery_key': email.delivery_key, 'proofs': proofs})
            result = {'status': 'REPLAY_VERIFIED', 'reports': reports, 'external_delivery': False}
        else:
            # Preserve the canonical issue selection, source/governance checks,
            # draw-time checks, payout acquisition and original task execution.
            prepared = getattr(canonical, args.mode)(apply=True, deliver=False, repository=repository, config=config)
            if not prepared.get('issue'):
                result = prepared
            else:
                email, proofs = style.prepare(repository, ROOT_DIR, config.destination, prepared['issue'], args.mode, git_commit=release['commit'])
                style.publish_readable(ROOT_DIR, email)
                # Compilation/replay can take time. Recheck the real pre-draw
                # deadline immediately before the original ledger and SMTP.
                if args.deliver and args.mode == 'pre':
                    from datetime import datetime, UTC
                    bundle = original.load_predraw_bundle(repository, issue=email.issue)
                    original.require_pre_draw_window(datetime.now(UTC), official_draw_time=bundle.checkpoint['body']['official_draw_time'])
                delivery = original.P3Top100NotificationDeliveryService(config).deliver(email) if args.deliver else None
                result = {**prepared, 'presentation_replay': proofs, 'delivery': delivery, 'external_delivery': bool(args.deliver)}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
