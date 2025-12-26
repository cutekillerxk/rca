# GitHub上传指南

## 已完成步骤

✅ 1. 创建了 `.gitignore` 文件（排除不必要的文件）
✅ 2. 初始化了Git仓库
✅ 3. 添加了所有文件
✅ 4. 创建了初始提交

## 下一步：上传到GitHub

### 方法1：在GitHub网站创建仓库（推荐）

1. **登录GitHub**，访问 https://github.com/new

2. **创建新仓库**：
   - Repository name: `rca` (或你喜欢的名字)
   - Description: `HDFS集群故障检测与自动处理系统`
   - 选择 Public 或 Private
   - **不要**勾选 "Initialize this repository with a README"（因为本地已有）
   - 点击 "Create repository"

3. **推送代码**（在rca目录下执行）：

```bash
# 添加远程仓库（替换YOUR_USERNAME为你的GitHub用户名）
git remote add origin https://github.com/YOUR_USERNAME/rca.git

# 推送代码
git branch -M main
git push -u origin main
```

### 方法2：使用SSH（如果已配置SSH密钥）

```bash
# 添加远程仓库（替换YOUR_USERNAME为你的GitHub用户名）
git remote add origin git@github.com:YOUR_USERNAME/rca.git

# 推送代码
git branch -M main
git push -u origin main
```

## 如果遇到问题

### 问题1：需要身份验证

如果提示需要登录，可以使用：
- **Personal Access Token**（推荐）
  - 设置 → Developer settings → Personal access tokens → Generate new token
  - 权限选择 `repo`
  - 使用token作为密码

### 问题2：分支名称

如果GitHub默认分支是 `main`，而本地是 `master`：

```bash
# 重命名分支
git branch -M main

# 或保持master
git push -u origin master
```

### 问题3：推送被拒绝

如果远程仓库已有内容：

```bash
# 先拉取
git pull origin main --allow-unrelated-histories

# 解决冲突后推送
git push -u origin main
```

## 验证

推送成功后，访问 `https://github.com/YOUR_USERNAME/rca` 查看你的仓库。

## 后续更新

以后修改代码后：

```bash
git add .
git commit -m "描述你的更改"
git push
```

---

**提示**：如果使用HTTPS推送，可能需要输入GitHub用户名和Personal Access Token。

