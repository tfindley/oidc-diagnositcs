# Container Vulnerability Risk Register

**Asset:** `ghcr.io/tfindley/oidc-diagnositcs` (OIDC Diagnostic Tool)
**Scanner:** grype
**Scan date:** 2026-04-10
**Register owner:** Tristan Findley
**Review cycle:** On each container rebuild / at minimum quarterly

## Summary

| Severity   | Total found | Fixed | Accepted | Residual |
| ---------- | ----------: | ----: | -------: | -------: |
| Critical   |           0 |     0 |        0 |        0 |
| High       |           8 |     4 |        4 |        0 |
| Medium     |          25 |     0 |       25 |        0 |
| Low        |          12 |     0 |       12 |        0 |
| Negligible |          50 |     0 |       50 |        0 |

> **Fixed** = ncurses-bin package removed (Dockerfile); `apt-get upgrade` run at build time picks up any Debian-backported patches.
> The 8 High findings map to 2 distinct CVEs. 4 of the 8 findings (all against `ncurses-bin`) are resolved by package removal. The remaining 4 are accepted (see below).

---

## Treatment key

| Code                            | Meaning                                                                    |
| ------------------------------- | -------------------------------------------------------------------------- |
| **FIXED**                       | Vulnerability eliminated — package removed or patched                      |
| **ACCEPTED — NOT APPLICABLE**   | Vulnerable code path is not present or reachable in this application       |
| **ACCEPTED — NO FIX AVAILABLE** | No Debian stable fix exists; vendor/upstream has not released a patch      |
| **ACCEPTED — DISPUTED**         | Upstream maintainer disputes severity or classifies as non-vulnerability   |
| **ACCEPTED — LOCAL ONLY**       | Exploitable only by a local authenticated user; not reachable from network |

---

## High severity

| Risk ID | CVE            | Affected packages                     | Vulnerability summary                                                                                                         | Treatment                   | Justification                                                                                                                                                                                                                                                                                                                                                                                               |
| ------- | -------------- | ------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R-H-01  | CVE-2025-69720 | libncursesw6, libtinfo6, ncurses-base | Stack-based buffer overflow in the `infocmp` command-line tool in ncurses < 6.5-20251213                                      | FIXED (partial — see note)  | `ncurses-bin` (the package containing the `infocmp` binary) has been removed from the image. The remaining three packages are libraries; they do not ship the vulnerable binary. Grype reports them as affected because they share the same version string — this is a scanner false-positive on the library packages. No application code calls `infocmp`.                                                 |
| R-H-02  | CVE-2026-4046  | libc-bin, libc6                       | `iconv()` in glibc ≤ 2.43 may crash via assertion failure when converting IBM1390 or IBM1399 character set inputs             | ACCEPTED — NOT APPLICABLE   | This application processes OIDC tokens (UTF-8/ASCII) and HTML. It does not convert IBM mainframe character sets. The IBM1390/IBM1399 conversion tables are not loaded unless explicitly called. No Debian security fix available at time of scan.                                                                                                                                                           |
| R-H-03  | CVE-2026-4437  | libc-bin, libc6                       | `gethostbyaddr()` in glibc 2.34–2.43 may treat a non-answer DNS section as a valid answer when using the DNS nsswitch backend | ACCEPTED — NO FIX AVAILABLE | The application makes DNS lookups for OIDC provider discovery. Exploitation requires a crafted response from the configured DNS server — i.e., the attacker must already control or MITM the DNS server this container queries. Deployments behind a trusted internal resolver are not at elevated risk. Debian has not released a backport fix for glibc 2.41. To be re-evaluated when a fix is available. |

---

## Medium severity

| Risk ID | CVE            | Affected packages                                                                                | Vulnerability summary                                                                                                                     | Treatment                   | Justification                                                                                                                                                                                                                                                                         |
| ------- | -------------- | ------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R-M-01  | CVE-2025-15366 | python 3.13.13                                                                                   | `imaplib` module allows command injection via newlines in user-controlled input                                                           | ACCEPTED — NOT APPLICABLE   | This application does not use the `imaplib` module. No IMAP client functionality exists. The only available fix is Python 3.15.0a6 (alpha), which is not a stable release.                                                                                                            |
| R-M-02  | CVE-2025-15367 | python 3.13.13                                                                                   | `poplib` module allows command injection via newlines in user-controlled input                                                            | ACCEPTED — NOT APPLICABLE   | This application does not use the `poplib` module. No POP3 client functionality exists. The only available fix is Python 3.15.0a6 (alpha), which is not a stable release.                                                                                                             |
| R-M-03  | CVE-2025-12781 | python 3.13.13                                                                                   | `base64.b64decode()` accepts `+/` characters regardless of `altchars` parameter, potentially causing data integrity issues                | ACCEPTED — NOT APPLICABLE   | This application uses `base64.urlsafe_b64decode()` for JWT decoding only, without a custom `altchars` alphabet. The vulnerability only affects applications that use an alternative base64 alphabet. No security impact in this context.                                              |
| R-M-04  | CVE-2025-6141  | libncursesw6, libtinfo6, ncurses-base, ncurses-bin                                               | Local stack-based buffer overflow in `postprocess_termcap()` in ncurses tinfo parser                                                      | ACCEPTED — LOCAL ONLY       | Requires local user access to trigger via a crafted termcap entry. No Debian fix available at time of scan. The application does not process termcap data; ncurses libraries are present as indirect dependencies of Python. Attack vector is local — not reachable from the network. |
| R-M-05  | CVE-2026-5704  | tar                                                                                              | Crafted tar archive allows hidden file injection bypassing pre-extraction inspection                                                      | ACCEPTED — NOT APPLICABLE   | The application does not extract tar archives. `tar` cannot be removed from the image as it is a hard dependency of `dpkg` (the Debian package manager). It is present in the image layer but is not executed at runtime.                                                             |
| R-M-06  | CVE-2026-4105  | libsystemd0, libudev1                                                                            | systemd-machined `RegisterMachine` D-Bus method has improper access control, allowing local unprivileged user to execute commands as root | ACCEPTED — NOT APPLICABLE   | `systemd` is not running as PID 1 in this container — `gunicorn` is. The `systemd-machined` service is not started and the D-Bus socket is not available. This vulnerability requires an active systemd session manager.                                                              |
| R-M-07  | CVE-2026-29111 | libsystemd0, libudev1                                                                            | Unprivileged IPC API call with spurious data causes systemd to hit an assert and freeze                                                   | ACCEPTED — NOT APPLICABLE   | systemd is not running as PID 1 in this container. The IPC API is not accessible.                                                                                                                                                                                                     |
| R-M-08  | CVE-2026-27456 | bsdutils, libblkid1, liblastlog2-2, libmount1, libsmartcols1, libuuid1, login, mount, util-linux | TOCTOU race in `/usr/bin/mount` SUID binary during loop device setup                                                                      | ACCEPTED — NOT APPLICABLE   | Exploitation requires: (1) a local unprivileged user account on the host, (2) SUID `/usr/bin/mount`, and (3) a crafted `/etc/fstab` entry pointing to an attacker-writable path. None of these conditions exist in a read-only container running a web application.                   |
| R-M-09  | CVE-2026-4438  | libc-bin, libc6                                                                                  | `gethostbyaddr()` in glibc 2.34–2.43 may return an invalid DNS hostname violating the DNS specification                                   | ACCEPTED — NO FIX AVAILABLE | Related to CVE-2026-4437 (same function family). Impact is incorrect hostname data rather than code execution. No Debian backport available. Application validates OIDC issuer claims separately from DNS resolution.                                                                 |
| R-M-10  | CVE-2026-27171 | zlib1g                                                                                           | CPU consumption via `crc32_combine64` / `crc32_combine_gen64` — loop with no termination condition                                        | ACCEPTED — NO FIX AVAILABLE | Requires attacker to supply crafted input to a zlib consumer. The application uses zlib indirectly (via Python compression libraries). No Debian fix available at time of scan. Exploitation would result in DoS (CPU spin), not data compromise.                                     |
| R-M-11  | CVE-2026-4878  | libcap2                                                                                          | Capability handling vulnerability in libcap2                                                                                              | ACCEPTED — NO FIX AVAILABLE | Application runs as a non-root user (`app`) with no special Linux capabilities granted. libcap2 is present as a system library dependency. No Debian fix available at time of scan.                                                                                                   |

---

## Low severity

| Risk ID | CVE            | Affected packages                                                                                | Vulnerability summary                                                                                                         | Treatment                 | Justification                                                                                                                                                              |
| ------- | -------------- | ------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- | ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R-L-01  | CVE-2024-56433 | login.defs, passwd                                                                               | shadow-utils default `/etc/subuid` range (100000–165535) may conflict with locally-administered network UIDs                  | ACCEPTED — NOT APPLICABLE | This application does not manage user accounts, subordinate UIDs, or NFS home directories. The finding applies to multi-user host systems, not web application containers. |
| R-L-02  | CVE-2026-3184  | bsdutils, libblkid1, liblastlog2-2, libmount1, libsmartcols1, libuuid1, login, mount, util-linux | Improper hostname canonicalization in `login(1) -h` can bypass PAM host-based access controls                                 | ACCEPTED — NOT APPLICABLE | The `login` utility with `-h` is not invoked by this application. PAM host-based access controls are not in use. This is a system administration utility vulnerability.    |
| R-L-03  | CVE-2026-34743 | liblzma5                                                                                         | `lzma_index_decoder()` leaves index in bad state after decoding empty index, causing buffer overflow on `lzma_index_append()` | ACCEPTED — NOT APPLICABLE | The application does not use XZ/LZMA decompression. liblzma5 is present as a dependency of other system packages.                                                          |

---

## Negligible severity

The following CVEs are rated negligible by the scanner. All are accepted. Detailed justification is provided for completeness.

| Risk ID | CVE              | Affected packages                                                                                | Reason for acceptance                                                                                                                                                                                             |
| ------- | ---------------- | ------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R-N-01  | CVE-2005-2541    | tar                                                                                              | 20-year-old finding. `tar` does not warn when extracting setuid files. Not exploitable unless an operator manually runs `tar x` on attacker-supplied archives. Application does not use tar.                      |
| R-N-02  | CVE-2007-5686    | login.defs, passwd                                                                               | Insecure `/var/log/btmp` permissions in an unrelated Linux distribution (rPath Linux). Not applicable to Debian.                                                                                                  |
| R-N-03  | CVE-2010-4756    | libc-bin, libc6                                                                                  | glibc glob DoS via crafted expressions. Requires an authenticated session to an FTP server; not applicable to an OIDC web tool. No upstream fix planned.                                                          |
| R-N-04  | CVE-2011-3374    | apt, libapt-pkg7.0                                                                               | `apt-key` GPG validation weakness. `apt-key` is deprecated and not used at runtime.                                                                                                                               |
| R-N-05  | CVE-2011-4116    | perl-base                                                                                        | File::Temp symlink handling. Perl is present as a system dependency; the application does not use Perl.                                                                                                           |
| R-N-06  | CVE-2013-4392    | libsystemd0, libudev1                                                                            | systemd symlink attack on file permissions. Local-only. systemd not running in container.                                                                                                                         |
| R-N-07  | CVE-2017-18018   | coreutils                                                                                        | `chown`/`chgrp` race with `-R -L`. Requires local user running these utilities. Not invoked by the application.                                                                                                   |
| R-N-08  | CVE-2018-20796   | libc-bin, libc6                                                                                  | glibc regex uncontrolled recursion via crafted pattern. Disputed by upstream as non-security. Application does not expose regex processing to untrusted input.                                                    |
| R-N-09  | CVE-2019-1010022 | libc-bin, libc6                                                                                  | glibc stack guard mitigation bypass. Disputed upstream — classified as non-security bug. Requires prior stack buffer overflow to exploit.                                                                         |
| R-N-10  | CVE-2019-1010023 | libc-bin, libc6                                                                                  | glibc libld re-mapping via malicious ELF. Disputed upstream — requires user to run `ldd` on attacker file. Application does not execute user-supplied binaries.                                                   |
| R-N-11  | CVE-2019-1010024 | libc-bin, libc6                                                                                  | glibc ASLR bypass via thread stack cache. Disputed upstream — classified as non-security. Useful only as a second-stage after initial exploitation.                                                               |
| R-N-12  | CVE-2019-1010025 | libc-bin, libc6                                                                                  | glibc ASLR bypass via heap address guessing. Disputed upstream — classified as non-security. Same secondary-exploitation caveat as R-N-11.                                                                        |
| R-N-13  | CVE-2019-9192    | libc-bin, libc6                                                                                  | glibc regex uncontrolled recursion (variant of CVE-2018-20796). Disputed by software maintainer.                                                                                                                  |
| R-N-14  | CVE-2021-45346   | libsqlite3-0                                                                                     | SQLite memory leak via corrupted database file. Disputed by SQLite maintainer — only triggered by a pre-corrupted database, which is not a normal attack surface. Application does not use SQLite.                |
| R-N-15  | CVE-2022-0563    | bsdutils, libblkid1, liblastlog2-2, libmount1, libsmartcols1, libuuid1, login, mount, util-linux | `chfn`/`chsh` INPUTRC environment variable leaks root-owned file content. These SUID utilities are not executed by the application. Affects util-linux < 2.37.4 (fixed upstream; Debian may not have backported). |
| R-N-16  | CVE-2023-31437   | libsystemd0, libudev1                                                                            | systemd sealed log modification. Denied as security vulnerability by systemd vendor. systemd not running in container.                                                                                            |
| R-N-17  | CVE-2023-31438   | libsystemd0, libudev1                                                                            | systemd sealed log truncation. Denied as security vulnerability by systemd vendor. systemd not running in container.                                                                                              |
| R-N-18  | CVE-2023-31439   | libsystemd0, libudev1                                                                            | systemd sealed log content modification. Denied as security vulnerability by systemd vendor. systemd not running in container.                                                                                    |
| R-N-19  | CVE-2025-5278    | coreutils                                                                                        | `sort` utility heap buffer under-read via crafted key format. Application does not invoke `sort`.                                                                                                                 |
| R-N-20  | CVE-2025-14104   | bsdutils, libblkid1, liblastlog2-2, libmount1, libsmartcols1, libuuid1, login, mount, util-linux | util-linux `setpwnam()` heap overread with 256-byte usernames. Login utilities are not invoked by the application.                                                                                                |
| R-N-21  | CVE-2025-70873   | libsqlite3-0                                                                                     | SQLite zipfile extension information disclosure via crafted ZIP file. Application does not use SQLite or process ZIP files.                                                                                       |

---

## Out of scope / will not report

The following categories of findings are excluded from this register:

- Vulnerabilities in packages **not present** in the built image (grype sometimes reports against parent image layers that have been superseded)
- Findings with no CVE ID (informational)
- Findings already resolved at time of register creation (ncurses-bin, CVE-2025-69720 partial)

---

## Review and sign-off

| Field            | Value      |
| ---------------- | ---------- |
| Register version | 1.0        |
| Created          | 2026-04-10 |
| Next review due  | 2026-07-10 |
| Reviewed by      | —          |
| Approved by      | —          |

> This register should be reviewed whenever: (1) a new container scan is performed, (2) a previously accepted CVE receives a fix, or (3) the application's functionality changes in a way that affects the applicability of any acceptance justification above.
