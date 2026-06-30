# Self-Iteration: Git Attribution

## Primary Goal

Make scheduled DEHPS self-iteration commits appear under the project GitHub identities instead of the local `Ark Codex <codex@local>` identity.

## Non-Goals

- Do not rewrite existing self-iteration commits.
- Do not change daily pipeline `auto-git` attribution.
- Do not change the self-iteration safety guard or push target.

## Change

`scripts/hourly_self_iterate.sh` now exports Git author and committer identity before launching Codex:

- `ark-65 <25193106+ark-65@users.noreply.github.com>`

The script also passes `core.hooksPath=scripts/git-hooks` to child Git commands. The tracked `commit-msg` hook appends this trailer when the scheduled self-iteration environment is present:

- `Co-authored-by: give me a 98K <240642031+inhuman-0@users.noreply.github.com>`

This mirrors the public attribution shape used by `zhongmiao-org/mermaid-markdown-bridge#31`, where the commit is tied to ark-65 and carries the inhuman-0 co-author trailer.

## Validation

```bash
bash -n scripts/hourly_self_iterate.sh
```

```bash
tmpdir="$(mktemp -d)"
git -C "$tmpdir" init -q
mkdir -p "$tmpdir/hooks"
cp scripts/git-hooks/commit-msg "$tmpdir/hooks/commit-msg"
chmod +x "$tmpdir/hooks/commit-msg"
git -C "$tmpdir" config user.name "ark-65"
git -C "$tmpdir" config user.email "25193106+ark-65@users.noreply.github.com"
printf 'smoke\n' > "$tmpdir/file.txt"
git -C "$tmpdir" add file.txt
DEHPS_SELF_ITERATE_GIT_COAUTHOR_TRAILER='Co-authored-by: give me a 98K <240642031+inhuman-0@users.noreply.github.com>' \
  git -C "$tmpdir" -c core.hooksPath="$tmpdir/hooks" commit -m "self-iterate: smoke attribution"
git -C "$tmpdir" log -1 --format='%an <%ae>%n%B'
rm -rf "$tmpdir"
```

The smoke commit body included the inhuman-0 co-author trailer.
