docker start hadoop-namenode
docker exec -it hadoop-namenode /bin/bash
root 12346
hadoop hadoop
ps -ef | grep sshd
service ssh start
vim $HADOOP_HOME/etc/hadoop/hadoop-env.sh
hdfs dfsadmin -report
service ssh start
docker-compose down -v
docker volume rm rca_hadoop_namenode rca_hadoop_datanode1 rca_hadoop_datanode2 rca_hadoop_datanode3 rca_hadoop_checkpoint
docker volume rm hadoop_namenode hadoop_datanode1 hadoop_datanode2