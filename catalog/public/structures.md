# 公开事件配方（不等人）

带子来自公开方案 + 同一段 NVDA 财报回放，不等人贴成交。

强事件（财报）的边是**定价**，不是猜涨跌。默认仍然是定义风险。裸卖、玉蜥蜴的裸 put 写在目录里只为了拒绝。

## 怎么选（写死）

完整门见表 `catalog/public/indicators.md`。缺一门短波动输入就空仓。

1. 事件日或 T−1，或窗口不在 T−2–5：空仓。
2. 短波动要 **同时** 过：IV rank≥50、implied/hist≥1.2、VRP≥1、期限斜率≥15vol、ATM 价差≤8%、IC credit/width≥0.20、max loss≤$500、ATM OI≥500、路径 helped≥50%（n≥4）。
3. 短波动不过、但 implied/hist<1.0 且价差/OI/反向路径过：反向铁秃鹰。
4. 其余：空仓。
5. VIX 百分位不是门。
6. 永远不选裸跨、裸跨式、玉蜥蜴。

tastylive 把期望波动写成 ATM 跨 × 0.85。本仓现场 implied 用 **straddle bid / spot**（卖得走的那一侧），不用中间价。

## 单腿

| id | 论文 | 过公告？ | 纸盘 |
| --- | --- | --- | --- |
| `long_call` / `long_put` | 赌方向。IV 贵时方向对了也常亏 | 是 | 对照 |
| `iv_expansion_exit_before` | T−5 左右买权利，T−1 卖给峰值 IV | **否** | 可以，日线评不了 |
| `covered_call` | 要底仓股票 | 是 | 观察 |

## 两腿

| id | 论文 | 纸盘 |
| --- | --- | --- |
| `put_credit_spread` / `call_credit_spread` | 有方向才卖垂直价差，短边在期望波动外 | 对照 |
| `long_straddle` / `long_strangle` | implied 便宜才买波动 | 对照 |
| `calendar_short_front` | 卖事件周、买更远。大跳空两边坏 | 对照 |
| `reverse_calendar_exit_before` | 买近卖远，**打印前走** | 可以，日线评不了 |
| `short_strangle` / `short_straddle` | 裸卖 | **禁止** |

## 三腿 / 四腿

| id | 论文 | 纸盘 |
| --- | --- | --- |
| `short_iron_condor` | 默认。短边 ±1.0× implied，翼 $5 | 默认 |
| `short_iron_fly` | ATM 短跨 + 翼。更脆 | 对照 |
| `reverse_iron_condor` | implied 便宜时的定义风险长波动 | 备选 |
| `broken_wing_butterfly` | 飞的变体 | 对照 |
| `jade_lizard` | 下行裸卖权 | **禁止** |

## 来源

- tastylive：二元事件卖权利金；期望波动 ≈ ATM 跨 × 0.85；用覆盖公告的最近到期。
- The Option Premium（2026-07-09）：铁秃鹰为工作马；1–2% 资金；不要猜财报。
- VolRadar / ORATS：crush 是代理；他们自己的产品在 7 日内不让新开——那是他们的风控，不是我们的成交。
- Volatility Box：短边在期望波动外，$5 翼；日历怕大缺口。
- FlashAlpha：implied 贵卖、implied 便宜买；反向铁秃鹰是定义风险长波动。
- Ticker Daily：事件前买权利、打印前卖掉，吃 IV 膨胀。
- X 新闻（2026-08-26）：NVDA 是当天强事件；Burry 的 call 是空头组合的对冲，不是「事件前赌涨」的模板。

机器命令：`python3 -m kop recipes`，`python3 -m kop select`，`python3 -m kop sweep`。
