#!/bin/bash
# cd /mnt/d/Git/Amagate
# ./release.sh

COMMIT_HASH=$(git rev-parse --short HEAD)
TIMESTAMP=$(date +'%Y%m%d-%H%M')

read -p "输入版本号 (例如1.0.0, 开发版输入dev): " TAG_NAME
# TAG_NAME=${TAG_NAME:-"dev-${TIMESTAMP}-${COMMIT_HASH}"}
if [[ "$TAG_NAME" == "dev" ]]; then
    TAG_NAME="dev-${TIMESTAMP}-${COMMIT_HASH}"
fi

# 如果TAG_NAME不为空，则更新版本号并提交
if [[ -n "$TAG_NAME" ]]; then
    echo $TAG_NAME >src/Amagate/version
    echo Amagate 版本号已更新为 $TAG_NAME

    printf "\n"
    git add src/Amagate/version
    git commit -m "📃 docs: 更新版本号"

    printf "\n"
    git tag -d $TAG_NAME
    # git push origin :refs/tags/$TAG_NAME

    printf "\n"
    git tag $TAG_NAME
    git push origin main --tags
fi
