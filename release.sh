#!/bin/bash
# cd /mnt/d/Astra/Git/Amagate


COMMIT_HASH=$(git rev-parse --short HEAD)
TIMESTAMP=$(date +'%Y%m%d-%H%M')

read -p "输入版本号 (例如1.0.0, 开发版直接回车): " TAG_NAME
TAG_NAME=${TAG_NAME:-"dev-${TIMESTAMP}-${COMMIT_HASH}"}

echo $TAG_NAME > src/Amagate/version

git tag %TAG_NAME%
git push origin %TAG_NAME%
