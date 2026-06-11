# AnyTLS Mihomo Web Panel

一个基于 **Mihomo（Clash Meta）内核** 的 **AnyTLS 可视化管理面板**。

通过简洁直观的 Web 界面，即可完成 AnyTLS 服务端配置、用户管理、证书维护以及客户端配置生成，无需手动编辑 YAML 文件。

---

## ✨ 功能特性

### 🖥️ Web 可视化管理

* 基于浏览器完成所有配置操作；
* 无需命令行修改配置文件；
* 配置变更后自动应用。

### 👥 多用户账号管理

* 支持创建、编辑、删除多个用户；
* 独立管理用户名与密码；
* 支持快速生成对应客户端配置。

### 🔐 SSL 证书管理

支持两种证书模式：

#### 自签名证书

* 基于自定义域名一键生成证书；
* 支持重新签发；
* 默认有效期 **10 年**。

#### CA 证书

* 支持上传真实域名证书；
* 自动读取证书信息；
* 实时显示证书生效时间与到期时间。

### ⚙️ 客户端参数配置

支持通过面板自定义以下参数：

* SNI 伪装域名；
* uTLS 浏览器指纹：

  * Chrome
  * Firefox
  * Safari
  * Edge
  * Random 等；
* 是否跳过证书验证。

### 📈 Padding 混淆策略

支持自定义 `padding-scheme` 规则，用于降低流量长度特征带来的识别风险。

### 🔗 节点分享与订阅

* 一键生成 `anytls://` 导入链接；
* 自动生成二维码；
* 提供动态订阅接口；
* 支持客户端自动更新节点。

兼容客户端包括：

* NekoBox
* v2rayN
* Shadowrocket
* 其他支持 AnyTLS 订阅的客户端

---

# 🚀 快速开始

## 环境要求

请确保服务器已安装：

* Docker
* Docker Compose

Ubuntu 安装 Docker：

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
```

---

## 使用 Docker Compose（推荐）

### 1. 创建工作目录

```bash
mkdir -p /opt/anytls-panel
cd /opt/anytls-panel
```

### 2. 创建 `docker-compose.yml`

```yaml
services:
  anytls-panel:
    image: ghcr.io/6106757-lab/anytls-mihomo:latest
    container_name: anytls-mihomo-panel
    restart: always
    network_mode: host

    volumes:
      - ./data:/root/.config/mihomo
```

### 3. 启动服务

```bash
docker compose up -d
```

---

## 使用 Docker Run

```bash
docker run -d \
  --name anytls-mihomo-panel \
  --restart always \
  --network host \
  -v /opt/anytls-panel/data:/root/.config/mihomo \
  ghcr.io/6106757-lab/anytls-mihomo:latest
```

---

# 📖 使用说明

## 访问面板

默认地址：

```text
http://服务器IP:8888
```

---

## 默认登录信息

默认密码：

```text
admin
```

首次登录后，请立即修改密码。

路径：

```text
安全设置 → 修改面板密码
```

---

## 修改监听端口

AnyTLS 默认监听：

```text
8443
```

若端口已被占用，可在面板中修改为其他端口，例如：

```text
8444
4433
9443
```

保存后即可自动应用。

---

# 📲 客户端导入

## 导入单个节点

进入：

```text
用户管理 → 生成连接
```

即可获得：

* anytls:// 导入链接；
* 对应二维码。

客户端扫码或粘贴即可使用。

---

## 动态订阅

面板会自动生成订阅地址：

```text
http://服务器IP:8888/sub
```

将其添加至客户端订阅管理中。

当服务端新增、删除或修改用户后，只需在客户端执行：

```text
更新订阅
```

即可同步最新配置。

---

# 📂 数据目录

所有配置均保存在挂载目录：

```text
/opt/anytls-panel/data
```

主要文件说明：

| 文件              | 作用          |
| --------------- | ----------- |
| config.yaml     | Mihomo 配置文件 |
| server.crt      | SSL 证书      |
| server.key      | SSL 私钥      |
| panel_pwd.txt   | 面板密码        |
| cert_domain.txt | 证书绑定域名      |

迁移或备份时，仅需备份整个 `data` 目录。

---

# 🔄 更新项目

拉取最新镜像：

```bash
docker compose pull
docker compose up -d
```

或：

```bash
docker pull ghcr.io/6106757-lab/anytls-mihomo:latest
docker restart anytls-mihomo-panel
```

---

# ⚠️ 免责声明

本项目仅用于学习、研究及合法的网络技术交流。

请严格遵守所在地法律法规，不得将本项目用于任何违法违规用途。

因使用本项目所产生的一切风险及后果，均由使用者自行承担，项目作者不承担任何责任。
