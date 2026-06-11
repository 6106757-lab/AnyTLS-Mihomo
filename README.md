AnyTLS Mihomo Web Panel
一个基于 Mihomo (Clash Meta) 内核 的 AnyTLS 可视化节点管理面板。
通过简洁直观的 Web 界面，轻松掌控端口、多账号管理、SSL 证书生命周期，并可一键调校客户端参数（SNI、uTLS 指纹等），自动生成专属导入二维码和 Base64 动态订阅链接。
🌟 核心特性
💻 可视化管理：告别笨重繁琐的命令行与 YAML 修改，在浏览器中直观配置所有参数。
👥 多用户支持：支持一键增、删、改多个账号（用户名与密码）。
🔒 证书生命周期管理：
支持自签名证书（一键基于自定义域名续签/重签 10 年证书）。
支持上传真实的 CA 域名证书。
网页端实时读取并直观显示证书生效/过期时间。
⚙️ 客户端参数精准调校：自定义 SNI 伪装域名、选择 uTLS 浏览器指纹（Chrome, Firefox, Safari 等）、开启/关闭跳过证书验证。
📊 混淆策略自定义：完美支持自定义 padding-scheme 规则（对抗精准流量长度分析）。
🔗 一键导出与动态订阅：
为每个账号一键生成 anytls:// 客户端协议链接和导入二维码。
提供专属动态订阅接口（/sub），可填入 NekoBox / v2rayN / Shadowrocket 自动同步与更新节点。
🚀 快速部署
本项目已完全容器化，并托管于 GitHub Container Registry (GHCR)。
准备工作
请确保你的服务器已安装 Docker 和 Docker Compose。若未安装，在 Ubuntu 上可通过以下命令安装：
code
Bash
curl -fsSL https://get.docker.com | sh && systemctl enable --now docker
方法一：使用 Docker Compose 运行（推荐）
创建工作目录：
code
Bash
mkdir -p /opt/anytls-panel && cd /opt/anytls-panel
创建 docker-compose.yml 配置文件：
code
Yaml
version: '3'
services:
  anytls-panel:
    image: ghcr.io/6106757-lab/anytls-mihomo:latest
    container_name: anytls-mihomo-panel
    restart: always
    network_mode: "host" # 使用 host 模式以便直接映射端口
    volumes:
      - ./data:/root/.config/mihomo # 本地数据持久化
启动容器：
code
Bash
docker compose up -d
方法二：使用 Docker Run 命令行直接运行
如果你不想创建任何配置文件，可以直接运行以下命令快速启动：
code
Bash
docker run -d \
  --name anytls-mihomo-panel \
  --restart always \
  --network host \
  -v /opt/anytls-panel/data:/root/.config/mihomo \
  ghcr.io/6106757-lab/anytls-mihomo:latest
📝 初始登录与使用说明
访问面板：
在浏览器中输入：http://你的服务器IP:8888
初始密码：
默认登录密码为：admin
修改密码（重要）：
登录后请立即切换到 “安全设置” 选项卡，修改面板密码以防被扫。
端口冲突解决：
默认监听端口为 8443。如果遇到端口被占用的提示，可在面板页面中将监听端口直接修改为 8444 或其他未占用端口，点击保存并应用即可。
🔗 节点导入与客户端使用
1. 节点一键导入 / 扫码
在“用户管理”栏目中，点击账号右侧的 “生成连接”，即可弹出该账号对应的 anytls:// 连接。
可以直接复制该链接，或使用客户端扫码直接导入。
2. 动态订阅链接 (Sub)
面板最上方会为你展示专属的动态订阅地址，格式通常为：http://你的服务器IP:8888/sub
将该地址复制并粘贴进 NekoBox、v2rayN 或 Shadowrocket 的订阅管理中。以后若在网页端增删账号，只需在客户端一键“更新订阅”即可，无需重复手动导入。
📂 数据存放说明
配置挂载后，宿主机本地的工作目录为：/opt/anytls-panel/data/。
该目录下会自动生成并保存以下关键数据（迁移或备份只需备份此目录即可）：
config.yaml（自动格式化生成的内核配置文件）
server.crt / server.key（当前的 SSL 证书文件对）
panel_pwd.txt（加密保存的面板登录密码）
cert_domain.txt（保存绑定的证书域名）
🔒 免责声明
本项目仅供学习、科研及计算机网络技术的研究与探讨使用。请勿将其用于非法用途。使用本软件所造成的任何直接或间接后果，均由使用者自行承担。# AnyTLS-Mihomo
