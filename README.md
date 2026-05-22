# DJI Video Recovery Skill for AI Coding Tools

[English](#english) | [中文](#中文)

---

<a id="english"></a>

## English

A recovery skill that enables AI agents (Claude Code, OpenClaw, Codex, etc.) to recover accidentally deleted DJI drone video files from ExFAT SD cards.

### How It Works

DJI drones store MP4 videos with the structure: `ftyp + free + free + mdat + moov`. The `moov` atom (video index/metadata) is written at the **end** of each recording. When files are accidentally deleted or a "cut" operation is interrupted, the `moov` is often lost, making the remaining data unplayable.

This skill uses **FAT chain recovery**:
1. Reads the ExFAT File Allocation Table
2. Follows cluster chains that still exist on disk
3. Reconstructs files in the correct order from scattered clusters
4. Scans for orphaned `moov` atoms and matches them using NAL unit validation

### Why Other Tools Fail

| Tool | Problem |
|------|---------|
| **PhotoRec / foremost** | Read sequential disk blocks. ExFAT fragments files across non-contiguous clusters, so sequential reading mixes data from multiple files. |
| **testdisk undelete** | ExFAT completely removes directory entries on deletion, making traditional undelete impossible. |
| **Raw NAL extraction** | DJI stores VPS/SPS/PPS only in `moov`'s hvcC box, not in the mdat stream. Without moov, frame boundaries are unknown. |

**FAT chain recovery works** because ExFAT's FAT table often survives deletion — the cluster chain data remains intact even though directory entries are gone.

### Features

- Recovers DJI video files (HEVC 4K/1080p, H.264 720p)
- Auto-detects ExFAT filesystem parameters from boot sector
- Reconstructs files from FAT cluster chains (byte-perfect)
- Matches orphaned moov atoms to files missing video indexes
- Batch verification with ffmpeg
- Works on macOS and Linux

### Requirements

- macOS or Linux
- Python 3.8+
- ffmpeg (for verification)
- Root/sudo access for raw disk reading

### Installation

```bash
git clone https://github.com/Iri-Y/dji-video-recovery-skill.git
cd dji-video-recovery-skill
./install.sh
```

### Usage with AI Tools

Tell your AI agent:

> "My DJI drone SD card has deleted videos I need to recover. The SD card is at /Volumes/SD_Card."

The AI will automatically:
1. Detect the SD card and verify ExFAT format
2. Grant read access to the raw disk device
3. Run FAT chain recovery
4. Match moov atoms to incomplete files
5. Verify recovered videos are playable

### Manual Usage

```bash
# Step 1: Grant disk read access
sudo chmod o+r /dev/rdisk4s1

# Step 2: Run recovery
sudo python3 scripts/fat_chain_recover.py /dev/rdisk4s1 ./recovered/

# Step 3: Verify results
python3 scripts/verify_recovery.py ./recovered/
```

### Tested Results

On a 64GB DJI OsmoPocket3 SD card with 583 deleted videos:

| Metric | Result |
|--------|--------|
| Total files recovered | 583 |
| Fully playable | 555 |
| Total data | 43 GB |
| Longest video | 3 min 07 sec |
| Quality loss | None (byte-perfect) |

### Project Structure

```
dji-video-recovery-skill/
├── README.md                    # This file
├── README_CN.md                 # Chinese documentation
├── skill.md                     # AI skill instructions
├── scripts/
│   ├── fat_chain_recover.py     # Core recovery script
│   └── verify_recovery.py       # Batch verification script
└── install.sh                   # Installation helper
```

### License

MIT License

---

<a id="中文"></a>

## 中文

一个面向 AI 编程工具（Claude Code、OpenClaw、Codex 等）的 DJI 无人机误删视频恢复技能。

### 工作原理

DJI 无人机以 `ftyp + free + free + mdat + moov` 结构存储 MP4 视频。`moov` 原子（视频索引/元数据）在每次录制的**最后**才写入。当文件被误删或"剪切"操作被中断时，`moov` 通常会丢失，导致剩余数据无法播放。

本技能使用 **FAT 链恢复法**：
1. 读取 ExFAT 文件分配表（FAT）
2. 跟踪磁盘上仍然存在的集群链
3. 按正确顺序从碎片化的集群中重建文件
4. 扫描孤立的 `moov` 原子，通过 NAL 单元验证进行匹配

### 为什么其他工具会失败

| 工具 | 问题 |
|------|------|
| **PhotoRec / foremost** | 按顺序读取磁盘块。ExFAT 将文件分散到不连续的集群，顺序读取会混合多个文件的数据。 |
| **testdisk 反删除** | ExFAT 在删除时完全移除目录条目，传统反删除无法工作。 |
| **原始 NAL 提取** | DJI 仅在 `moov` 的 hvcC 中存储 VPS/SPS/PPS，不在 mdat 流中。没有 moov 就无法确定帧边界。 |

**FAT 链恢复有效**是因为 ExFAT 的 FAT 表通常在删除后仍然完好——即使目录条目被删除，集群链数据仍然存在。

### 功能特点

- 恢复 DJI 视频文件（HEVC 4K/1080p、H.264 720p）
- 自动从引导扇区检测 ExFAT 文件系统参数
- 从 FAT 集群链重建文件（字节级精确）
- 将孤立的 moov 原子匹配到缺少视频索引的文件
- 使用 ffmpeg 批量验证
- 支持 macOS 和 Linux

### 系统要求

- macOS 或 Linux
- Python 3.8+
- ffmpeg（用于验证）
- 需要 root/sudo 权限读取原始磁盘

### 安装

```bash
git clone https://github.com/YOUR_USERNAME/dji-video-recovery-skill.git
cd dji-video-recovery-skill
./install.sh
```

### 配合 AI 工具使用

告诉你的 AI 助手：

> "我的 DJI 无人机 SD 卡有误删的视频需要恢复。SD 卡在 /Volumes/SD_Card。"

AI 会自动执行：
1. 检测 SD 卡并验证 ExFAT 格式
2. 授予原始磁盘设备的读取权限
3. 运行 FAT 链恢复
4. 将 moov 原子匹配到不完整的文件
5. 验证恢复的视频可以播放

### 手动使用

```bash
# 步骤 1：授予磁盘读取权限
sudo chmod o+r /dev/rdisk4s1

# 步骤 2：运行恢复
sudo python3 scripts/fat_chain_recover.py /dev/rdisk4s1 ./recovered/

# 步骤 3：验证结果
python3 scripts/verify_recovery.py ./recovered/
```

### 测试结果

在 64GB DJI OsmoPocket3 SD 卡上恢复 583 个误删视频：

| 指标 | 结果 |
|------|------|
| 恢复文件总数 | 583 |
| 完全可播放 | 555 |
| 恢复数据量 | 43 GB |
| 最长视频 | 3 分 07 秒 |
| 质量损失 | 无（字节级精确重建） |

### 许可证

MIT License
