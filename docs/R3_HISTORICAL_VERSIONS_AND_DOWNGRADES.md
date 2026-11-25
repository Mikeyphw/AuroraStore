# R3A — Historical versions and safe downgrade requests

## Scope

The manual version picker uses **Exodus** reports as historical metadata. Exodus is **not**
a Google **Play** APK archive, and a version listed there is not proof that Play will serve it.
The UI deduplicates positive 64-bit numeric version codes, sorts numerically, and labels
versions older than the currently installed app.

A user may enter a historical version code manually. Invalid, zero, negative, non-numeric,
and overflowing version codes are not executable requests. Network lookup errors leave the
manual input usable rather than crashing the coroutine.

For any version different from the current Play listing, Aurora sends no stale file URLs or
fabricated static-library version codes from the latest release. The download worker resolves
the selected version's files by its exact requested version code. This avoids accidentally
reusing *latest-release download URLs* for an older version. Availability is not guaranteed.

## Downgrade and data safety

If the requested version is lower than the installed version, the manual screen requires
explicit acknowledgement of the version comparison, potential data incompatibility, and
Android platform downgrade restrictions. There is **no automatic uninstall**, no root
`-d` downgrade flag, no data-clearing fallback, and no hidden bypass of platform protections.
A confirmed request may still be rejected by Android; no success is claimed until the actual
installed version matches the exact requested version in the R2A/R2B/R2C result and restart
policies. A newer installed version cannot falsely satisfy an older download attempt. Backups
remain the user's responsibility.

R3A does not provide an API to fetch older APKs from third-party mirrors, override signing
checks, or automatically install incompatible downgrades. A release policy involving safe
manual uninstall and explicit data-loss acknowledgement is out of scope.

## Qualification

`check_r3.py` and `HistoricalVersionPolicyTest` run in Foundation CI. Android build, JVM
and ktlint qualification run only on hosted GitHub Actions. API 36 emulator installation and
process-death recovery remain covered by R2D. No live historical Play availability or physical
device downgrade qualification is claimed.

## Audited safety/UX refinements

The manual screen no longer force-unwraps Play app metadata while it is loading, and
all install inputs remain disabled until app details are available. A selected Exodus
code is normalized to its canonical decimal form, then revalidated before the
downgrade confirmation is accepted. The confirmation is rejected if the installed
version or selected code changes while the dialog is open.

The passive Exodus privacy-report request and the manual history picker now share
one guarded network fetch. Network errors leave version entry usable, and a failed
request cannot crash an uncaught privacy-report coroutine. Cancellation is propagated.

This does not attest that an APK returned by Play has the requested package identity
or signer; that validation and live historical-version availability remain future
qualification work.
