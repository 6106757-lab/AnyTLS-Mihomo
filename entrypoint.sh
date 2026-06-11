#!/bin/sh
ARCH=$(uname -m)
case "$ARCH" in
  x86_64 | amd64) MIHOMO_ARCH="amd64" ;;
  aarch64 | arm64) MIHOMO_ARCH="arm64" ;;
  *) echo "不支持的系统架构: $ARCH"; exit 1 ;;
esac

# 自动下载并配置最新版 Mihomo 内核
if [ ! -f "/usr/local/bin/mihomo" ]; then
    echo "正在下载 Mihomo 内核..."
    LATEST_VERSION=$(curl -s https://api.github.com/repos/MetaCubeX/mihomo/releases/latest | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
    LATEST_VERSION=${LATEST_VERSION:-"v1.18.9"}
    wget -q -O "/tmp/mihomo.gz" "https://github.com/MetaCubeX/mihomo/releases/download/${LATEST_VERSION}/mihomo-linux-${MIHOMO_ARCH}-${LATEST_VERSION}.gz"
    gunzip -c /tmp/mihomo.gz > /usr/local/bin/mihomo
    chmod +x /usr/local/bin/mihomo
    rm -f /tmp/mihomo.gz
fi

# 初始化自签名证书与默认配置
if [ ! -f "/root/.config/mihomo/config.yaml" ]; then
    echo "创建默认配置与自签名证书..."
    openssl req -x509 -newkey rsa:2048 -keyout /root/.config/mihomo/server.key -out /root/.config/mihomo/server.crt -sha256 -days 3650 -nodes -subj "/CN=anytls"
    cat << 'INNER_EOF' > /root/.config/mihomo/config.yaml
listeners:
- name: anytls-in-1
  type: anytls
  port: 8443
  listen: 0.0.0.0
  users:
    admin: adminpwd
  certificate: /root/.config/mihomo/server.crt
  private-key: /root/.config/mihomo/server.key
  padding-scheme: |
   stop=8
   0=30-30
   1=100-400
   2=400-500,c,500-1000,c,500-1000,c,500-1000,c,500-1000
   3=9-9,500-1000
   4=500-1000
   5=500-1000
   6=500-1000
   7=500-1000
INNER_EOF
fi

# 启动 Web 面板
echo "启动 AnyTLS 可视化管理面板..."
exec python /app/panel.py
