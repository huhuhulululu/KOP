# 数据接口

免费先用到能挡单。付费只为一样东西：历史期权 **bid/ask**，好记美元带子。没有 key 就不编中间价。

## 现在已经在用（免费，无 key）

| 源 | URL / 模块 | 拿什么 | 进哪道门 |
| --- | --- | --- | --- |
| CBOE delayed chain | `cdn.cboe.com/api/global/delayed_quotes/options/NVDA.json` | bid/ask/iv/delta/OI/volume，约 15 分钟延迟 | implied、期限、RR、价差、OI、拟建 IC |
| CBOE iv30 年高低 | `.../historical_data/NVDA.json` | iv30 annual high/low | range rank |
| CBOE 指数 | `.../quotes/_VIX.json`（以及 `_VIX9D` `_VIX3M`） | 现货 VIX | INFO |
| Yahoo chart | `query1.finance.yahoo.com/v8/finance/chart/NVDA` | 日 OHLC | HV20/HV60、交易日、回放路径 |
| FRED | `fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS` | VIX 日序列 | VIX 1y 百分位（INFO） |
| 种子财报日 | `kop/calendar.py` | NVDA AMC 日期 | 窗口 |

探过、**不要再试** 的：

- Yahoo `v7/finance/options`、`quoteSummary` → 401
- CBOE `us_indices/daily_prices/VIX.json` → 403（用 delayed quotes + FRED）
- Stooq → JS 墙

Nasdaq 期权链 JSON 能开，但比 CBOE 少希腊值，不并行拉。

## 值得稍微付钱的（按用处）

带子上最大的洞是：**六次财报没有当时的买卖价**，所以没有费后盈亏。下面三家里，先买能补这个洞的。

| 源 | 大概价（2026 中公开标价，下单前再核） | 能补什么 | 值不值 |
| --- | --- | --- | --- |
| **Polygon / Massive options** | Starter ~$29/月（15 分钟延迟，2 年）；Developer ~$79/月（4 年） | 合约日线/分钟聚合，能回放 T−3 的 bid/ask | **最值。** 设 `POLYGON_API_KEY` 后 `kop.market.paid.polygon_option_daily` 会真拉，不编 |
| **ThetaData** | Value ~$40/月；Standard ~$80/月（tick + 更长历史）。要本机 terminal `127.0.0.1:25510` | 历史 NBBO，按根+到期批量 | 要做 tick 级滑点再上。云代理里不好跑 terminal，所以**没有空壳客户端** |
| **ORATS** | 大约 $99/月，有试用 | 财报 implied vs actual、crush | 比 leave-one-out 中位数更干净的 implied。有 `ORATS_API_KEY` 再接，现在不当门 |
| **Tradier** | 开户后数据常免费；纯数据大约 $10/月。沙盒可先跑 | 延迟报价 + 以后纸/真下单 | 设 `TRADIER_TOKEN`（沙盒再加 `TRADIER_SANDBOX=1`）。现在只报价，不下单 |

不买：Unusual Whales 流向、SpotGamma/FlashAlpha 的 GEX 仪表。那是叙事，不是本仓的定义风险门。

## 环境变量（可选，不挡搭建）

```
POLYGON_API_KEY=
TRADIER_TOKEN=
TRADIER_SANDBOX=1
ORATS_API_KEY=
```

`kop snapshot` 的 `paid_configured` 会列出已配置的源。一个都没有也可以跑现场门：CBOE 已经有今天的买卖价。付费只为**过去**六次事件的权利金。
