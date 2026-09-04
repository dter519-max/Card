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

## 已知缺口（照实记录，不要编造补齐）

- Block F 地面层（F1/F2/F3）有位置资料但公司没给价格表 → 搜得到，计算器显示「无价格」
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
