"""Public event-driven option recipes. Not a human tape.

Sources are public practitioner write-ups (tastylive expected-move,
The Option Premium, VolRadar, Volatility Box, FlashAlpha, OIC-style
defined-risk notes). Each recipe is machine-selectable. Undefined-risk
names stay in the catalog so the selector can refuse them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Recipe:
    id: str
    name: str
    legs: int
    family: str
    stance: str
    risk: str
    hold_through_event: bool
    paper_allowed: bool
    role: str
    sources: tuple[str, ...]
    gist: str

    def as_dict(self) -> dict:
        return asdict(self)


RECIPES: tuple[Recipe, ...] = (
    Recipe(
        id="do_nothing",
        name="Stand down",
        legs=0,
        family="none",
        stance="none",
        risk="none",
        hold_through_event=False,
        paper_allowed=True,
        role="default_when_no_edge",
        sources=("equicurious playbook: no edge → stand down",),
        gist="强事件上没有定价优势就空仓。对照基准永远是 $0。",
    ),
    Recipe(
        id="short_iron_condor",
        name="Short iron condor",
        legs=4,
        family="vol",
        stance="short_vol",
        risk="defined",
        hold_through_event=True,
        paper_allowed=True,
        role="default",
        sources=(
            "tastylive: sell premium into binary events, nearest expiry after print",
            "The Option Premium 2026-07-09: IC wings outside expected move, 1–2% capital",
            "Volatility Box: shorts at or outside expected move, $5 wings on $100–$300 names",
            "VolRadar: defined-risk only; they themselves skip inside 7d as a vendor rule",
        ),
        gist="事件前卖定义风险短波动。短行权价放在 ±1.0× 期望波动之外，两翼写死宽度。吃 IV crush，不猜涨跌。",
    ),
    Recipe(
        id="short_iron_fly",
        name="Short iron butterfly",
        legs=4,
        family="vol",
        stance="short_vol",
        risk="defined",
        hold_through_event=True,
        paper_allowed=True,
        role="contrast",
        sources=("tastylive / Volatility Box: tighter cousin of the condor",),
        gist="短跨放在 ATM，两翼放到期望波动附近。权利金更厚，路径更容易撞翼。对照用，不当默认。",
    ),
    Recipe(
        id="put_credit_spread",
        name="Put credit spread",
        legs=2,
        family="vertical",
        stance="short_vol_bullish",
        risk="defined",
        hold_through_event=True,
        paper_allowed=True,
        role="contrast",
        sources=("The Option Premium: 0.20–0.30Δ short put, wing 5–10 strikes, only with a lean",),
        gist="有偏多时才用。NVDA 第一期没有方向优势，只作对照。",
    ),
    Recipe(
        id="call_credit_spread",
        name="Call credit spread",
        legs=2,
        family="vertical",
        stance="short_vol_bearish",
        risk="defined",
        hold_through_event=True,
        paper_allowed=True,
        role="contrast",
        sources=("symmetric to put credit spread",),
        gist="有偏空时才用。第一期不当默认。",
    ),
    Recipe(
        id="reverse_iron_condor",
        name="Reverse iron condor",
        legs=4,
        family="vol",
        stance="long_vol",
        risk="defined",
        hold_through_event=True,
        paper_allowed=True,
        role="alt_when_implied_cheap",
        sources=(
            "tastylive: reverse IC = long vol, defined debit",
            "equicurious / FlashAlpha: buy the move only if implied < typical realized",
        ),
        gist="期望波动明显低于历史实现时，买定义风险长波动。最大亏损是权利金。",
    ),
    Recipe(
        id="long_straddle",
        name="Long ATM straddle",
        legs=2,
        family="vol",
        stance="long_vol",
        risk="defined",
        hold_through_event=True,
        paper_allowed=True,
        role="contrast",
        sources=("FlashAlpha: long straddle when VRP/implied is cheap vs history",),
        gist="买 ATM 跨。IV 已贵时大概率输给 crush。对照必须看见数字。",
    ),
    Recipe(
        id="long_strangle",
        name="Long OTM strangle",
        legs=2,
        family="vol",
        stance="long_vol",
        risk="defined",
        hold_through_event=True,
        paper_allowed=True,
        role="contrast",
        sources=("common long-vol cheaper debit than ATM straddle",),
        gist="比买跨便宜，更要现货真的走远。对照。",
    ),
    Recipe(
        id="long_call",
        name="Long ATM call",
        legs=1,
        family="single",
        stance="directional",
        risk="defined",
        hold_through_event=True,
        paper_allowed=True,
        role="contrast",
        sources=("The Option Premium: retail long calls lose to crush even when direction is right",),
        gist="事件前买单腿 call。方向对了也常亏。对照，禁止当默认。",
    ),
    Recipe(
        id="long_put",
        name="Long ATM put",
        legs=1,
        family="single",
        stance="directional",
        risk="defined",
        hold_through_event=True,
        paper_allowed=True,
        role="contrast",
        sources=("same crush mechanic as long call",),
        gist="事件前买单腿 put。对照。",
    ),
    Recipe(
        id="iv_expansion_exit_before",
        name="Long premium, sell into peak IV",
        legs=1,
        family="single",
        stance="expansion",
        risk="defined",
        hold_through_event=False,
        paper_allowed=True,
        role="alt_pre_event",
        sources=("Ticker Daily: buy ~T−5 at moderate IV, sell T−1 at peak, do not hold the print",),
        gist="吃事件前 IV 膨胀，打印前必须走。不持有过公告。",
    ),
    Recipe(
        id="calendar_short_front",
        name="Calendar (sell event week, buy back)",
        legs=2,
        family="calendar",
        stance="short_front_vol",
        risk="defined",
        hold_through_event=True,
        paper_allowed=True,
        role="contrast",
        sources=(
            "FlashAlpha / Volatility Box: front crushes, back holds; large gap kills both legs",
        ),
        gist="卖事件周、买更远到期。现货钉住行权价才赚。大跳空两边一起坏。对照。",
    ),
    Recipe(
        id="reverse_calendar_exit_before",
        name="Reverse calendar, exit before print",
        legs=2,
        family="calendar",
        stance="expansion",
        risk="defined",
        hold_through_event=False,
        paper_allowed=True,
        role="alt_pre_event",
        sources=("Trading Strategy Guides: buy front / sell back, close before the bell on earnings day",),
        gist="买近卖远，吃期限结构变陡。公告前平掉，不扛 crush。",
    ),
    Recipe(
        id="broken_wing_butterfly",
        name="Broken-wing butterfly",
        legs=3,
        family="vol",
        stance="short_vol_skew",
        risk="defined",
        hold_through_event=True,
        paper_allowed=True,
        role="contrast",
        sources=("public BWB notes: skip one wing to cheapen / zero-debit a fly",),
        gist="铁秃鹰的变体，一边翼更宽。定义风险。第一期只对照。",
    ),
    Recipe(
        id="short_strangle",
        name="Naked short strangle",
        legs=2,
        family="vol",
        stance="short_vol",
        risk="undefined",
        hold_through_event=True,
        paper_allowed=False,
        role="forbidden",
        sources=("The Option Premium: only if you can eat 5× credit; convert to IC otherwise",),
        gist="裸卖跨。第一期禁止。",
    ),
    Recipe(
        id="short_straddle",
        name="Naked short straddle",
        legs=2,
        family="vol",
        stance="short_vol",
        risk="undefined",
        hold_through_event=True,
        paper_allowed=False,
        role="forbidden",
        sources=("undefined gap risk through a strong event",),
        gist="裸卖跨式。第一期禁止。",
    ),
    Recipe(
        id="jade_lizard",
        name="Jade lizard",
        legs=3,
        family="vol",
        stance="short_vol_skew",
        risk="undefined",
        hold_through_event=True,
        paper_allowed=False,
        role="forbidden",
        sources=("tasty: short put + short call spread; upside defined, downside naked",),
        gist="下行是裸卖权。第一期禁止。",
    ),
    Recipe(
        id="covered_call",
        name="Covered call",
        legs=1,
        family="single",
        stance="stock_overlay",
        risk="stock_required",
        hold_through_event=True,
        paper_allowed=False,
        role="observe",
        sources=("needs long stock; not an options-only book",),
        gist="要底仓股票。观察，不进第一期纸盘。",
    ),
)


def recipe(recipe_id: str) -> Recipe:
    for item in RECIPES:
        if item.id == recipe_id:
            return item
    raise KeyError(recipe_id)


def allowed_paper() -> tuple[Recipe, ...]:
    return tuple(item for item in RECIPES if item.paper_allowed)


def forbidden() -> tuple[Recipe, ...]:
    return tuple(item for item in RECIPES if item.role == "forbidden")


def by_id() -> dict[str, Recipe]:
    return {item.id: item for item in RECIPES}
