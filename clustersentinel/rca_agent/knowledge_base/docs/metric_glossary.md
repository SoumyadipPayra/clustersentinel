# Metric Glossary

All metrics below are sampled per node every 30 seconds (configurable).

---

## Node-Level Metrics

### cpu_usage_pct
- **Measures**: Total CPU utilization across all physical cores on the node (hypervisor + VMs + CVM)
- **Normal range**: 20–50%
- **Warning threshold**: >70%
- **Critical threshold**: >90%
- **High means**: Compute-intensive workloads, a noisy neighbor VM, or CVM overhead from storage stress
- **Low means**: Node is underutilized or VMs have been migrated away

### memory_usage_pct
- **Measures**: Physical RAM consumed by all running VMs plus hypervisor overhead
- **Normal range**: 45–65%
- **Warning threshold**: >80%
- **Critical threshold**: >92%
- **High means**: Memory pressure — expect balloon driver activation, VM page swapping, and CVM cache eviction
- **Low means**: Node is underprovisioned relative to its capacity

### storage_read_iops
- **Measures**: Read I/O operations per second served by this node's storage (local + distributed)
- **Normal range**: 800–4,500 IOPS
- **Warning threshold**: <500 or >8,000 IOPS (context-dependent)
- **Critical threshold**: <200 IOPS (severe degradation)
- **High means**: Read-intensive workloads, a noisy neighbor, or active storage rebalance
- **Low means**: Disk degradation, I/O throttling, or very light workload

### storage_write_iops
- **Measures**: Write I/O operations per second acknowledged to guest VMs
- **Normal range**: 400–2,200 IOPS
- **Warning threshold**: <300 or >5,000 IOPS
- **Critical threshold**: <100 IOPS
- **High means**: Write-intensive workloads, bulk data ingestion
- **Low means**: Disk pre-failure (retries consuming IOPS budget), CVM overload, or write queue backpressure

### storage_read_latency_ms
- **Measures**: Average time to complete a storage read operation (from guest VM perspective)
- **Normal range**: 1–3 ms (SSD-tier)
- **Warning threshold**: >5 ms
- **Critical threshold**: >20 ms
- **High means**: SSD degradation, cache miss storm causing HDD reads, or CVM I/O queue backup
- **Low means**: Healthy, cache-warm workload

### storage_write_latency_ms
- **Measures**: Average time for a write to be acknowledged (requires replication to complete)
- **Normal range**: 2–4 ms
- **Warning threshold**: >8 ms
- **Critical threshold**: >30 ms
- **High means**: Replication lag (network issue), CVM overload, disk degradation, or storage rebalance
- **Low means**: Healthy write path

### network_rx_mbps
- **Measures**: Inbound network throughput on the node's storage/management NIC
- **Normal range**: 100–500 MB/s
- **Warning threshold**: >750 MB/s (on 10GbE = 1,000 MB/s max)
- **Critical threshold**: >900 MB/s (near saturation)
- **High means**: Active rebalance data migration, live VM migration, backup traffic
- **Low means**: Light east-west traffic

### network_tx_mbps
- **Measures**: Outbound network throughput from this node
- **Normal range**: 80–450 MB/s
- **Warning threshold**: >700 MB/s
- **Critical threshold**: >900 MB/s
- **High means**: Same causes as network_rx_mbps; simultaneous RX+TX spike = network saturation event
- **Low means**: Light outbound replication traffic

### controller_vm_cpu_pct
- **Measures**: CPU usage of the Controller VM (CVM) managing this node's storage
- **Normal range**: 12–25%
- **Warning threshold**: >40%
- **Critical threshold**: >65%
- **High means**: High write workload requiring CVM processing, disk retries, rebalance coordination, or node degradation
- **Low means**: Light storage activity

### controller_vm_mem_pct
- **Measures**: Memory utilization of the CVM
- **Normal range**: 28–40%
- **Warning threshold**: >55%
- **Critical threshold**: >70%
- **High means**: Large read cache being actively used, or CVM is under memory pressure from the hypervisor
- **Low means**: Light workload with minimal caching

### disk_throughput_mbps
- **Measures**: Raw bytes per second read/written to local physical disks (before caching)
- **Normal range**: 80–300 MB/s
- **Warning threshold**: >450 MB/s
- **Critical threshold**: >650 MB/s (sustained)
- **High means**: Active data tiering migration, storage rebalance, or bulk sequential I/O
- **Low means**: Workload is cache-resident; no physical disk I/O required

### active_vms
- **Measures**: Number of powered-on VMs currently assigned to this node
- **Normal range**: 6–24 VMs (depends on cluster size)
- **Warning threshold**: >35 VMs (overcommitted)
- **Critical threshold**: Sudden drop >5 VMs (unexpected VM evacuation)
- **High means**: High VM density; monitor cpu_usage_pct and memory_usage_pct carefully
- **Low means**: VMs have been evacuated (scheduled or due to node health score drop)

---

## Cluster-Level Metrics

### total_cpu_usage_pct
- **Measures**: Mean CPU utilization across all nodes
- **Normal range**: 20–55%
- **Warning threshold**: >70%

### total_memory_usage_pct
- **Measures**: Mean memory utilization across all nodes
- **Normal range**: 45–65%
- **Warning threshold**: >80%

### storage_utilization_pct
- **Measures**: Fraction of total cluster IOPS capacity in use
- **Normal range**: 15–60%
- **Warning threshold**: >75%

### avg_read_latency_ms / avg_write_latency_ms
- **Measures**: Cluster-wide average read/write latency
- See per-node thresholds; cluster averages mask per-node hotspots

### degraded_nodes
- **Measures**: Count of nodes with cpu_usage_pct or memory_usage_pct above 70%
- **Normal**: 0
- **Warning**: ≥1 (investigate immediately)
- **Critical**: ≥2 (cluster redundancy at risk)

### replication_lag_ms
- **Measures**: Estimated delay for writes to propagate to all replicas (computed from node write latency variance)
- **Normal range**: 0–5 ms
- **Warning threshold**: >20 ms
- **Critical threshold**: >100 ms
- **High means**: Network saturation, CVM overload, or a rebalance event is in progress
