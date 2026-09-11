# Retained P3 canonical runtime alias

A pre-transition check found that the packaged cd069c1 resident source had an
empty `runtime` directory instead of its original symlink to the canonical
production runtime. Its frozen supervisor derives `state_path` from this root;
the missing alias would place status writes inside readonly packaged source.
Request 817/execution 658 installed package799e8648, then stopped before any timer
pause or resident restart. The failed preflight is recorded; the package and its
actual human approval remain preserved.

The corrected package preserves the original absolute runtime symlink and its
existing `/runtime` Git exclude rule (original shared `.git/info/exclude`, line8).
The rule hides only the runtime alias; source object history is unchanged. The
launcher rejects an absent or different alias. Offline acceptance now constructs
the original frozen supervisor without dispatch or database access, reads its
actual default state_path, and requires both canonical resolution and the same
existing status file. Its namespace also checks the runtime symlink directly.
Frozen source files, dependencies, Git history, scientific contracts and results
remain unchanged. The independent learning/observer domains are unaffected.

Validation: six targeted mount/Git tests passed. Full nine-entry real namespace
acceptance, original frozen contracts and the actual resident path probe are
passed and are recorded with the final release evidence. These inspections use
readonly data mounts and no network. They are not production execution or report
acceptance.

Report impact: this preflight prevented a new status-write regression. No services
or timers were changed by Request817; 816's previous rollback remains in effect.
The unsupported objective class, 2026105 settlement/post-report gap and 2026104
missed deadline are retained as baseline defects. Current-cycle report acceptance
is still incomplete; no resend, task reset or scientific conclusion change.

The owner subsequently instructed that following tasks be automatically approved
until the goal is complete. Any delegated approval must record that instruction
and the executing agent truthfully; it must not claim another interactive human
review occurred or overwrite decisions 3481/3486. The exact corrected package and
operation still require their own auditable request and execution identity.
