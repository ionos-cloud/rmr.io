<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# RMR and BRMR Documentation
```{toctree}
:maxdepth: 1
:caption: Contents
guide/index
architecture/index
design/index
subsystems/index
misc/index
```


```{warning}
RMR and BRMR are under active development and are **not ready for production use**. The codebase contains known bugs, incomplete features, and areas that require improvement, correction, or refactoring — expect instability and potential data loss. APIs and interfaces may change without notice.
```

RMR (Reliable Multicast over RTRS) is a kernel module that provides active-active block-level replication over RDMA. It guarantees delivery of IO to a group of storage nodes and handles resynchronization of data directly between storage nodes without involving the compute client.

BRMR (Block device over RMR) sits on top of RMR and exposes a standard Linux block device (`/dev/brmrX`) backed by an RMR pool. Together, RMR and BRMR provide a single-hop replication and resynchronization solution for RDMA-connected storage clusters.

## Project links

- Source code: <https://github.com/ionos-cloud/RMR>
- Issues: <https://github.com/ionos-cloud/RMR/issues>
- Roadmap: <https://github.com/ionos-cloud/RMR/issues>

