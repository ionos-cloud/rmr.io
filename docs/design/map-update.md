<!-- SPDX-FileCopyrightText: 2026 IONOS SE -->
<!-- SPDX-License-Identifier: GPL-2.0-or-later -->

# Map Update
Network disruption, disk failure, or a crash on a storage node causes IO to fail on the affected node (See [Failure recovery](failure-recovery.md)). Once the failure is resolved, the node must resynchronize before it can service IOs again. First, the recovering node fetches an updated dirty map from a NORMAL storage server — this mechanism is called map update. After the map update completes, IOs can be serviced again. RMR-server syncs the dirty data both while servicing IOs and through the sync thread.

