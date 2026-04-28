<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Contributing

This page covers contributions to the **RMR and BRMR kernel modules**. Corrections or additions to this documentation itself follow a separate, lighter flow in the documentation repository.

## Scope and repositories

- **Code** (RMR and BRMR kernel modules): <https://github.com/ionos-cloud/RMR>.
- **Documentation** (this site): a separate repository. Please do not mix code and documentation changes in the same patch.

## Reporting bugs

File bugs on the source-code repository's issue tracker. A useful report includes:

- Kernel version (`uname -r`) and distribution.
- RMR commit being tested (`git log -1 --oneline`).
- Output of `modinfo` for the loaded RMR/BRMR modules.
- Relevant `dmesg` around the failure.
- Steps to reproduce.
- Whether the bug is reproducible on every run or intermittent.

For security-sensitive issues, please do not file a public issue — contact the maintainers privately.

## Building from source

RMR and BRMR are out-of-tree Linux kernel modules.

- Install kernel headers matching the target kernel (`linux-headers-$(uname -r)` on Debian/Ubuntu).
- `make` in the source-code repository root.
- Load modules in dependency order: `rtrs-*`, then `rmr-*`, then `brmr-*`. Unload in reverse order.

See the [User/admin guide to RMR cluster management](../guide/cluster-management.md) for a full two-node bring-up.

## Testing

*TBD*

## Coding style

RMR and BRMR follow the **Linux kernel coding style**. Read it once:

- <https://docs.kernel.org/process/coding-style.html>

Before submitting, run the checks bundled in `scripts/`:

- `scripts/checkpatch.pl --strict <patch>` on every patch in the series. Errors must be fixed; warnings must be fixed or justified in the commit message.
- `scripts/check-style.sh` for whitespace and formatting.

Patches that have not been run through `checkpatch.pl` will typically be bounced back.

## Commit message format

Commit messages follow kernel conventions. Your `git log` should blend in with the existing history.

**Subject line**

```
<subsystem>: <lowercase imperative summary>
```

- Subsystem prefixes used in this tree include: `rmr`, `rmr-clt`, `rmr-srv`, `brmr`, `brmr-clt`, `brmr-srv`. Match existing use; introduce a new prefix only when genuinely distinct.
- Imperative mood ("add", "fix", "remove" — not "added" / "fixes").

**Body**

- Blank line after the subject.
- Describe user-visible behaviour changes, any locking or ABI implications, and how you tested.
- Reference related commits by their short hash and subject when relevant.

**Trailers**

Trailers sit at the bottom of the body, separated by a blank line. This project follows the Linux kernel's trailer conventions (`Fixes:`, `Reported-by:`, `Reviewed-by:`, `Tested-by:`, `Co-developed-by:` / `Signed-off-by:` pairs, etc.). For the authoritative rules on which trailers to use and the order they appear in, see the kernel's submitting-patches document:

- <https://docs.kernel.org/process/submitting-patches.html>

Every commit must end with your own `Signed-off-by:` (see [Licensing and sign-off](#licensing-and-sign-off) below).

## Licensing and sign-off

### License

RMR and BRMR are licensed under **GPL-2.0-or-later**. Every new source file must carry an SPDX header on its first line:

```c
// SPDX-License-Identifier: GPL-2.0-or-later
```

Use `/* ... */` for headers where C99 line comments are not appropriate, and the shell/Makefile comment syntax (`# SPDX-License-Identifier: ...`) for build files. Also add an `SPDX-FileCopyrightText` line where the copyright holder is not already obvious from repository-wide conventions.

### Developer Certificate of Origin

Contributions are accepted under the **Developer Certificate of Origin** (DCO), version 1.1. By adding a `Signed-off-by:` line to a commit, you certify the following:

```
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.


Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

### Signing off

Every commit must end with a `Signed-off-by:` trailer. Use a known identity — no anonymous contributions — and make sure the email matches `git config user.email`:

```
Signed-off-by: Random J Developer <random@developer.example.org>
```

The easiest way to add it is with `git commit -s`. Patches without sign-off will not be merged.

## Submitting patches

Submit changes as a **GitHub pull request** against the source-code repository.

1. Fork the repository and create a topic branch off the latest `main`.
2. Make your changes as one or more logical commits. Each commit must:
   - Contain one self-contained change — do not mix unrelated fixes or refactors.
   - Pass `scripts/checkpatch.pl`.
   - End with your `Signed-off-by:` trailer.
3. Push to your fork and open a PR to `develop` branch. The PR description should summarise the series and, where applicable, point to the issue being fixed.
