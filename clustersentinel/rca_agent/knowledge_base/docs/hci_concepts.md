# HCI Concepts Reference

## What is a Hyperconverged Infrastructure (HCI) Cluster?

A Hyperconverged Infrastructure cluster combines compute, storage, and networking into a single software-defined unit running on commodity hardware nodes. Unlike traditional three-tier architectures, HCI eliminates dedicated storage arrays by pooling the local storage of each node into a shared distributed fabric.

## Node Roles

Each node in an HCI cluster serves dual roles simultaneously:
- **Compute node**: Runs guest virtual machines (VMs) via a hypervisor (VMware ESXi, AHV, Hyper-V)
- **Storage node**: Contributes its local SSDs and HDDs to the cluster-wide distributed storage pool

## Controller VM (CVM)

Every node runs a **Controller VM (CVM)** — a dedicated management VM that handles all storage I/O for that node. The CVM:
- Intercepts all guest VM disk I/O and routes it through the distributed storage fabric
- Manages data replication to peer nodes
- Handles storage tiering (hot SSD tier vs cold HDD tier)
- Coordinates deduplication, compression, and erasure coding

A healthy CVM consumes 15–25% CPU and 28–40% memory. Elevated CVM CPU (>50%) is an early warning sign of storage stress, rebalancing operations, or node degradation.

## Distributed Storage Fabric

Data written by any VM is immediately replicated across multiple nodes. The replication factor (RF) determines redundancy:
- **RF2**: 2 copies of all data (tolerate 1 node failure)
- **RF3**: 3 copies of all data (tolerate 2 node failures)

Data is distributed across nodes using a consistent hashing scheme. Each I/O write must complete on the required number of replicas before being acknowledged to the guest VM.

## Storage Tiering

HCI clusters implement intelligent tiering:
- **Hot tier (SSD/NVMe)**: Frequently accessed ("hot") data resides on fast flash storage
- **Cold tier (HDD)**: Infrequently accessed data is downtiered to spinning disks

The storage controller continuously monitors access patterns and moves data between tiers automatically. Unexpected spikes in `disk_throughput_mbps` can indicate active tiering migrations.

## Replication Lag

`replication_lag_ms` measures the delay between a write being acknowledged on the primary node and that write being confirmed on replica nodes. Normal values are <5ms. Values above 20ms indicate network congestion, an overloaded CVM, or a struggling peer node.

## ADS-Style Dynamic Scheduling

Advanced Data Services (ADS) continuously rebalances VM placement and storage distribution across nodes to optimize:
- CPU and memory utilization
- Storage hotspots and skew
- Network bandwidth consumption

A storage rebalance event manifests as sustained high `disk_throughput_mbps` (200–500 MB/s) combined with elevated write latency across all nodes simultaneously.
