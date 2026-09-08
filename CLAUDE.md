# Alpha Agent System — 项目须知

甲板山庄 Jiangnan Villa / Papan Memorial 的销售系统。给销售代理用的：查空置骨灰位
（niche）和土葬位（burial plot）、看格子图、算价钱。

**工作分支是 `claude/new-session-h1gdy9`，不是 `main`。**

## 命令

```bash
npm install
npm run build      # -> dist/index.html（单一自包含文件）
npm run preview    # http://127.0.0.1:4173 本机预览
npm run deploy     # build + surge dist alphaagentsystem.surge.sh
```

线上：https://alphaagentsystem.surge.sh

## 架构

整个 app 就是 `App.jsx` 一个文件（~800KB），其中约 95% 是内嵌的真实库存资料。
打包后是**一个 HTML 文件**，CSS/JS/图标全内嵌，丢到任何静态托管即可，没有后端。

写代码时注意几点：

- **别让 Tailwind 直接扫 `App.jsx`**。那些资料是单行超长字符串，Tailwind 的扫描器会
  100% CPU 卡死。`scripts/build.mjs` 会先把 className 抽到 `.tailwind-classes.txt`，
  Tailwind 只扫那个（~200ms）。
- **别用 `execFileSync` 调 `npx`/任何 `.cmd`**。用户在 Windows，Node 会报
  `spawnSync npx.cmd EINVAL`。Tailwind 现在是在 Node 里经 PostCSS 跑的，不起子进程。
- 编辑 `App.jsx` 时用 Edit 而不是整份 Write，文件太大。读也要用 offset/limit 分段读。
- **贴着屏幕边缘的东西要自己补 `env(safe-area-inset-*)`**。`build.mjs` 的 viewport 是
  `viewport-fit=cover`，页面会一路画到状态栏和 home indicator 底下 —— 顶栏和底部 tab bar
  必须各自把那条留白 padding 回来，否则那两条就是透的，正在滚的内容会从上下两头露出来
  （手机上看就是「上下镂空」）。没有 inset 的装置上 `env()` 是 0，样子不变。
- **别用 `100vh`，用 `.app-vh`**（`min-height:100vh` 打底 + `100dvh`）。iOS Safari 的
  `100vh` 是按工具栏收起来时的高度算的，工具栏还在的时候页面就比屏幕高一截，整个版面会往
  浏览器 chrome 底下漂。

## 资料从哪来

价格、现金回扣、头期/供期：公司的价目表 PDF。
空置/已售状态：公司导出的「福位楼层图 / 位子图」PDF —— 是**原生 Excel 导出**（不是扫描件），
所以文字和单元格底色都能用 PyMuPDF 程序化读取：**黄色 = 已售，白色/无填色 = 空置**，
编号前带 `*` = Reserve Unit。

资料是**快照不是实时**（`NICHE_STATUS_UPDATED` / `BURIAL_STATUS_UPDATED`），每天都有成交。
用户会不定期传新的导出 PDF 来更新。

更新资料有两支脚本，骨灰位和土葬各一支。别再从头写解析器 —— 下面每个坑都已经修在
里面了，重写一次就会重踩一次：

```bash
pip install pymupdf
python3 scripts/update_niche_data.py  "Niche Floor Plan (xxxxxxxx).pdf"    # 骨灰位
python3 scripts/update_burial_data.py "Burial Floor Plan (xxxxxxxx).pdf"   # 土葬
python3 scripts/update_niche_data.py plan.pdf --check                       # 只解析+验证
```

两支都会自己读出图纸日期、跑验证，验证不过就拒绝写入 App.jsx。

### 骨灰位 `update_niche_data.py`

「同一面墙出现重复编号」= 解析错了（会失败）；「同一个编号出现在两面墙」= 图纸自己印重复
（只警告，照实保留，别自作主张改）。

解析要注意的坑（都踩过）：
- 一个 Hall 的 R/F/L 三个侧翼是**并排**的，每行会重复出现多个层号 token，
  逐行收集时必须在下一个层号处停，否则会把隔壁侧翼的编号吃进来、朝向标错。
- 侧翼/区段的表头是**整排一次出现在数据之前**的，用单一「当前侧翼」变量会被最后一个覆盖。
  要按 x 坐标建锚点，再把每行按最近的 x 归属。
- Ground/First Floor 那几页的 block 字母是跟中文名黏在一个 token 里的（如 `K（聖寶院）-`），
  而且可能跟 `BLOCK` 这个词不在同一行 —— 直接取「BLOCK 后面那个词」会拿到 `GROUND` 而误判成 G 座。
- 同一行的格子 y 座标有次像素抖动（322.7 / 323.1）。**分行必须用聚类，不能把 y 硬套到固定格**，
  否则边界刚好卡在中间时，落到隔壁 band 的格子会排到下一个区段的行号后面，被吃进隔壁区段。
- 有些墙中间是**真的有空格**（L 座每个区段都有，B1 的 R 面少一个 0210）。那个空格是用来
  对齐两边的，不能收掉 —— 收掉的话后面每个编号都会往左移一位。所以格子要按栏位座标摆，
  空的就留空。
- **单/双位（S/D）印在 LEVEL 表头那一行**，一个栏位一个，不是逐格标的 —— 也就是说
  单双是**整栏**的属性。收集时要从 LEVEL 那个 token 往右扫到下一个 LEVEL 为止（并排的墙
  共用同一行），每一格再按最近的 x 认领自己的标记。存成 `cell.u`（"D"/"S"），
  同时也写进 `AVAIL_RAW` 第 6 栏。
  验证方法很好用：价目表自己印了 "TOTAL UNIT : DOUBLE = x, SINGLE = y"，
  能跟解析结果对（F 座地面 200/930、F 座一楼 80/990、N2 36/153，2026-09 三个都精准吻合）。
  注意 `cell.s` 的 "S" 是 Sold，`cell.u` 的 "S" 是 Single —— 两个不同栏位，别搞混。

改完资料务必抽样跟旧数据对一遍（A/B/C/D 座当年是完全吻合的，Block N 的总数能跟表格
自己印的 "TOTAL UNIT" 对上），别解析完就直接信。

### 土葬 `update_burial_data.py`

土葬图纸排版比骨灰位简单太多：一页一个 Zone，一个行号一排位子，没有并排的墙面。
但还是有几个坑：

- **底色是整段画的**，不是一格一格 —— 一个黄色矩形会盖住连续好几个已售位子。所以判断
  某一格的状态，是看它的文字落在哪个矩形里，不能指望它有自己的矩形。
- **行的分隔线也是「填色矩形」**，只是被压到 0.4 点高。不排掉的话，靠近线的位子会读成黑色。
  脚本用「高/宽 < 2 点就跳过」挡掉。
- **`*`（Reserve Unit）有两种写法**：多数是独立一个 token 贴在编号左边（间距不到 1 点），
  但 exporter 偶尔会黏成一个 token（`*DA-13-118`）。两种都要认 —— 当年手工整理就是漏了
  黏在一起的那两个，DA 的 13 行少了 `DA-13-118` / `DA-13-128`。
- **行号在左边空白处，且比自己那排编号低 2~3 点**。所以位子归行要用「垂直距离最近的行号」，
  不能用固定 y 分带。各行还是左右错开的（阶梯状），x 完全不能用来分行。
- **DB 那一页的第 13 行是另一种产品**（编号前缀 `DBS-`，尺寸和价钱都不同），
  在 app 里是独立的 zone key `DB13`。靠编号前缀分，不是靠行号。
- **行的顺序照图纸由上到下排，不是照数字大小排**。Zone B 的 1A/1B 印在 1 上面；
  Imperial Zone 整个是倒过来印的（由上到下是 3A, 3, 2, 1）。跟着图纸走。
- 中式编号跳过 4 和 5，用 `A`/`B` 顶上 —— 行号和位子号**两段都会出现** A/B
  （行 3A/3B/13A/13B，位子 A8/B8/1A8/A08）。正则不能只吃数字。

验证方法跟骨灰位一样：先拿旧图纸跑一遍，看能不能重现 App.jsx 里现有的资料。
2026-09 那次比对，1310 格里只有上面说的 DA 两格和 Imperial 的行序两处不同，其余全中。

## 产品资料从哪来（不是我编的）

「产品资料 Knowledge」和「FSP 配套」两页的内容，全部来自公司自己的销售资料，不要凭常识补：

- 车程 → `PMB Photos/Location Map.png`（看板上印的）
- 九个「最」、园区设施与景观 → `Business Kits/甲板山庄景点与设施 - Jan22.pdf`
- 信托基金／维护费 → `ALPHA Trust fund.pdf`
- FSP 圆满契约 → **2025 那份**（`fsp_alpha_team_2025.pdf`）。Drive 里还有一份 Jan22 的，
  价钱不同，**别用旧的**。
- 星洲日报摄影比赛得奖名单 → `PMB Photos/甲板得奖作品 watermark/`（档名就是奖项＋姓名＋州属）

**这些 PDF 的文字层不可信，价格一定要转成图自己看过再写。** 已经踩过两次：
FSP 2025 的两张汇总页，文字层把期数栏位顺序读反了（印的是 48/48/60/60，读出来是
60/60/48/48；另一页印 36/48/48，读出来 48/36/48）——照文字层写就会把月供配错配套。
Trust Fund 那张更糟，三个表格被压成一串没有分隔的数字。

空置数量一律从 `NICHE_AVAIL` / `BURIAL_AVAIL` 现算，不要写死在文案里。

### 园区导览的照片

「园区导览 Park Guide」的照片**没有打包进 app**，是用 Drive 的 file id 直接从
`https://drive.google.com/thumbnail?id=<id>&sz=w<宽>` 读的。原图一张 5–160MB，
内嵌进单一 HTML 会直接把 app 撑死。这招能用是因为那些档案的分享权限是
**「知道连结的任何人」**（`get_file_permissions` 查出来是 `anyone: reader`）——
公司哪天把分享关掉，图就读不到了，所以每张图都有 `onError` 退回「载入不到」，
每个卡片底下也留了 Drive 资料夹连结。也因此**看照片需要网络**，app 其他功能不用。

> 这个沙箱连不到 `drive.google.com`（跟 surge 一样被挡），所以我**没办法在这边真的看到图**。
> URL 格式和分享权限都验过了，但第一次上线后请在手机上自己开一次确认。

中文座名（慈慧阁／静宁阁／…）是从**福位楼层图 PDF** 的页首抓的
（`(慈慧閣）- BLOCK A NICHE NUMBERING`），不是自己编的。

跟园区分布图看板（`PMB Photos/江南古镇分布图.jpg`）逐个座对过，结论**不是「两份完全对不上」**
（我第一次拿低清图看，读错了字，写了这个结论，后来用高清图推翻）：

| | 楼层图 | 看板 | 状态 |
|---|---|---|---|
| A B C D E F G | 慈慧阁 静宁阁 三善院 百孝阁 怀德院 朝阳阁 清宁院 | **一模一样** | A/B/C 用户另外确认过 |
| M | 三福院 | 善福院 | **用户确认用「善福院」**，楼层图那个不要用 |
| K | 圣宝院 | 盛宝殿 | 还没确认 |
| L | 存孝院 | 忠孝院 | 还没确认 |
| N | 德阳院 | 三合院 | 还没确认 |
| P | 竹林阁 | 四合院 | 还没确认 |

M 是 2026-09 用户直接讲的（我自己看图那个字读不出来）—— **用户讲的优先于 PDF**。
剩下 K/L/N/P 四个 app 里两个名字都列出来，叫业务去跟公司确认。
看板本身也放进 app 了（Drive id `1YZ8huM7Fhe6V8ZZHT8N20oXGjvtVYb4A`），点了放大自己看。

看板全文（2026-09 用高清版逐个放大读的，A–W 全部）：

```
A BLOCK A 慈慧閣    B BLOCK B 靜寧閣    C BLOCK C 三善院    D BLOCK D 百孝閣
E BLOCK E 懷德院    F BLOCK F 朝陽閣    G BLOCK G 清寧院    H BLOCK H 光明殿
I TEMPLE 善福堂     J TEMPLE 普航殿     K BLOCK K 盛寶殿    L BLOCK L 忠孝院
M BLOCK M 善福院    N BLOCK N 三合院    O CREMATORIUM 聖陽館  P 四合院
Q WATERFALL 瀑布    R 湖上石雕四面觀音   S 聚寶湖            T CHAPEL 教堂
U 佛祖与佛塔        V FAMILY LOT 家族墓園  W WASH ROOM 軒雨廳
```

> **踩过两次的坑：低清图上的中文字不能信。** 同一块看板，我在低清版上把 A 读成「慕義閣」、
> 把 P 读成「西合院」、还以为 K 两份一样 —— 三个都是错的。
> 方法：整块板是转 90° 的，`Image.rotate(90, expand=True)` 转正，再 crop + LANCZOS 放大。
> **放大后还是糊的就是分辨率不够，去要高清版，不要猜。**

K 座和 P 座 Drive 里没有照片资料夹；看板上有个 Block H，楼层图和价目表都没有，没有列进去。

设施的名字也是用户讲了算：看板印「WASHROOM 軒雨閣」，用户说**叫「洗手间」就好，另外那个名字不要理**，
所以「軒雨閣」在 app 里**一个字都不出现**（测试有守住这点）。Drive 里也没有洗手间的照片，就空着。

## 已知缺口（照实记录，不要编造补齐）

- **E 座和 N 座的价目表把 3B 层写成「Level 5」**。12 个座里只有这两个自己跟自己对不上：图纸写 3B，
  价目表在同一个位置（6 跟 3A 中间）写 5，其余 10 个座两份文件一致。**已回原始 PDF 核对过，
  不是转录错误**——E 座（原生 PDF）和 N 座（扫描件，已转图目视确认）印的确实是 5。
  几乎肯定是同一层的两种写法，但**没有自作主张套上去** —— 报价是真金白银，计算器会明说这件事
  让业务去跟主管确认。影响 6 个空置格（E 座 5 个、N 座 1 个）。公司确认后改 `HALL_GROUP` / `PRICING` 即可。

> Block F 地面层（F1/F2/F3）以前记成「公司没给价格表」，**其实一直在 Drive 的 Niches Pricing List
> 里**（`Blk F Price List (Gr. Flr) - 010422.pdf`）。2026-09 已解析写入，185 个空置格现在算得出价。
> 教训：说「公司没给」之前，先把 `Niches Pricing List` 资料夹整个列一遍。
- **信托基金／维护费是另外收的**，不含在福位价里 —— 计算器算出来的数字少了这一笔
  （骨灰位 RM1,700–4,800、土葬 RM5,000–20,000）。那张表上**没有 K 座**，也没有 Zone A/AS/B。
- FSP 2025 那份的 EPP 促销期是 01.07.2025–30.09.2025，**已经过期**；app 里有写明。
- Block M 全部售罄
- Zone A/AS 没有土葬位子图
- 少数格子被价格分类色（如 Special View）盖住看不出空/售 → 标「待确认」

## 登入 / 账号

`ADMIN_EMAIL` / `ADMIN_DEFAULT_PASSWORD` 在 `App.jsx` 里播种管理员账号，
密码存 salted SHA-256（`crypto.subtle`，file:// 下退回字符串 hash）。
管理员能开/删账号、重设密码、升降权限；一般用户只能改自己密码。

> **这是「软门」，不是访问控制，跟用户沟通时别说成是资料保护。**
> 纯前端、无后端，验证在访客浏览器里跑，开 DevTools 就能绕过去读到价格和库存。
> 账号存 localStorage，因此是**按设备**的，换设备要重开。
> 要真正保护得改成有后端的架构（资料放服务器，验证通过才下发）。

## 用户

用户是中文使用者（马来西亚），用中文沟通。不太熟悉命令行 —— 给步骤要具体到
可以直接复制粘贴，别假设他知道 cd / 环境变量这些。
