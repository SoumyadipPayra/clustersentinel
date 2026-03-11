# HCI Failure Patterns

## NODE_DEGRADATION

**Description**: A single node is progressively failing. The CVM becomes overwhelmed trying to compensate for underlying hardware issues.

**Metric sequence**:
1. `controller_vm_cpu_pct` rises gradually (baseline 20% → 50–80% over 15–45 minutes)
2. `storage_write_iops` drops as the CVM struggles to process writes
3. `storage_write_latency_ms` increases (normal 2–4ms → 20–100ms)
4. `cpu_usage_pct` of the node rises as the hypervisor competes with the struggling CVM

**Causal mechanism**: CVM is retrying storage operations due to disk or memory errors. Each retry consumes additional CPU. Write acknowledgments are delayed, causing IOPS to drop from the guest VM perspective.

**Key discriminator**: Only one node is affected. If multiple nodes show similar patterns simultaneously, suspect CASCADING_FAILURE or STORAGE_REBALANCE.

---

## NOISY_NEIGHBOR

**Description**: A single VM on a shared node monopolizes CPU and IOPS, starving co-located VMs.

**Metric sequence**:
1. `cpu_usage_pct` on the affected node spikes suddenly (to 80–95%)
2. `storage_read_iops` jumps significantly (2,000–5,000 above baseline)
3. `active_vms` count may decrease as the scheduler migrates VMs away
4. Other nodes remain unaffected

**Causal mechanism**: A guest VM experiences a workload spike (batch job, backup, in-memory database rebuild). The hypervisor does not immediately throttle the noisy VM, causing resource starvation for neighbors.

**Key discriminator**: Abrupt onset (seconds, not minutes). Only `cpu_usage_pct` and `storage_read_iops` spike — write metrics and latency remain normal initially.

---

## STORAGE_REBALANCE

**Description**: The cluster's distributed storage system is rebalancing data across nodes — triggered by adding a node, removing a node, or an ADS optimization cycle.

**Metric sequence**:
1. `disk_throughput_mbps` rises on all nodes simultaneously (baseline 100–250 → 400–700 MB/s)
2. `storage_write_latency_ms` increases moderately (4–15ms range) across all nodes
3. `network_rx_mbps` and `network_tx_mbps` both spike as data migrates over the east-west network
4. `replication_lag_ms` increases due to elevated network traffic

**Causal mechanism**: The storage fabric is moving data blocks from overloaded nodes to underutilized ones. This is expected behavior but degrades performance temporarily.

**Key discriminator**: All nodes are affected equally. `disk_throughput_mbps` is the leading indicator. Write latency rises moderately but read latency remains near-normal (reads are served from the local copy).

---

## MEMORY_PRESSURE

**Description**: Gradual memory exhaustion on one or more nodes, causing the CVM to swap and the hypervisor to balloon VM memory.

**Metric sequence**:
1. `memory_usage_pct` climbs slowly (baseline 55% → 85–95% over 20–60 minutes)
2. `controller_vm_mem_pct` also rises as the CVM's working set grows
3. Storage I/O latency increases as the CVM loses its read cache effectiveness
4. `active_vms` may decrease if the scheduler evacuates VMs

**Causal mechanism**: Memory leaks in guest VMs or workload growth exhausts physical RAM. The hypervisor inflates balloon drivers in other VMs to reclaim memory, degrading their performance.

**Key discriminator**: Slow, monotonically increasing memory metrics. No sudden spikes. May affect two nodes if they host related workloads.

---

## NETWORK_SATURATION

**Description**: East-west intra-cluster network is saturated, blocking storage replication and inter-VM communication.

**Metric sequence**:
1. `network_rx_mbps` and `network_tx_mbps` both spike sharply (to near-maximum link capacity, e.g. 900–1000 MB/s on a 10GbE link)
2. `replication_lag_ms` rises sharply (20–200ms)
3. `storage_write_latency_ms` increases because write acknowledgments are blocked waiting for replication
4. Possible `storage_write_iops` drop as the I/O queue backs up

**Causal mechanism**: A large data transfer (backup, replication, live migration of many VMs simultaneously) saturates the shared storage/management network.

**Key discriminator**: Both RX and TX saturate simultaneously. `replication_lag_ms` is the most sensitive early indicator. Compute metrics (CPU, memory) remain normal.

---

## DISK_PRE_FAILURE

**Description**: A physical disk is degrading — sectors are failing, causing the storage controller to retry reads/writes. This can precede a complete disk failure by hours.

**Metric sequence**:
1. `storage_read_latency_ms` begins creeping up (baseline 1.5–2.5ms → 5–30ms over 1–3 hours)
2. `storage_write_latency_ms` follows (baseline 2–3ms → 8–50ms)
3. `storage_read_iops` drops as retries consume IOPS budget
4. `storage_write_iops` also drops
5. `controller_vm_cpu_pct` may rise slightly due to retry processing

**Causal mechanism**: NAND flash cells or HDD sectors are returning correctable errors. Each error requires a read retry, increasing latency. As degradation worsens, error rate accelerates.

**Key discriminator**: Very gradual onset (hours). Both read and write latency rise together. `disk_throughput_mbps` remains normal or drops slightly. Only one node is affected.

---

## CASCADING_FAILURE

**Description**: A node degradation event triggers a storage rebalance on the remaining nodes as the cluster attempts to restore RF2 redundancy.

**Metric sequence** (Phase 1 — Primary node):
1. Same pattern as NODE_DEGRADATION: CVM CPU spike, write IOPS drop, write latency rise
2. The cluster detects the degraded node and begins re-replicating its data

**Metric sequence** (Phase 2 — Secondary nodes, 10–30 minutes after Phase 1):
1. `disk_throughput_mbps` rises on all healthy nodes (replication traffic)
2. `storage_write_latency_ms` increases cluster-wide
3. `replication_lag_ms` spikes as the fabric re-establishes RF2 parity
4. `network_rx_mbps`/`network_tx_mbps` increase on healthy nodes

**Causal mechanism**: When a node degrades, the distributed storage detects under-replicated data blocks. It immediately begins re-replicating these blocks to other nodes, causing a rebalance-like load on healthy nodes.

**Key discriminator**: Time-ordered two-phase pattern. Phase 1 affects one node; Phase 2 spreads to remaining nodes. `replication_lag_ms` is very high throughout Phase 2.
