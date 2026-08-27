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
- 不要等人贴单。带子 = 公开配方 + 回放。自动下单仍然关着。

## 第一期 playbook

`nvda_earnings_defined_short_vol` — 门写死在 `kop/config.py` 和 `catalog/rules/playbook.md`。

## 命令

```bash
python3 -m kop calendar
python3 -m kop chain
python3 -m kop snapshot     # 每道门的值 / GATE|INFO / 过没过；不成交
python3 -m kop observe      # 拉链、记账、给门，不成交
python3 -m kop recipes      # 公开单腿/多腿目录
python3 -m kop select       # 等同 snapshot：现场规则选配方，不成交
python3 -m kop replay       # 最近 6 次 NVDA 财报现货路径
python3 -m kop tape
python3 -m kop sweep        # 同一段历史上给每条配方打路径分
python3 -m kop status
python3 -m kop paper-once   # 选出配方；不成交到券商
python3 -m kop day          # 日更：盯市 / 平仓 / 门全开才记纸盘成交；券商锁着
python3 -m kop phase1       # 每月 $500 记分板和算术
python3 -m kop book
python3 -m kop pnl
python3 -m unittest discover -s tests -q
```

成交规则：卖出 `bid − 0.05`，买入 `ask + 0.05`，乘数 100，费 $0.65/张，最大亏损写死 $500。

## 数据

| 需要 | 现在用的 |
| --- | --- |
| 期权链 + 报价 | CBOE delayed（bid/ask/IV/delta/OI） |
| 实现波动 / 日历 | Yahoo chart 日线 → HV20/HV60、交易日 |
| 指数波动 | CBOE `_VIX` + FRED `VIXCLS`（INFO，不挡单） |
| 财报日历 | 种子日期 + Yahoo calendarEvents |
| IV rank | CBOE iv30 相对 1 年高低；样本够了改百分位 |
| 纸盘账本 | `data/kop.sqlite`（不是 btchour.sqlite） |

没有历史期权链 API key。所以回放表能填现货路径，**不能编权利金**。
公开配方的对照打的是路径是否帮论文，见 `catalog/public/structures.md`。
每道门的公式和源见 `catalog/public/indicators.md`，接口清单见 `catalog/public/data_sources.md`。

值得付的：Polygon/Massive options（约 $29–79/月）或 ThetaData，用来补六次财报当天的 bid/ask。设 `POLYGON_API_KEY` 才会去拉。第一阶段**先不订阅**。从今往后的成交用 CBOE 延迟买卖价记纸盘。

第一阶段目标每月 $500 是记分板。现在这套 1 张 NVDA 财报铁秃鹰就算从没亏过大约 $42/月，路径 2/6，EV 为负。算术见 `catalog/rules/phase1.md`。不靠加张数凑。

## 和 BTCHOUR 的关系

旧仓：`github.com/huhuhulululu/BTCHOUR` 分支 `cursor/kalshi-btc-hourly-4882`，PR #1。  
那是 Kalshi BTC 小时盘 coupon。达成标准不能搬过来。

期权仓的达成 = 纸盘打出类似人工事件单的**定义风险路径**，不是回放变绿，不是小时盘 clip。
