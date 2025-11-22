#!/bin/bash
# AstrBot插件GitHub推送脚本

# 配置变量 (请根据实际情况修改)
REPO_NAME="astrbot-plugin-auto-file-handler"
GITHUB_USERNAME="yourusername"
PLUGIN_DIR="/path/to/astrbot_plugin_auto_file_handler"

echo "🚀 开始推送AstrBot插件到GitHub..."

# 检查插件目录是否存在
if [ ! -d "$PLUGIN_DIR" ]; then
    echo "❌ 错误: 插件目录不存在: $PLUGIN_DIR"
    exit 1
fi

echo "✅ 找到插件目录: $PLUGIN_DIR"

# 进入插件目录
cd "$PLUGIN_DIR"

# 初始化Git仓库 (如果尚未初始化)
if [ ! -d ".git" ]; then
    echo "🔧 初始化Git仓库..."
    git init
fi

# 添加所有文件
echo "➕ 添加文件到Git..."
git add .

# 检查是否有文件需要提交
if ! git diff-index --quiet HEAD --; then
    # 创建提交
    echo "📝 创建提交..."
    git commit -m "Auto File Handler Plugin v1.5.12"
else
    echo "ℹ️  没有文件需要提交"
fi

# 设置远程仓库
echo "🔗 设置远程仓库..."
git remote remove origin 2>/dev/null
git remote add origin "https://github.com/$GITHUB_USERNAME/$REPO_NAME.git"

# 创建主分支并推送
echo "📤 推送到GitHub..."
git branch -M main
git push -u origin main

echo "🎉 推送完成!"

echo ""
echo "下一步建议:"
echo "1. 访问 https://github.com/$GITHUB_USERNAME/$REPO_NAME"
echo "2. 添加LICENSE文件"
echo "3. 创建Release版本"
echo "4. 在README中添加徽章"
