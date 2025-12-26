明白了，你现在要进入 **Hadoop 集群配置阶段**，也就是在每个容器内编辑 Hadoop 的配置文件，让 NameNode 和 DataNode 能互相识别并正常工作。下面我给你一个 **逐步操作指南**，解释每个配置文件的作用和如何设置。

---

# **前提**

* 你已经在每个容器安装了 **Java + SSH + Hadoop**。
* 自定义网络 `hadoop-net` 已创建，并且容器都在这个网络里。
* 容器名称：

  * `hadoop-namenode`
  * `hadoop-datanode1`
  * `hadoop-datanode2`

---

# **1️⃣ core-site.xml**

* **位置**：`$HADOOP_HOME/etc/hadoop/core-site.xml`
* **作用**：设置 Hadoop 的核心配置，包括 HDFS 的地址。
* **操作**（NameNode 容器内）：

```bash
cd $HADOOP_HOME/etc/hadoop
vim core-site.xml
```

* **示例配置**：

```xml
<configuration>
  <property>
    <name>fs.defaultFS</name>
    <value>hdfs://namenode:9000</value>
  </property>
</configuration>


```

<configuration>

  <!-- Hadoop 默认 NameNode 地址（端口改为 9000 也可以） -->
  <property>
    <name>fs.defaultFS</name>
    <value>hdfs://namenode:9000</value>
  </property>

  <!-- NameNode RPC 地址，必须监听 0.0.0.0，否则容器外无法访问 -->
  <property>
    <name>dfs.namenode.rpc-address</name>
    <value>0.0.0.0:9000</value>
  </property>

  <!-- NameNode WebUI 地址：9870（必须监听 0.0.0.0） -->
  <property>
    <name>dfs.namenode.http-address</name>
    <value>0.0.0.0:9870</value>
  </property>

  <!-- HDFS 静态用户（避免权限问题） -->
  <property>
    <name>hadoop.http.staticuser.user</name>
    <value>root</value>
  </property>

</configuration>


* **说明**：

  * `fs.defaultFS`：HDFS 的默认文件系统 URI
  * `namenode`：容器名，也就是 NameNode 的 hostname（Docker 网络解析）
  * `9000`：HDFS RPC 端口

---

# **2️⃣ hdfs-site.xml**

* **作用**：设置 HDFS 相关目录、DataNode 存储等
* **操作**：

```bash
vim hdfs-site.xml
```

* **示例配置**：

```xml
<configuration>
  <property>
    <name>dfs.replication</name>
    <value>2</value>
  </property>

  <property>
    <name>dfs.namenode.name.dir</name>
    <value>/usr/local/hadoop/hdfs/namenode</value>
  </property>

  <property>
    <name>dfs.datanode.data.dir</name>
    <value>/usr/local/hadoop/hdfs/datanode</value>
  </property>
</configuration>
```

* **说明**：

  * `dfs.replication`：HDFS 副本数量（根据 DataNode 数量设置，一般 ≤ DataNode 数）
  * `dfs.namenode.name.dir`：NameNode 存储目录
  * `dfs.datanode.data.dir`：DataNode 存储目录

> 提示：在每个节点容器里要保证这些目录存在

```bash
mkdir -p /usr/local/hadoop/hdfs/namenode
mkdir -p /usr/local/hadoop/hdfs/datanode
```

---

# **3️⃣ mapred-site.xml**

* **作用**：MapReduce 配置
* **操作**：

```bash
cp mapred-site.xml.template mapred-site.xml
vim mapred-site.xml
```

* **示例配置**：

```xml
<configuration>
  <property>
    <name>mapreduce.framework.name</name>
    <value>yarn</value>
  </property>
</configuration>
```

* **说明**：

  * `mapreduce.framework.name`：指定使用 YARN 作为资源管理框架

---

# **4️⃣ yarn-site.xml**

* **作用**：YARN 配置，包括 ResourceManager 和 NodeManager
* **操作**：

```bash
vim yarn-site.xml
```

* **示例配置**：

```xml
<configuration>
  <property>
    <name>yarn.resourcemanager.hostname</name>
    <value>namenode</value>
  </property>
  <property>
    <name>yarn.nodemanager.aux-services</name>
    <value>mapreduce_shuffle</value>
  </property>
</configuration>
```

* **说明**：

  * `yarn.resourcemanager.hostname`：指定 ResourceManager 主机，这里我们使用 NameNode 容器
  * `mapreduce_shuffle`：YARN MapReduce shuffle 服务

---

# **5️⃣ workers 文件**

* **位置**：`$HADOOP_HOME/etc/hadoop/workers`
* **作用**：列出所有 DataNode 节点
* **操作**：

```bash
vim workers
```

* **内容示例**：

```
namenode
datanode1
datanode2
```

> 注意：填写容器 hostname，Hadoop 启动 DFS/Datanode 时会读取 workers 文件。

---

# **操作总结**

1. **NameNode 容器**：

   * 编辑：`core-site.xml`, `hdfs-site.xml`, `mapred-site.xml`, `yarn-site.xml`
   * 编辑 workers 文件，列出 DataNode 容器名
   * 创建 HDFS 目录：

     ```bash
     mkdir -p /usr/local/hadoop/hdfs/namenode
     mkdir -p /usr/local/hadoop/hdfs/datanode
     ```

2. **DataNode 容器**：

   * 编辑：`core-site.xml`, `hdfs-site.xml`, `mapred-site.xml`, `yarn-site.xml`（同 NameNode，除 `dfs.namenode.name.dir` 可不用创建）
   * 创建 DataNode 存储目录：

     ```bash
     mkdir -p /usr/local/hadoop/hdfs/datanode
     ```

3. **保持网络通信正常**：

   * NameNode 可以通过 `namenode` 容器名访问
   * DataNode 可以通过 `namenode` 容器名访问 NameNode

---

💡 **提示**：

* 编辑配置时，所有容器的 `$HADOOP_HOME` 路径要一致
* 配置文件中使用容器名作为 hostname，这样 Docker 网络可以解析
* 完成配置后，可以执行 **NameNode 格式化** 并启动 HDFS

---

如果你愿意，我可以帮你写一个 **完整的示例配置文件集（core-site、hdfs-site、yarn-site、mapred-site、workers）**，你直接复制到容器中就能用，保证 NameNode + 2 个 DataNode 的小集群可用。

你希望我直接给这个完整配置吗？
PermitRootLogin yes
PasswordAuthentication yes
service ssh restart
