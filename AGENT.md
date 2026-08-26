# 给下一个 agent 的检查清单

仓库：`github.com/huhuhulululu/KOP`  
默认分支：`main`  
纸盘：只要模拟成交。`ALLOW_LIVE = false`。`AUTO_TRADE = false`。

## 开仓时必须对齐

1. **数据从哪来**
   - 现货日线：Yahoo chart（公开）。
   - 期权链 / IV / delta：CBOE delayed quotes（公开，15 分钟延迟）。有 bid/ask/iv/delta。
   - 没有券商账号，没有期权交易权限，没有历史期权链。
   - 没有 Kalshi，也不要去接。
2. **第一期只做** NVDA 财报、定义风险短波动（`nvda_earnings_defined_short_vol`）。
   观察名单里还有 TSLA / AAPL / MSFT / AMZN，不要并行写策略。
3. **金带子**：主人还没有把自己的历史成交贴进来。回放了最近 6 次 NVDA 财报的现货路径，权利金进/出是 `missing_quotes`。
   这些行 **不算** 可重复人工样本。
4. **单笔风险**：纸盘上限 **$500**。不允许保证金裸卖权。`NAKED_SHORTS = false`。
5. **不要改 BTCHOUR，不要接 Kalshi。** 分仓、分 sqlite（`data/kop.sqlite`）、分 loop。

## 现在做到哪

- 拉链、拉财报日历、记账：有。
- 回放 6 次 NVDA 财报：有现货路径，没有历史买卖价，所以没有往返盈亏。
- playbook + 单测：有。门写死，循环关着。
- 自动下单：没有。`kop paper-once` 会记拒绝原因然后退出。

## 下一周不要做的

- 不要五只股票一起开打。
- 不要事件前买裸 call/put。
- 不要用中间价补历史权利金。
- 不要把 VolRadar / ORATS 的 crush 赢率写成「策略已验证」。
- 不要把 BTCHOUR 的 11/5/−3.03 或 25¢ coupon 当达成标准。
- 没有至少 4 笔 `human` / `recorded_bid_ask` 之前，不要开策略循环。

## 有历史成交时

把当时买卖价（不要中间价）记进账本，`fill_status=human`，字段对齐 `catalog/research/nvda_earnings_tape.md`。
再谈纸盘循环。再谈第二只股票。
