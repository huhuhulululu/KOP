# 指标（能挡单才算数）

每一行要么是 **GATE**（不过就空仓），要么是 **INFO**（背景，不开门）。缺 GATE 输入 = 关。改阈值要换 playbook 名字。

现场命令：`python3 -m kop snapshot`

## GATE

| 名字 | 公式 | 源 | 短波动门槛 | 长波动门槛 |
| --- | --- | --- | ---: | ---: |
| `days_before` | 事件日 − 今天，按交易日 | Yahoo 日线日历 | 在 2–5 | 同左 |
| `implied_over_hist` | ATM 跨 **bid** / spot ÷ 近 6 次 \|收盘变动\| 中位数 | CBOE 链 + 回放 | ≥ 1.20 | < 1.00 |
| `iv30_range_rank`（样本 < 60 用这个） | 100 × (iv30 − 1y低) / (1y高 − 1y低) | CBOE historical_data | ≥ 50 | 不要求贵 |
| `iv_percentile`（样本 ≥ 60） | ledger 里日 iv30 的百分位 | `observations` | ≥ 50 | 不要求贵 |
| `vrp_iv30_over_hv20` | iv30 / HV20 | CBOE iv30 / Yahoo 对数收益 | ≥ 1.00 | 不用 |
| `term_slope_vol` | 近月 ATM IV − 约 30DTE ATM IV（vol pts） | CBOE 链 | ≥ 15 | 不用 |
| `atm_straddle_spread_pct` | (跨 ask − 跨 bid) / 跨 bid | CBOE ATM | ≤ 0.08 | ≤ 0.08 |
| `ic_credit_over_width` | 铁秃鹰净权利金（bid/ask+$0.05 滑点后） / $5 | CBOE 拟建仓 | ≥ 0.20 | 不用 |
| `ic_max_loss_usd` | 宽度 − 权利金 + 费 | 同上 | ≤ 500 | 不用 |
| `atm_oi` | ATM call OI + put OI | CBOE | ≥ 500 | ≥ 500 |
| `path_hit_rate` | 近 ≥4 次里，短铁秃鹰路径 `helped` 的比例 | Yahoo 高低 vs ±implied | ≥ 0.50 | 不用 |
| `reverse_path_hit_rate` | 反向铁秃鹰路径 `helped` 比例 | 同上 | 不用 | ≥ 0.50 |

`helped` / `hurt` 是路径论文，**不是美元**。没有历史买卖价就不能把 path_hit 说成已验证盈亏。

## INFO（不算分、不开门）

| 名字 | 为什么留下 |
| --- | --- |
| `vix` / `vix_1y_percentile` | 指数波动。安静的 VIX + 贵的单票事件溢价是合法短波动；**不要求 VIX 高** |
| `vix9d` / `vix3m` | 指数期限结构，背景 |
| `hv60` | 慢实现波动，背景 |
| `risk_reversal_25d` | 25Δ put IV − call IV。正=看跌偏斜。事件周常会被 call 买偏，不作门 |
| `event_week_oi` / `volume` | 流动性背景 |
| `paid_historical_bid_ask` | 有 key 才能补历史成交。没 key 就不编权利金 |

## 公开方法从哪来（不是花架子）

- **期望波动 / 卖事件权利金**：tastylive expected move = ATM 跨；本仓用 **straddle bid / spot**，不用中间价，也不乘 0.85。
- **IV rank 才卖**：常见短波动纪律。CBOE 没有日 iv30 序列时用 1 年高低 range rank，样本够了换百分位，阈值都是 50。
- **VRP（隐含 / 实现）**：标准 variance-risk-premium。用 iv30/HV20，不用 VIX/HV。
- **期限结构**：事件周 IV 明显高于 30 日 IV，才说明权利金堆在打印附近。
- **买卖价差**：宽价差把 credit/width 吃掉。门槛写死 8%。
- **路径命中**：同一 6 次 NVDA 财报，理论短边 ±1× implied。2025-02 到 2026-05，短铁秃鹰帮到 **2/6**。这个数会挡短波动，哪怕现场 implied 看起来很贵。

## 今天（2026-08-26，事件日）现场不该过的门

事件日 `days_before=0` 已经空仓。即使不是事件日，当时测到的其它硬门也过不了：

- iv30 range rank ≈ 42.7 < 50
- path_hit_rate = 2/6 ≈ 0.33 < 0.50

implied/hist、VRP、期限、价差、credit/width 当时是过的。过的门不能把没过的门洗绿。
