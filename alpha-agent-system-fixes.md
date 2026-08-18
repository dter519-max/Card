# Alpha Agent System — Bug Fixes Changelog

参考文件:`App.jsx`(已修复版本,随本文档一起附上)

---

## 1. 查福位带入计算器时,Hall 被错误覆盖

**现象**:从"查福位"点选 LC1-07-108,进入计算器后 Hall 却变成了 A2,价钱也跟着错。

**原因**:`SingleQuoteView` 里有个 `useEffect`,只要 `code` 变化就会重新用 `AVAIL.find()` 按编号查一次。但 Block L 里同一个编号(如 "07-108")会出现在多个不同 Hall 下(A2、C1 各有一个)。组件刚挂载、code 从 prefill 带入时也会触发这个 effect,`.find()` 只认数组里第一个匹配——顺序排在前面的 Hall(如 A2)就把正确的 C1 覆盖掉了。

**修复**:
- 加一个 `useRef` 标记,首次挂载且 prefill 已经带有完整 hallcode 时,跳过这次自动查找,不覆盖。
- 如果同一编号在同一 Block 里确实对应多个 Hall,输入框下方会显示橙色提示,提醒手动核对。

```js
const skippedPrefillAutoFill = useRef(false);
const [ambiguousCode, setAmbiguousCode] = useState(false);

useEffect(() => {
  if (!skippedPrefillAutoFill.current && prefill?.hallcode && code === prefill.code) {
    skippedPrefillAutoFill.current = true;
    return;
  }
  skippedPrefillAutoFill.current = true;

  if (!code.trim()) { setAmbiguousCode(false); return; }
  const matches = AVAIL.filter((r) => r.code.toLowerCase() === code.trim().toLowerCase() && (!block || r.block === block));
  setAmbiguousCode(matches.length > 1);
  const hit = matches[0];
  if (hit) {
    setBlock(hit.block); setHallcode(hit.hallcode); setSide(hit.side); setLevel(hit.level);
  }
}, [code]);
```

（别忘了 `import { useState, useEffect, useMemo, useRef } from "react";` 要把 `useRef` 加进去——我们第一版就是漏了这个 import 才报 `Can't find variable: useRef` 的错。）

---

## 2. 所有计算永远要用「促销价 Promo Price」,不是「原价 Actual Price」

**现象**:计算器里"原价"这格数字没错,但现金回扣、净价、头期、月供全部拿"原价"去算,而不是价格表里的"推介价"。

**规则确认**(客户原话):"上面可以写原价,但是永远什么都好,都是要用 Promo Price"——即:
- 顶部展示可以同时列出原价(参考用),
- 但现金回扣级距判断、净价、头期、供期、月供,一律以 **推介价 Promo Price** 为计算基础。

**修复**(`SingleQuoteView` 与 `MultiQuoteView` 都改了):

```js
const priceInfo = hallcode && side && level ? lookupPrice(block, hallcode, side, level) : null;
// 原价只做展示参考;以下所有计算都用推介价
const actualPrice = priceInfo ? (isDouble ? priceInfo.doubleActual : priceInfo.singleActual) : null;
const basePrice = priceInfo ? (isDouble ? priceInfo.doublePromo : priceInfo.singlePromo) : null;

const eligible = REBATE_ELIGIBLE_BLOCKS.includes(block);
const rebate40 = basePrice != null && eligible ? getRebate(basePrice, isDouble, "40") : 0;
const netPrice40 = basePrice != null ? basePrice - rebate40 : null;
const plan = netPrice40 != null ? computeInstallment(netPrice40) : null;
```

界面上也加了单独一行「促销价 Promo Price(以此价格计算)」,跟「原价 Actual Price」分开显示,避免 agent 混淆。

**验证案例**:LC1-07-108,Level 7,双人
| 项目 | 数值 |
|---|---|
| 原价(参考) | RM40,880 |
| 促销价(计算基础) | RM27,880 |
| 现金回扣 40% | -RM1,500 |
| 净价 | RM26,380 |
| 头期 | RM10,900 |
| 供期 | 36 个月 |
| 月供 | RM430/月 |

---

## 3. Block L 楼层示意图方位错误

**规则确认**(客户原话 + Block L Ground Floor Plan 对照):
- **LC1 / LB1 / LA1** = Frontage(正面,临主通道)
- **LB2** = Left 左(Hall B 靠近 Hall A 那一侧)
- **LB3** = Right 右(Hall B 靠近 Hall C 那一侧)
- 其余所有柱位(A2/A3/A6-12、C2/C3/C6-12)= 内部柱位,**没有**方位区分

这跟价格表分组(`A1_C1` / `A2_3_6-12_C2_3_6-12` / `B2_B3` / `B1`)完全吻合,说明公司价格分级本来就是照这个方位规则做的。

**修复**:`MiniFloorPlan` 组件拆出共用的 `HallDiagram` SVG,针对 `block === "L"` 单独判断:

```js
const BLOCK_L_FRONTAGE_HALLS = ["A1", "C1", "B1"];
const BLOCK_L_RIGHT_HALL = "B3"; // 靠近 Hall C
const BLOCK_L_LEFT_HALL = "B2"; // 靠近 Hall A

function MiniFloorPlan({ block, side, hallcode }) {
  if (block === "L") {
    if (BLOCK_L_FRONTAGE_HALLS.includes(hallcode)) {
      return <HallDiagram highlightF footerLabel={`L${hallcode} · 正面 Frontage(临主通道)`} />;
    }
    if (hallcode === BLOCK_L_RIGHT_HALL) {
      return <HallDiagram highlightR footerLabel="LB3 · Right 右(Hall B 靠近 Hall C 那一侧)" />;
    }
    if (hallcode === BLOCK_L_LEFT_HALL) {
      return <HallDiagram highlightL footerLabel="LB2 · Left 左(Hall B 靠近 Hall A 那一侧)" />;
    }
    return ( /* 内部柱位,无方位区分 的文字提示 */ );
  }
  // ...其余 Block 逻辑不变
}
```

调用处记得把 `block` 传进去:`<MiniFloorPlan block={block} side={side} hallcode={hallcode} />`

---

## 4. 查福位多选时,勾选会「连坐」到其他卡片

**现象**:同一个 Block 里,不同 Hall 但编号相同的两张卡片(如 F座 Hall F5 的 07-108 和 Hall F7 的 07-108),勾一个另一个也会跟着显示打勾。

**原因**:`SearchScreen` 里判断"是否已选中"用的 key 只算了 `block + code`:

```js
const keyOf = (r) => `${r.block}-${r.code}`;   // 有问题
```

同一 Block 里编号会跨 Hall 重复,导致两个不同的福位被当成同一个。

**修复**:把 Hall、朝向、楼层都算进 key 里,确保每个福位有唯一身份:

```js
const keyOf = (r) => `${r.block}-${r.hallcode}-${r.side}-${r.level}-${r.code}`;
```

---

## 遗留 / 建议后续检查项

- 上面第 4 点这种「同一 Block 编号跨 Hall 重复」的情况,除了影响多选勾选,理论上也可能影响别处任何用 `code` 单独当 key 或做匹配的地方——建议在 Claude Code 里全局搜一次 `.code` 相关的比对/key 逻辑,确认没有漏网的。
- 第 1 点的「编号模糊(ambiguousCode)」提示目前只在 `SingleQuoteView` 里做了;`SearchScreen` 的结果列表本身没有这个问题(因为它是直接列出所有匹配项,不需要去重猜测),但如果之后要加"直接输入编号跳转"这类功能,要小心同样的坑。
- 现金回扣的级距判断(`getRebate` 里 >35000/>25000/>15000)目前是用促销价去判断,如果这个门槛在原始促销文件里其实是按「原价」定的,需要跟主管确认一下这个假设是否成立。
