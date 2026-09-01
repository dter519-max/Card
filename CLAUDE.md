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

解析要注意的坑（都踩过）：
- 一个 Hall 的 R/F/L 三个侧翼是**并排**的，每行会重复出现多个层号 token，
  逐行收集时必须在下一个层号处停，否则会把隔壁侧翼的编号吃进来、朝向标错。
- 侧翼/区段的表头是**整排一次出现在数据之前**的，用单一「当前侧翼」变量会被最后一个覆盖。
  要按 x 坐标建锚点，再把每行按最近的 x 归属。
- Ground/First Floor 那几页的 block 字母是跟中文名黏在一个 token 里的（如 `K（聖寶院）-`），
  而且可能跟 `BLOCK` 这个词不在同一行 —— 直接取「BLOCK 后面那个词」会拿到 `GROUND` 而误判成 G 座。

改完资料务必抽样跟旧数据对一遍（A/B/C/D 座当年是完全吻合的，Block N 的总数能跟表格
自己印的 "TOTAL UNIT" 对上），别解析完就直接信。

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
