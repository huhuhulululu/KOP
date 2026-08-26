# KOP

Known-event Options Paper。用**上市期权**做已知事件（先做财报波动，不猜涨跌）。

不是 Kalshi 小时盘，不是「收盘是否高于 X」的二元合约，也不是把 BTCHOUR 的 25¢ coupon 搬到股票上。

GitHub 仓库简介如果还写着 `kalshi options`，那是开仓占位，**以这份说明为准**。

## 一句话

事件前隐含波动常被买贵。第一期只测：英伟达财报上，**定义风险短波动**卖不卖得走。没有信息优势。

## 不要做的事

- 不要复用 `github.com/huhuhulululu/BTCHOUR` 的 ticker / impulse / 25¢ rest / KXBTCD 逻辑。
- 不要五只股票 × 所有事件一起开打。
- 不要事件前买裸 call/put 赌方向。
- 不要 Kalshi / Polymarket 二元合约冒充期权。
- 不要说「每笔赚 20%」。计分可以留 `EV = p·b − (1−p)`，兑现看往返和路径。
- 不要和 BTCHOUR 共库、共 sqlite、共 loop。
- 没有人工带子之前，不要开自动下单（纸盘也不要乱扫链下单）。

## 第一期 playbook

`nvda_earnings_defined_short_vol` — 门写死在 `kop/config.py` 和 `catalog/rules/playbook.md`。

## 命令

```bash
python3 -m kop calendar
python3 -m kop chain
python3 -m kop observe      # 拉链、记账、给门，不成交
python3 -m kop replay       # 最近 6 次 NVDA 财报现货路径
python3 -m kop tape
python3 -m kop sweep        # 同一段历史上的买跨 / 买 call / 什么都不做
python3 -m kop status
python3 -m kop paper-once   # 拒绝：没有带子，AUTO_TRADE=false
python3 -m unittest discover -s tests -q
```

成交规则：卖出 `bid − 0.05`，买入 `ask + 0.05`，乘数 100，费 $0.65/张，最大亏损写死 $500。

## 数据

| 需要 | 现在用的 |
| --- | --- |
| 期权链 + 报价 | CBOE delayed（bid/ask/IV/delta） |
| 财报日历 | 种子日期 + Yahoo calendarEvents |
| Greeks / IV | CBOE；IV rank 先用 iv30 相对 1 年高低，样本够了再改百分位 |
| 纸盘账本 | `data/kop.sqlite`（不是 btchour.sqlite） |

没有历史期权链 API key。所以回放表能填现货路径，**不能编权利金**。

## 和 BTCHOUR 的关系

旧仓：`github.com/huhuhulululu/BTCHOUR` 分支 `cursor/kalshi-btc-hourly-4882`，PR #1。  
那是 Kalshi BTC 小时盘 coupon。达成标准不能搬过来。

期权仓的达成 = 纸盘打出类似人工事件单的**定义风险路径**，不是回放变绿，不是小时盘 clip。
