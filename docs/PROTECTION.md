# 代码保护与授权详细说明

本文档说明“代码加固 + license 授权”方案的完整落地方式，以及它的能力边界。

## 1. 设计目标

目标不是“绝对不可逆”，而是：
- 提高源码逆向成本
- 控制可运行性（到期、设备绑定、可撤销）
- 让部署流程标准化、可运维

## 2. 威胁模型与边界

可覆盖：
- 交付镜像后，用户直接查看明文 Python 源码
- license 过期后仍继续运行
- license 拷贝到另一台机器直接运行

无法完全覆盖：
- 拥有 root 权限的对手进行动态内存提取
- 对 Python 运行时做深度 Hook/调试绕过
- 容器运行期被完整 dump 后做离线分析

结论：该方案是“工程防护”，不是“军事级防护”。

## 3. 方案总览

采用两层机制：

1) 构建期代码保护（Build-time）
- 使用 PyArmor 生成受保护产物
- 镜像只打包受保护产物，不携带源码
- 参考：`docker/Dockerfile.protected`

2) 运行期授权校验（Runtime）
- 服务启动时校验 `license.json`
- 校验内容：签名、有效期、机器绑定
- 代码位置：`app/common/license.py` 与 `app/application.py`

## 4. license 数据结构

```json
{
  "subject": "customer_a",
  "issuedAt": "2026-01-01T00:00:00Z",
  "expiresAt": "2027-01-01T00:00:00Z",
  "machineId": "xxxx",
  "signature": "base64..."
}
```

签名规则：
- 对除 `signature` 以外字段做 canonical JSON 序列化
- 使用 Ed25519 私钥签名
- 服务端用公钥验签

## 5. 为什么仅改 docker-compose 不够

`docker-compose` 只能：
- 编排容器
- 传环境变量
- 挂载文件

它不能：
- 把源码加密
- 替换解释器行为
- 自动实现签名体系

因此必须有构建期步骤（PyArmor/Nuitka/Cython 之一），compose 只负责“把结果跑起来”。

## 6. 实施步骤（推荐）

### 6.1 生成密钥对

```bash
python3 scripts/license_tool.py gen-key \
  --private-key runtime/license/private_key.pem \
  --public-key runtime/license/public_key.pem
```

### 6.2 读取目标机器标识

```bash
cat /etc/machine-id
```

### 6.3 签发 license

```bash
python3 scripts/license_tool.py sign \
  --private-key runtime/license/private_key.pem \
  --subject customer_a \
  --machine-id "$(cat /etc/machine-id)" \
  --expires-at 2027-12-31T23:59:59Z \
  --output runtime/license/license.json
```

### 6.4 构建受保护镜像

```bash
./scripts/build_protected_image.sh ai_alerting:protected
```

### 6.5 启用授权校验

在 compose 或运行环境设置：

```yaml
ALERT_LICENSE_ENABLED: "true"
ALERT_LICENSE_PATH: /root/.ai_alerting/license/license.json
ALERT_LICENSE_PUBLIC_KEY_PATH: /root/.ai_alerting/license/public_key.pem
ALERT_LICENSE_REQUIRE_MACHINE_BINDING: "true"
ALERT_LICENSE_FAIL_OPEN: "false"
ALERT_LICENSE_ALLOW_HOSTNAME_FALLBACK: "false"
```

## 7. 运维建议

私钥管理：
- 私钥只放在签发机，不进入仓库、不进镜像
- 建议放到 KMS/HSM 或至少离线保险库

续期策略：
- 采用短周期 license（如 3 个月），到期前自动签发新 license
- 服务可通过发布新 `license.json` 完成续期

换机策略：
- 设备变更时，重新读取新 machine-id 并重签 license

失效策略：
- 若需立即停用，撤销当前 license 并下发新策略（过期时间设为当前）

监控告警：
- 记录 license 到期时间
- 距离到期 30/7/1 天分别告警

## 8. 配置优先级

授权与告警参数统一遵循：
- 环境变量 > `runtime/config.json` > 代码默认

配置加载失败策略：
- 默认严格模式（`ALERT_CONFIG_STRICT=true`）下，`config.json` 解析失败会阻止启动。
- 仅建议在故障应急时临时设置 `ALERT_CONFIG_STRICT=false` 回退默认值。

## 9. 安全加固可选项（增强）

- 将镜像设为只读根文件系统（只把 runtime 挂载为可写）
- 关闭容器特权，使用最小权限用户运行
- 去掉调试工具、shell
- 配合网关鉴权与 mTLS，减少接口暴露风险
