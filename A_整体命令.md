明白了，你希望 **一步步学习如何在 Windows11 + Docker Desktop 环境下，创建多容器 Hadoop 集群，并打包成可移植镜像**，不仅是执行操作，还要理解每一步的原因。我给你整理一个 **详细行动方案+命令+原因解释**，尽量兼顾教学和实践。

---

## **一、准备环境**

1. **确保 Docker Desktop 已安装并运行**

   * Windows 11 支持 Docker Desktop 并可启用 WSL2 或 Hyper-V。
   * 打开 PowerShell 或 CMD，执行：

     ```bash
     docker version
     ```

     ✅ 如果能显示客户端和服务器版本，说明 Docker 正常运行。

2. **切换到 Linux 容器模式**

   * Docker Desktop 右下角设置选择 **Switch to Linux Containers**。

---

## **二、创建基础 Linux 容器（虚拟机）**

### 1️⃣ 拉取基础 Linux 镜像

* **命令行位置**：PowerShell / CMD
* **命令**：

  ```bash
  docker pull ubuntu:22.04
  ```
* **原因**：拉取官方 Ubuntu 镜像，为后续安装 Hadoop 提供基础 Linux 环境。

---
1. **创建自定义 Docker 网络**（宿主机执行）

   ```bash
   docker network create hadoop-net
   ```

   * **原因**：容器需要互相通信，Docker 自定义网络比默认桥接网络更可控，便于节点间用容器名通信。

### 2️⃣ 创建第一个容器（当作 NameNode）

* **命令**：

  ```bash
  docker run -it --name hadoop-namenode --hostname namenode --network hadoop-net ubuntu:22.04 /bin/bash
  docker run -it --name hadoop-datanode1 --hostname datanode1 --network hadoop-net ubuntu:22.04 /bin/bash
  docker run -it --name hadoop-datanode2 --hostname datanode2 --network hadoop-net ubuntu:22.04 /bin/bash
  ```
* **解释**：

  * `-it`：交互式终端，方便配置。
  * `--name`：容器名字，便于管理。
  * `--hostname`：容器内部主机名，Hadoop 配置需要。
  * `/bin/bash`：进入容器 shell。
* **原因**：创建一个独立的 Linux 容器，可以像虚拟机一样操作。

---

### 3️⃣ 安装必要组件（容器内执行）

* **组件**：

  * OpenJDK（Hadoop 依赖）
  * SSH（Hadoop 节点间通信）
  * Vim、curl 等工具
* **命令（容器内）**：

  ```bash
# 替换 archive.ubuntu.com 为清华源
sed -i 's@archive.ubuntu.com@mirrors.tuna.tsinghua.edu.cn@g' /etc/apt/sources.list

# 替换 security.ubuntu.com 为清华源
sed -i 's@security.ubuntu.com@mirrors.tuna.tsinghua.edu.cn@g' /etc/apt/sources.list

echo "nameserver 8.8.8.8" > /etc/resolv.conf
echo "nameserver 223.5.5.5" >> /etc/resolv.conf
apt-get update
apt-get install -y openjdk-11-jdk ssh vim curl net-tools iputils-ping sudo
  ```
* **原因**：Hadoop 需要 Java；SSH 用于集群节点通信；其他工具方便调试和配置。

---



---

### 5️⃣ 安装 Hadoop（容器内）

* **命令（容器内）**：

  ```bash
  curl -O https://downloads.apache.org/hadoop/common/hadoop-3.3.6/hadoop-3.3.6.tar.gz
  tar -xzvf hadoop-3.3.6.tar.gz -C /usr/local/
  mv /usr/local/hadoop-3.3.6 /usr/local/hadoop
  ```

创建hadoop用户：
useradd -m -s /bin/bash hadoop
修改密码 passwd hadoop

* **配置环境变量（容器内 /root/.bashrc）**：
su hadoop
vim ~/.bashrc

```bash
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export HADOOP_HOME=/usr/local/hadoop
export PATH=$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin
```

  * 然后执行：

    ```bash
    source ~/.bashrc
    ```
* **原因**：Hadoop 安装目录和环境变量配置，保证可以在命令行直接使用 Hadoop 命令。
vim hadoop-env.sh添加：
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export HADOOP_HOME=/usr/local/hadoop
export PATH=$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin

### 4️⃣ 配置 SSH 无密码登录（集群必备）

* **命令（容器内）**：

  ```bash
  ssh-keygen -t rsa -P "" -f ~/.ssh/id_rsa
  cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
  chmod 600 ~/.ssh/authorized_keys
  sudo service ssh start

  ssh-copy-id hadoop@datanode1
  ```
* **原因**：Hadoop 集群节点之间通过 SSH 通信，需要免密码登录。
---

## **四、Hadoop 集群配置**

1. **编辑配置文件**（容器内）：

   * core-site.xml
   * hdfs-site.xml
   * mapred-site.xml
   * yarn-site.xml
   * 主要配置 NameNode 地址、DataNode 列表、HDFS 数据目录。

2. **格式化 HDFS**（NameNode 容器内）

   ```bash
   hdfs namenode -format
   ```

3. **启动集群**（容器内）

   * NameNode：

     ```bash
     start-dfs.sh
     start-yarn.sh
     ```
   * DataNode 会自动注册。

4. **测试集群**：

   ```bash
   hdfs dfs -mkdir /test
   hdfs dfs -put localfile /test/
   hdfs dfs -ls /test
   ```

---

## **五、打包自定义镜像**

1. **提交容器为镜像**（宿主机执行）

   ```bash
   docker commit hadoop-namenode myhadoop:namenode
   docker commit hadoop-datanode1 myhadoop:datanode
   docker commit hadoop-datanode2 myhadoop:datanode
   ```

   * **原因**：保存当前容器状态（安装 Hadoop、配置 SSH、环境变量等）为镜像。

2. **上传到仓库**

   ```bash
   docker tag myhadoop-datanode2:v1 cutekiller/myhadoop-datanode2:v1

   docker push cutekiller/myhadoop-datanode2:v1

   ```

3. **在其他机器一键部署**

   * 拉取镜像：

     ```bash
     docker pull cutekiller/myhadoop-namenode:v1

     ```
   * 创建 Docker 网络：

     ```bash
     docker network create hadoop-net
     ```
   * 启动容器：

     ```bash
     docker run -dit --name namenode --hostname namenode --network hadoop-net myhadoop:namenode
     docker run -dit --name datanode1 --hostname datanode1 --network hadoop-net myhadoop:datanode
     docker run -dit --name datanode2 --hostname datanode2 --network hadoop-net myhadoop:datanode
     ```
   * 进入容器启动 Hadoop 服务。

---

## **六、学习重点**

1. **Docker 网络**：保证集群节点互联。
2. **容器内多服务管理**：使用 supervisord 或 systemd。
3. **数据持久化**：HDFS、日志挂载宿主机卷。
4. **镜像打包和复用**：`docker commit` 保存当前容器状态，上传仓库可实现“一键部署”。

---

💡 **建议提升学习效率**：

* **先手动在一个容器中搭建 Hadoop**，熟悉配置。
* **再写 Dockerfile + Docker Compose 自动化多容器集群**。
* 这样不仅能操作，还能理解每一步原因和原理。

---

如果你愿意，我可以帮你直接写一个 **完整的 Dockerfile + supervisord 配置 + Docker Compose 文件示例**，用于 Windows Docker Desktop 环境，一键启动多容器 Hadoop 集群，支持多服务。

你希望我直接写吗？
