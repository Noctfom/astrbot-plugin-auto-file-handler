# AstrBot自动文件处理器插件 - GitHub推送指南

## 📋 准备工作

### 1. 创建GitHub仓库
1. 登录GitHub账号
2. 点击右上角 "+" 号，选择 "New repository"
3. 仓库名称建议: `astrbot-plugin-auto-file-handler`
4. 描述: "AstrBot自动文件处理器插件 - 自动接收、存储和管理用户发送的文件"
5. 选择 "Public" (公开仓库)
6. **不要**初始化README、.gitignore或license
7. 点击 "Create repository"

### 2. 准备本地插件文件
确保你已经有完整的插件文件结构:
```
astrbot_plugin_auto_file_handler/
├── main.py
├── plugin.json
├── _conf_schema.json
└── README.md
```

## 🚀 推送步骤

### 方法一: 命令行推送 (推荐)

#### 1. 初始化本地Git仓库
```bash
# 进入插件目录
cd /path/to/astrbot_plugin_auto_file_handler

# 初始化Git仓库
git init

# 添加所有文件
git add .

# 创建初始提交
git commit -m "Initial commit: Auto File Handler Plugin v1.5.12"
```

#### 2. 连接远程仓库
```bash
# 添加远程仓库 (替换为你的仓库URL)
git remote add origin https://github.com/yourusername/astrbot-plugin-auto-file-handler.git

# 验证远程仓库
git remote -v
```

#### 3. 推送到GitHub
```bash
# 推送到主分支
git push -u origin main
```

> 如果遇到 "main" 分支不存在的错误，先创建分支:
```bash
git branch -M main
git push -u origin main
```

### 方法二: GitHub Desktop (图形界面)

#### 1. 安装GitHub Desktop
- 访问 https://desktop.github.com/ 下载安装

#### 2. 添加本地仓库
1. 打开GitHub Desktop
2. 选择 "Add local repository"
3. 选择插件文件夹路径
4. 点击 "Add Repository"

#### 3. 推送仓库
1. 在左下角输入提交信息: "Initial commit: Auto File Handler Plugin v1.5.12"
2. 点击 "Commit to main"
3. 点击 "Publish repository"
4. 选择公开仓库，点击 "Publish"

## 📝 后续维护

### 添加License文件
```bash
# 创建MIT许可证
echo "MIT License

Copyright (c) $(date +%Y) Your Name

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE." > LICENSE

git add LICENSE
git commit -m "Add MIT License"
git push
```

### 创建Release版本
1. 在GitHub仓库页面点击 "Releases"
2. 点击 "Draft a new release"
3. 标签版本: `v1.5.12`
4. 标题: `Auto File Handler Plugin v1.5.12`
5. 描述: 简要说明此版本的改进
6. 上传压缩包文件: `file_handler_v1.5.12_final.zip`
7. 点击 "Publish release"

## 🎯 最佳实践

### 1. 版本管理
- 遵循语义化版本控制 (Semantic Versioning)
- 格式: `v主版本.次版本.修订版本` (如 v1.5.12)

### 2. 提交信息规范
```
feat: 添加新功能
fix: 修复bug
docs: 更新文档
style: 代码格式调整
refactor: 代码重构
perf: 性能优化
test: 测试相关
chore: 构建过程或辅助工具的变动
```

### 3. README优化建议
- 添加徽章 (build status, license等)
- 包含屏幕截图或GIF演示
- 提供详细的安装和配置说明
- 添加常见问题解答 (FAQ)

## 🔧 故障排除

### 常见问题及解决方案

#### 1. 推送权限错误
```
# 检查远程仓库URL
git remote -v

# 重新设置凭证
git remote set-url origin https://yourusername:token@github.com/yourusername/repo.git
```

#### 2. 文件过大无法推送
```
# 查看大文件
git ls-files --size | sort -n -k 2

# 移除大文件
git rm --cached large_file.zip
echo "large_file.zip" >> .gitignore
```

#### 3. 分支冲突
```
# 拉取远程更改
git pull origin main

# 解决冲突后提交
git add .
git commit -m "Resolve conflicts"
git push
```

## 📚 参考资源

- [GitHub官方文档](https://docs.github.com/)
- [Git教程](https://git-scm.com/book/zh/v2)
- [语义化版本控制](https://semver.org/lang/zh-CN/)
- [开源许可证选择](https://choosealicense.com/)

---

🎉 恭喜！你的插件即将开源分享给全世界的AstrBot用户！
