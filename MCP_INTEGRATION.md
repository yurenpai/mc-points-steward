# MCP 集成说明 · 麦享掌柜

> 本文件说明「麦享掌柜」（`mc-points-steward`）实际使用了哪些 MCP Server / Tool、
> 如何调用、以及各自带来的业务价值。
>
> 参赛必交文件 · [麦当劳中国 MCP 开发者创新大赛](https://github.com/M-China/mcd-developer-innovation-challenge)
>
> 所有字段与数值均为 **2026-10-12 真实调用实测**，未实测项已明确标注。

---

## 1. 接入信息

| 项目 | 值 |
|---|---|
| MCP Server | `mcd-mcp`（麦当劳中国官方） |
| 传输协议 | Streamable HTTP |
| 接入地址 | `https://mcp.mcd.cn` |
| 鉴权 | `Authorization: Bearer <TOKEN>` |
| 限流 | 600 次/分钟/Token |
| 工具总数 | 35（本机实测 `connection-ready tools:35`） |
| 本项目实际使用 | **10 个**（其中 2 个不可逆操作未实调） |

配置示例见 [`mcp-config.example.json`](mcp-config.example.json)，**仅含环境变量占位符 `${MCD_MCP_TOKEN}`，不含真实凭证**。

> ⚠️ **实测坑**：`Authorization` 头**必须带 `Bearer ` 前缀和一个空格**。
> 裸 token → `403 校验鉴权authToken必填`；带前缀 → `200` 且成功拉取工具列表。

---

## 2. 工具清单与业务价值

| # | Tool | 入参 | 在本项目中的角色 | 状态 |
|:--:|---|---|---|:--:|
| 1 | `query-my-account` | 无 | **F1 积分账本**：读余额、累计、已用、已过期、冻结、本月/下月将过期 | ✅ 实测 |
| 2 | `mall-points-products` | `catRuleIds` | **F2 商城去伪 + F3 性价比**：核心数据源，逐类目查询后合并 | ✅ 实测 |
| 3 | `mall-product-detail` | `spuId` | **F4 商品详情 + F3+ 隐藏现金成本**：SKU、兑换内容、 **`extTradePrice`（列表接口没有）** | ✅ 实测（9 件全量） |
| 4 | `mall-create-order` | `skuId`+`spuCategory` (`addressId`, `count`) | **F5 兑换下单**：不可逆操作，需二次确认 | ⚠️ 契约已确认，**未实调**（不发起真实交易） |
| 5 | `query-lottery-info` | 无 | **F6 抽奖参谋**：奖池结构与资格判定 | ✅ 实测 |
| 6 | `draw-lottery` | — | **F6 执行抽奖**：需用户明确说"抽" | ⏳ 未执行（不发起真实扣分） |
| 7 | `query-my-prizes` | 无（`pageNum`, `pageSize`≤50） | **F7 奖品档案**：历史中奖记录 | ✅ 实测（空，结构已确认） |
| 8 | `now-time-info` | 无 | **校时**：判过期前必调，不依赖本机时钟 | ✅ 实测 |
| 9 | `mall-order-list` | `lastId`, `size`(≤10) | 商城订单核对 | ✅ 实测（空，结构已确认） |
| 10 | `campaign-calendar` | `specifiedDate`(可选) | **F8 活动日历**：限定情报附属层 | ✅ 实测（10 月 14 个活动日） |

> **10 项中 8 项已实调**（2 项不可逆操作未发起真实调用，契约已从 schema 完整记录）。

---

## 3. 调用链路

### 3.1 F1 · 积分账本

```
query-my-account  ──►  账本三层视图
                       ├─ 可用积分
                       ├─ 来龙去脉：累计 − 已用 − 已过期 − 冻结 ≈ 可用（自洽校验）
                       └─ 到期提醒：本月将过期 / 下月将过期（置顶，最高价值信息）
```

**实测返回（9 字段，已脱敏）**

```json
{
  "availablePoint": "0",
  "accumulativePoint": "0",
  "usedPoint": "0",
  "expiredPoint": "0",
  "frozenPoint": "0",
  "currentMouthExpirePoint": "0",
  "nextMouthExpirePoint": "0",
  "lastMouthExpirePoint": "0",
  "currency": "麦享会积分"
}
```

> ⚠️ **官方拼写坑**：字段名是 `current**Mouth**ExpirePoint`（**Mouth「嘴」，不是 Month「月」**），
> 三个过期字段全部沿用这个拼错的版本。按正确拼写 `Month` 写代码会取到 `None`。
> 这是本项目实测发现并写进 SKILL.md 的硬规则。

---

### 3.2 F2 + F3 · 商城去伪与性价比（核心链路）

```
now-time-info  ─────────────► 校准当前时间（不信任本机时钟）
        │
        ▼
mall-points-products  ──►  ① catRuleIds=1>4    （商品券，24 件）
   ├─ 逐类目查询 ────────►  ② catRuleIds=2>8    （周边，3 件）
   │   （不能只查默认）     ③ 按需追加 2 / 2>9 / 1>6>40
        │
        ▼
   按 spuId 合并去重  ──►  27 件积分类商品
        │
        ▼
scripts/rank_products.py
   ├─ 剔除现金商品   point == 0 且 price > 0    → cash_only
   ├─ 剔除假上架     status == 2 但 downTime < now → extinct
   ├─ 剔除售罄       status == 3                 → extinct
   ├─ 解析券面价     从 spuName 正则取「N元」      → coupon_price
   ├─ 算性价比       point / coupon_price        → unit_price（分/元）
   ├─ 临期分级       ≤7天 ⚠️ / ≤3天 🔴
   └─ 同名陷阱检测   同名但积分不同               → name_traps
        │
        ▼
   输出 4 个桶 + coverage + name_traps
        │
        ▼
   Agent 解读（脚本不做主观判断）
```

**为什么必须逐类目查（本项目最重要的实测发现）**

| 查询方式 | 返回件数 | 其中真可兑 |
|---|---:|---:|
| 默认（不传 `catRuleIds`） | 50 | **7** ❌ 少报 |
| `catRuleIds=1>4` | 24 | 9 |
| `catRuleIds=2>8` | 3 | 0 |
| **逐类目合并去重** | **27** | **9** ✅ |

默认查询漏掉 `17075`（3.9元圆筒冰淇淋 100 分）与 `17078`（16.9元2份麦辣鸡翅 200 分），
**两件都是真能兑的** —— 只调一次默认查询会少报 **22%** 的可兑选项。

**调用示例**

```bash
python scripts/rank_products.py \
  --input raw_cat_1_4.json \
  --input raw_cat_2_8.json \
  --now "2026-10-12 16:07:00"
```

输出的 `coverage` 段记录每份输入的增量贡献，让"数据是否查全"可追溯：

```json
"coverage": [
  {"input": "raw_cat_1_4.json", "returned": 24, "new_after_dedup": 24, "cumulative": 24},
  {"input": "raw_cat_2_8.json", "returned": 3,  "new_after_dedup": 3,  "cumulative": 27}
]
```

**实测结果（2026-10-12 16:07，合并后 27 件）**

| 分类 | 件数 |
|---|---:|
| 真可兑 | **9** |
| 已绝版（名存实亡） | **18** |
| 时效未知 | 0 |

> 绝版率 **18/27 = 67%**。

**去伪实证**：`Nike Book 2 麦当劳特别联名款`（8888 分）仍返回 `status: 2`（上架），
但其兑换窗口为 `2026-06-05 14:00:00 ~ 16:00:00`——**仅两小时**，早已结束。
周边类目（`2>8`）实测 3 件，**100% 已过期**。

**性价比实测极值**：最优 `7.25 分/元`（6.9元可乐麦炫酷），最差 `36.53 分/元`
（21.9元巨无霸可乐组合），**相差 5.04 倍**。

**同名陷阱实测（并已自我更正）**：`10.9元指定小食任选` 存在两个 spuId——`17076`（100 分）与
`17077`（200 分），**名字一字不差但积分差一倍**。项目初期据此判定为"选错就多付一倍"，
并建议"选最低分那个"。补调 `mall-product-detail` 后**推翻了该结论**：

| spuId | 积分 | 到店另付 | 实际兑换内容（取自 `note`） |
|---:|---:|---:|---|
| 17076 | 100 | ¥10.9 | 中薯条 / 奥利奥麦旋风 任选 1 件 |
| 17077 | 200 | ¥10.9 | 麦乐鸡-4块 / 麦辣鸡翅-2块 / 那么大鸡排（椒盐风味）任选 1 件 |

→ **是"同名不同物"，不是"同物不同价"。** 贵的那个未必是坑。
现已改为展示内容差异，让用户按想吃什么选，而不是按积分高低选。

---

### 3.3 F3+ · 隐藏现金成本（🔴 本轮核心发现）

`mall-points-products` 与 `mall-product-detail` 返回的**不是同一套价格信息**：

```
mall-points-products   →  point（积分） / price（恒为 "0"）
                          ✗ 完全没有 extTradePrice

mall-product-detail    →  skuList[].points / .price / .extTradePrice  ✅
```

**`extTradePrice` = 券核销额外支付金额**，即兑换成功后到店还得再付的现金。

对真可兑 9 件**逐一**调 `mall-product-detail`（2026-10-12 18:34，无抽样）：

| spuId | 商品 | 积分 | `extTradePrice` |
|---:|---|---:|---:|
| 17073 | 6.9元可乐麦炫酷 | 50 | **¥6.9** |
| 17074 | 6.9元香芋派/菠萝派任选 | 50 | **¥6.9** |
| 17075 | 3.9元圆筒冰淇淋 | 100 | **¥3.9** |
| 17076 | 10.9元指定小食任选 | 100 | **¥10.9** |
| 17077 | 10.9元指定小食任选 | 200 | **¥10.9** |
| 17078 | 16.9元2份麦辣鸡翅 | 200 | **¥16.9** |
| 17079 | 16.9元麦辣可乐组合 | 500 | **¥16.9** |
| 17080 | 17.9元板烧可乐组合 | 500 | **¥17.9** |
| 17081 | 21.9元巨无霸可乐组合 | 800 | **¥21.9** |

> **纯积分白拿：0 / 9（0%）。** 另付区间 **¥3.9 ~ ¥21.9**。
> `extTradePrice` 与商品名内的数字 **9/9 完全恒等** → 商品名里的数字是**券后支付价**，不是市价。

**这条发现的工程含义**：把「3.9元圆筒冰淇淋 100 分」理解成"100 积分换一个冰淇淋"是错的，
正确理解是"**100 积分 + 3.9 元** 换一个冰淇淋"。只看列表接口做推荐，属于实质性误导。

**脚本落地**（`rank_products.py --detail`）：

```bash
python scripts/rank_products.py \
  --input raw_cat_1_4.json --input raw_cat_2_8.json \
  --detail mall_details_20261012.json \
  --now "2026-10-12 18:34:00"
```

```json
"hidden_cost": {
  "redeemable_total": 9,
  "detail_matched": 9,
  "with_cash_on_top": 9,
  "pure_points": 0,
  "cash_min": 3.9,
  "cash_max": 21.9,
  "warning": "全部需到店另付现金，无一件是纯积分白拿"
}
```

未传 `--detail` 时 `cash_on_top` / `pure_points` 保持 `null`——**宁可不说，不可说错**。

**两个附带发现的官方不一致**（与 `currentMouthExpirePoint` 同类，已写进 SKILL.md）：

1. **时间字段不同名**：列表是 `upTime` / `downTime`，**详情是 `upDate` / `downDate`**。
   按文档写 `data.downTime` 取详情会得到 `None`。
2. **`note` 禁止解析**：官方明确要求购买须知"必须原文展示，不得拆分、提取或改写；
   **严禁从中提取任何数值用于下单校验、价格计算、库存判断**"。
   本项目的所有数值均取自 `skuList`，**不取自 `note`**（有针对性断言守护）。

已由 `tests/test_hidden_cost.py`（42 断言）钉死。

---

### 3.4 F6 · 抽奖参谋

```
query-lottery-info  ──►  scripts/lottery_advice.py  ──►  Agent 做期望值解读
                          （解析奖池结构）
```

**实测返回要点**

| 字段 | 值 |
|---|---|
| `activityName` / `activityCode` | 麦麦积分抽奖 / `dtx2` |
| `beginTime` / `endTime` | 2025-01-26 / **2030-12-31**（长期活动） |
| `drawPoint` | `24`（单次消耗积分） |
| `drawTypeText` | 消耗积分抽奖 |
| `drawDecision.resourceEligible` | `false` |
| `drawDecision.reason` | `积分不足` |
| `drawDecision.nextConsumption` | `{type:"POINTS", points:"24", text:"本次将消耗 24 积分"}` |

**奖池实测 10 品**：立减券 ×3（1/2/3 元）+ 折扣券 ×6（5折×4、5.5折×1、6折×1）
+ 积分奖 ×1（**30 积分**，即"回血"奖）。

> **铁律（写进 SKILL.md）**：能否抽奖**只信 `drawDecision.resourceEligible`**，
> **禁止**用 `availablePoint` 或 `availableTimes` 自行推断。官方明确"库存、人群、风控等以实际抽奖结果为准"。

---

### 3.5 F5 · 兑换下单（未执行的不可逆操作）

```
用户选定商品
   → mall-product-detail(spuId)       拉 SKU、兑换内容、extTradePrice（隐藏现金）
   → 输出完整摘要（商品名 / 积分 / 到店另付 / 有效期）
   → 等用户明确说「确认」「换」
   → mall-create-order(skuId, spuCategory [, addressId, count])
```

**入参契约**（来自工具 schema，2026-10-12 确认）：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `skuId` | integer | ✅ | 取自 `mall-product-detail` 的 `skuList[].skuId`，**不是 spuId** |
| `spuCategory` | string | ✅ | `"1"` 虚拟商品 / `"2"` 实体物品 |
| `addressId` | string | 条件 | 仅 `spuCategory="2"`（实物）时必填 |
| `count` | integer | 否 | 默认 1 |

**硬约束**：仅支持 `shopId=2`（实测积分商品的 `shopId` 均为 2）；
兑换多件必须**分别下单且排队**（等前一个响应成功再调下一个）；
**禁止**跳过调用直接生成"下单成功"，**禁止**复用已有订单冒充。
所有限购/库存/价格校验**以下单接口返回为准**，不得用详情的 `spuLimit` 或 `note` 做前置校验。

返回：`orderId` / `coupons[]` / `couponId` / `orderItemId` / `couponCodes[]` /
`receiveQuantity` / `orderItemStatus`（1 成功 / 0 失败）/ `orderStatus` /
`status`（1 全部成功 / 2 部分成功 / 0 失败）。

四道安全闸（见 SKILL.md「安全红线」）：

1. 执行前输出完整摘要
2. 必须等明确指令——"看看""随便""先了解"一律不执行
3. 积分不足客观提示，**绝不引导消费**
4. 失败原样转述，**不重试、不猜测原因**

> ⏳ **未发起真实调用**：`mall-create-order` 与 `draw-lottery` 为不可逆操作
> （产生真实订单、券码与积分扣减），本项目不代为发起；
> 入参与返回字段已从 schema 完整确认并记入 `references/api_fields.md`。

---

## 4. 业务价值总结

| 维度 | 没有这个 Skill | 有了麦享掌柜 |
|---|---|---|
| **知道有多少分** | 打开 App 看一个余额 | 账本三层 + 到期提醒，来龙去脉自洽 |
| **知道能换什么** | 看到 27 件"在售"，信以为真 | 剔掉 18 件假的，只剩 9 件真可兑 |
| **知道换哪个划算** | 无法比较（`price` 字段恒为 0） | 解析券面价，按「分/元」排序，最优最差差 5 倍 |
| **知道还要付多少钱** 🔴 | 以为积分兑换就是免费 | 标出"到店另付 ¥X"，实测 9/9 都要付 |
| **避免同名踩坑** | 两个同名商品分不清 | 检出后展示**内容差异**，按想吃什么选 |
| **数据是否查全** | 不知道接口会漏 | 逐类目合并 + `coverage` 可追溯 |
| **会不会误操作** | App 里容易误触 | 不可逆操作一律二次确认 |

**核心价值**：麦当劳 MCP 提供了 35 个工具，但**原始数据存在系统性失真**
（假上架 67%、隐藏现金成本 100%、默认查询漏报 22%、同名不同物）。
麦享掌柜的价值不在于"多接了几个接口"，而在于**把失真的数据还原成一份可信的账**
——这是一层 MCP 本身不提供的判断。

---

## 5. 未使用但有价值的工具（路线图）

| Tool | 潜在用途 |
|---|---|
| `available-coupons` / `auto-bind-coupons` | 攒分路径：领券与积分联动 |
| `order-list` | 消费分析（实测返回空，无数据源） |
| `list-nutrition-foods` | 营养维度（与积分主线无关，主动划清边界） |
| `query-store-coupons` / `query-promotions` | 门店级优惠（需先拿 addressId → storeCode，链式依赖较长） |

> `campaign-calendar` 已于 2026-10-12 实测（10 月 14 个活动日，含
> 麦当劳×PEACEMINUSONE 联名三弹与学生麦金学期卡），已纳入 F8 限定情报附属层。

---

## 6. 降级与容错

| 场景 | 策略 |
|---|---|
| mcd-mcp 未接入/未授权 | 提示接入要点（Bearer 前缀），**绝不伪造数据** |
| 商品列表返回空 | "商城当前无可兑商品"，不输出空榜 |
| 缺 `downTime` | 归"时效未知"栏，不标临期 |
| 缺券面价 | 单列"无券面价参考"，不填 0、不排名 |
| `drawDecision` 缺失 | 不推断资格，原样展示 + "以 App 页面为准" |
| 下单/抽奖失败 | 原样转述错误，不重试、不猜测原因 |
| 积分为 0 | 走「开张前夜」分支，给攒分路径，**严禁引导消费** |

统一话术前缀：**「掌柜没法确认这件事」**——明确区分"没查到"与"确认没有"。

---

## 7. 离线演示（无需 Token）

无需麦当劳 Token，一键复现完整输出（内置 2026-10-12 真实调用快照）：

```bash
cd skill && python scripts/demo.py
```

数据来自 `tests/fixtures/` 下 2026-10-12 真实调用快照（账户 ID 已脱敏）。
演示开口强制声明：① 这是**快照数据**非实时；② 看真实数据需连接 mcd-mcp。

---

## 8. 合规声明

- 本文件不含任何真实 Token、手机号、账户凭证
- 所有展示数据均已脱敏（账户 ID 已处理）
- 配置文件仅使用环境变量占位符 `${MCD_MCP_TOKEN}`
- 完整合规声明见 [`CONTEST_DECLARATION.md`](CONTEST_DECLARATION.md)
