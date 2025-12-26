# Docker 环境中操作 Hadoop 集群命令指南

## 问题分析

### 为什么 `hdfs --daemon stop datanode` 可以工作？

1. **`hdfs` 是可执行文件**（二进制或脚本）
2. **位置**：通常在 `$HADOOP_HOME/bin/hdfs`
3. **PATH 配置**：`$HADOOP_HOME/bin` 通常在容器的 PATH 环境变量中
4. **执行方式**：直接执行 `hdfs` 命令，系统会在 PATH 中找到它
5. **单节点操作**：`hdfs --daemon stop datanode` 只在当前容器内执行，不需要 SSH

### 为什么 `stop-dfs.sh` 不能直接工作？

1. **`stop-dfs.sh` 是 shell 脚本**
2. **位置**：通常在 `$HADOOP_HOME/sbin/stop-dfs.sh`
3. **PATH 配置**：`$HADOOP_HOME/sbin` 通常**不在** PATH 环境变量中
4. **执行方式**：直接执行 `stop-dfs.sh`，系统在 PATH 中找不到
5. **集群级操作**：`stop-dfs.sh` 使用 `--workers` 参数，需要通过 SSH 连接到所有节点
6. **SSH 依赖**：在 Docker 容器环境中，容器之间**没有配置 SSH**，所以会失败

### 关键区别

**`stop-dfs.sh` 脚本的工作原理：**
```bash
# stop-dfs.sh 内部使用 --workers 参数
hdfs --workers --daemon stop datanode
```
- `--workers` 参数会尝试通过 SSH 连接到配置的所有 worker 节点
- 需要容器之间有 SSH 配置和无密码登录
- 在 Docker 环境中，容器之间通常没有配置 SSH

**`hdfs --daemon` 命令的工作原理：**
```bash
hdfs --daemon stop datanode
```
- 直接在当前容器内执行，不需要 SSH
- 只操作当前容器内的守护进程
- 适合 Docker 容器环境

## Hadoop 目录结构

```
$HADOOP_HOME/  (通常是 /opt/hadoop-3.2.1)
├── bin/          # 用户命令（在 PATH 中）
│   ├── hdfs
│   ├── hadoop
│   └── ...
└── sbin/         # 管理员脚本（通常不在 PATH 中）
    ├── start-dfs.sh
    ├── stop-dfs.sh
    ├── start-all.sh
    ├── stop-all.sh
    └── ...
```

- **`bin/` 目录在 PATH 中**，所以 `hdfs`、`hadoop` 可以直接执行
- **`sbin/` 目录不在 PATH 中**，所以 `stop-dfs.sh` 需要完整路径
- **`.sh` 脚本使用 `--workers`**，需要 SSH 连接，不适合 Docker 环境

## 宿主机命令行操作 Hadoop 集群

### 1. 使用 `hdfs --daemon` 命令（推荐，适合 Docker 环境）

`hdfs --daemon` 支持的操作：
- `start` - 启动守护进程
- `stop` - 停止守护进程
- `status` - 查看守护进程状态

支持的守护进程类型：
- `namenode` - NameNode
- `datanode` - DataNode
- `secondarynamenode` - SecondaryNameNode（CheckpointNode）

#### 命令格式：
```bash
docker exec <container> hdfs --daemon <start|stop|status> <daemon_type>
```

#### 实际示例：

**单节点操作：**
```bash
# 停止单个 DataNode
docker exec datanode1 hdfs --daemon stop datanode

# 启动单个 NameNode
docker exec namenode hdfs --daemon start namenode
```

**集群级操作（逐个容器执行）：**
```bash
# 停止整个集群（需要逐个容器执行）
docker exec namenode hdfs --daemon stop namenode
docker exec datanode1 hdfs --daemon stop datanode
docker exec datanode2 hdfs --daemon stop datanode
docker exec datanode3 hdfs --daemon stop datanode
docker exec checkpointnode hdfs --daemon stop secondarynamenode
```

### 2. 使用脚本命令（不推荐在 Docker 环境使用）

**为什么 `.sh` 脚本在 Docker 环境中不工作：**
- `stop-dfs.sh` 使用 `--workers` 参数，需要通过 SSH 连接其他节点
- Docker 容器之间没有配置 SSH
- 即使使用完整路径，也会因为 SSH 失败而无法正确执行

**如果必须使用脚本（需要配置 SSH）：**
```bash
# 需要先配置容器之间的 SSH 无密码登录
docker exec namenode /opt/hadoop-3.2.1/sbin/stop-dfs.sh
```

## 命令格式对应关系

| 操作类型 | 推荐命令格式 | 说明 |
|---------|------------|------|
| 单节点停止 | `docker exec datanode1 hdfs --daemon stop datanode` | 直接在当前容器执行 |
| 单节点启动 | `docker exec datanode1 hdfs --daemon start datanode` | 直接在当前容器执行 |
| 集群停止 | 逐个容器执行 `hdfs --daemon stop` | 不使用 stop-dfs.sh（需要 SSH） |
| 集群启动 | 逐个容器执行 `hdfs --daemon start` | 不使用 start-dfs.sh（需要 SSH） |

## 总结对比

| 操作方式 | 命令格式 | 优点 | 缺点 | Docker 环境适用性 |
|---------|---------|------|------|-----------------|
| `hdfs --daemon` | `hdfs --daemon <action> <daemon>` | 简单，在 PATH 中，单节点操作，不需要 SSH | 需要逐个节点操作 | ✅ 完全适用 |
| `.sh` 脚本 | `$HADOOP_HOME/sbin/<script>` | 可以一键启动/停止整个集群 | 需要完整路径，需要 SSH，sbin 不在 PATH 中 | ❌ 不适用（需要 SSH） |

## 推荐使用方式（Docker 环境）

- **单节点操作**：使用 `hdfs --daemon`（简单直接，推荐）
- **集群级操作**：逐个容器执行 `hdfs --daemon`（不使用 `.sh` 脚本，避免 SSH 依赖）

## 环境变量

在容器中，HADOOP_HOME 通常设置为：
```bash
HADOOP_HOME=/opt/hadoop-3.2.1
```

可以通过以下命令验证：
```bash
docker exec namenode bash -c 'echo $HADOOP_HOME'
```

## 注意事项

1. **`.sh` 脚本在 Docker 环境中不适用**，因为它们需要 SSH 连接
2. **`hdfs` 命令可以直接使用**，因为 `bin` 目录在 PATH 中
3. **集群级操作需要逐个容器执行**，不能依赖 `.sh` 脚本
4. **使用 `bash -c` 执行命令**，确保环境变量正确加载
5. **单引号转义**：如果命令中包含单引号，需要正确转义

## 为什么 stop-dfs.sh 返回码是 0 但实际失败？

从错误信息看：
```
ERROR: Attempting to operate on hdfs namenode as root
ERROR: but there is no HDFS_NAMENODE_USER defined. Aborting operation.
```

虽然脚本执行了，但因为：
1. 缺少用户环境变量（已修复）
2. SSH 连接失败（`ssh: command not found`），无法连接到其他节点
3. 脚本可能部分执行成功（当前节点），但其他节点未执行

所以返回码是 0（脚本本身执行成功），但实际集群操作失败。

## 正确的 Docker 环境操作方式

**集群停止：**
```bash
# 逐个容器执行，不使用 stop-dfs.sh
docker exec namenode hdfs --daemon stop namenode
docker exec datanode1 hdfs --daemon stop datanode
docker exec datanode2 hdfs --daemon stop datanode
docker exec datanode3 hdfs --daemon stop datanode
docker exec checkpointnode hdfs --daemon stop secondarynamenode
```

**集群启动：**
```bash
# 逐个容器执行，不使用 start-dfs.sh
docker exec namenode hdfs --daemon start namenode
docker exec datanode1 hdfs --daemon start datanode
docker exec datanode2 hdfs --daemon start datanode
docker exec datanode3 hdfs --daemon start datanode
docker exec checkpointnode hdfs --daemon start secondarynamenode
```
