# nvda_earnings_defined_short_vol

写死。要改数字就开新 playbook 名字，不要事后改这一条去凑绿。

| 门 | 值 |
| --- | --- |
| 标的 | NVDA 上市期权 only |
| 事件 | 财报 AMC |
| 进场 | 事件前 2–5 个交易日（默认 T−3） |
| 出场 | 权利金收到 50%，或财报后 1 个交易日，先到先走 |
| 结构 | 短铁秃鹰，两翼各 $5，1 张 |
| 单笔风险 | 最大亏损 ≤ $500（宽度 − 权利金 + 费） |
| IV | `iv_percentile` ≥ 50；样本不足 60 日时用 CBOE `iv30` 相对 1 年高低的 range rank，同一阈值 50 |
| 成交 | 卖出用 bid−$0.05，买入用 ask+$0.05，从不用中间价 |
| 费 | $0.65 / 张 / 边，乘数 100 |
| 禁止 | 事件前买 call/put；裸卖；盘中追跳空；同一事件加仓翻方向；保证金裸卖权 |
| 循环 | 至少 4 笔 `human` 或 `recorded_bid_ask` 带子 + `AUTO_TRADE=false` 仍然关着 |

对照（同一 6 次财报，开/关变体，不改门）：

- 短铁秃鹰（本 playbook）
- 买跨
- 买 call
- 什么都不做 = $0

计分可以留 `EV = p·b − (1−p)`。兑现只看往返和路径。

不要从 BTCHOUR 抄：impulse、$100、YES/NO 25¢、KXBTCD、flex / lock_wait / dump_gap、Kalshi。
