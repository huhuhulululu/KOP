# NVDA 财报金带子（研究，不是成交）

Playbook：`nvda_earnings_defined_short_vol`。进场默认 T−3 个交易日。
现货路径来自 Yahoo 日线。权利金进/出没有历史买卖价，所以 **往返盈亏空着**。
Vendor implied / crush 是 VolRadar 引用的 ORATS 10 日 ATM 代理，**不是** 当时链上的买卖价，不能当 fill。
可计入循环的样本（human / recorded_bid_ask）：**0**。不到 4 笔就不许开策略循环。

| 事件 | 进场日 | IV rank | 结构 | 进场价 | 跳空 | 收盘路径 | 出场 | 往返 | 状态 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NVDA FY25 Q4 2025-02-26 AMC | 2025-02-21 (T−3) | missing | short_iron_condor | — | +2.83% | -8.48% | 50% credit or T+1, first; not filled | — | `missing_quotes` |
| NVDA FY26 Q1 2025-05-28 AMC | 2025-05-22 (T−3) | missing | short_iron_condor | — | +5.52% | +3.25% | 50% credit or T+1, first; not filled | — | `missing_quotes` |
| NVDA FY26 Q2 2025-08-27 AMC | 2025-08-22 (T−3) | missing | short_iron_condor | — | -0.43% | -0.79% | 50% credit or T+1, first; not filled | — | `missing_quotes` |
| NVDA FY26 Q3 2025-11-19 AMC | 2025-11-14 (T−3) | missing | short_iron_condor | — | +5.06% | -3.15% | 50% credit or T+1, first; not filled | — | `missing_quotes` |
| NVDA FY26 Q4 2026-02-25 AMC | 2026-02-20 (T−3) | missing | short_iron_condor | — | -0.66% | -5.46% | 50% credit or T+1, first; not filled | — | `missing_quotes` |
| NVDA FY27 Q1 2026-05-20 AMC | 2026-05-15 (T−3) | missing | short_iron_condor | — | -0.53% | -1.77% | 50% credit or T+1, first; not filled | — | `missing_quotes` |

## 路径，不是盈亏

跳空只是开盘。有的日子开盘不远，当天走出更大的幅度（例如 2025-02-26 跳空 +2.8%，收盘 −8.5%）。
短波动能不能拿住，要看整天高低，不是只看开盘缺口。

| 事件 | 进场收盘 | 事件收盘 | 反应开/高/低/收 | vendor implied | 收盘是否超出 implied |
| --- | ---: | ---: | --- | ---: | --- |
| FY25 Q4 2025-02-26 | 134.43 | 131.28 | O 135.00 / H 135.01 / L 120.01 / C 120.15 (gap +2.83% · close -8.48%) | missing | n/a |
| FY26 Q1 2025-05-28 | 132.83 | 134.81 | O 142.25 / H 143.49 / L 137.91 / C 139.19 (gap +5.52% · close +3.25%) | missing | n/a |
| FY26 Q2 2025-08-27 | 177.99 | 181.60 | O 180.82 / H 184.47 / L 176.41 / C 180.17 (gap -0.43% · close -0.79%) | ±3.0% | False |
| FY26 Q3 2025-11-19 | 190.17 | 186.52 | O 195.95 / H 196.00 / L 179.85 / C 180.64 (gap +5.06% · close -3.15%) | ±3.4% | False |
| FY26 Q4 2026-02-25 | 189.82 | 195.56 | O 194.27 / H 194.29 / L 184.32 / C 184.89 (gap -0.66% · close -5.46%) | ±3.0% | True |
| FY27 Q1 2026-05-20 | 225.32 | 223.47 | O 222.29 / H 227.40 / L 217.93 / C 219.51 (gap -0.53% · close -1.77%) | ±2.8% | False |

## 对照 sweep（同一段历史）

买跨、买 call、什么都不做，必须和短铁秃鹰跑同一 6 次事件。
没有买卖价就没有权利金数字。不要用中间价补。

| 事件 | 短铁秃鹰 | 买跨 | 买 call | 什么都不做 |
| --- | --- | --- | --- | ---: |
| NVDA:2025-02-26:amc | unscored_missing_quotes | unscored_missing_quotes | unscored_missing_quotes | 0.0 |
| NVDA:2025-05-28:amc | unscored_missing_quotes | unscored_missing_quotes | unscored_missing_quotes | 0.0 |
| NVDA:2025-08-27:amc | unscored_missing_quotes | unscored_missing_quotes | unscored_missing_quotes | 0.0 |
| NVDA:2025-11-19:amc | unscored_missing_quotes | unscored_missing_quotes | unscored_missing_quotes | 0.0 |
| NVDA:2026-02-25:amc | unscored_missing_quotes | unscored_missing_quotes | unscored_missing_quotes | 0.0 |
| NVDA:2026-05-20:amc | unscored_missing_quotes | unscored_missing_quotes | unscored_missing_quotes | 0.0 |

## 这一轮不能说的话

- 不能说「每笔赚 20%」。连一笔费后往返都还没记上。
- 不能把 vendor crush 赢率当成 playbook 已验证。
- 不能把 BTCHOUR 小时盘 clip 达成标准搬过来。

下一步：有人把当时链上的买卖价记进账本，状态变成 `human` 或 `recorded_bid_ask` 之后，才写循环。

