# Alpha Agent System

甲板山庄 Jiangnan Villa / Papan Memorial 销售系统 — 骨灰位（niche）与土葬（burial plot）的
空置查询、格子图、价格计算器。

单页 React 应用，**打包后是一个自包含的 `index.html`**（CSS、JS、图标全部内嵌），
可以丢到任何静态托管上，不需要服务器。

## 快速开始

```bash
npm install
npm run build      # 产出 dist/index.html
npm run preview    # 本机 http://127.0.0.1:4173 看效果
npm run deploy     # 打包 + 部署到 alphaagentsystem.surge.sh
```

首次 `npm run deploy` 会要求登入 surge（输入 email，收一次性密码）。
surge 没装的话先 `npm install -g surge`。

## 文件结构

| 文件 | 作用 |
|---|---|
| `App.jsx` | 整个应用 + 全部真实资料（价格表、空置状态） |
| `src-entry.jsx` | React 挂载入口 |
| `scripts/build.mjs` | 打包：Tailwind → esbuild → 组装成单一 HTML |
| `scripts/serve.mjs` | 本机预览服务器 |
| `alpha-agent-system-fixes.md` | 早期 bug 修复记录 |

> `tailwind.config.js` 扫描的是 `.tailwind-classes.txt`（build 时自动生成），
> 不是 `App.jsx` —— 因为 `App.jsx` 有 ~800KB 是单行的库存资料，Tailwind 直接扫会卡死。

## 资料来源与更新

价格、现金回扣、头期/供期算法来自公司的价目表 PDF；空置/已售状态来自公司导出的
「福位楼层图 / 位子图」PDF（原生 Excel 导出，所以文字和格子底色都能程序化读取：
**黄色 = 已售，白色 = 空置**）。

资料是**快照，不是实时的** —— 每天都有成交。当前快照日期写在 App 里
（`NICHE_STATUS_UPDATED` / `BURIAL_STATUS_UPDATED`）。要更新就拿新导出的
PDF 重新解析后替换 `App.jsx` 里的 `AVAIL_RAW` / `NICHE_STATUS` / `BURIAL_STATUS`。

已知缺口（照实记录，没有编造）：
- Block F 地面层（F1/F2/F3）有位置资料但公司没有价格表 → 搜得到，但计算器会显示"无价格"
- Block M 全部售罄
- Zone A/AS 没有土葬位子图
- 少数格子被价格分类色（如 Special View）盖住，看不出空/售 → 标为"待确认"，没有猜

## 登入与账号

首次打开会要求登入。管理员账号在 `App.jsx` 里以 `ADMIN_EMAIL` /
`ADMIN_DEFAULT_PASSWORD` 播种，第一次登入后请立刻在「更多 → 账号管理」改掉默认密码。

管理员可以开设 / 删除账号、重设密码、升降权限；一般用户只能改自己的密码。

> **⚠️ 这个登入是「软门」，不是真正的访问控制。**
> 本应用是纯前端静态页面，没有后台，密码验证在访客自己的浏览器里执行 ——
> 懂技术的人打开 DevTools 就能绕过去读到里面的价格和库存资料。
> 它能挡住随手点进来的人、能区分管理员与一般用户，但**不等于资料受保护**。
> 账号存在各自浏览器的 localStorage，因此是**按设备**的：换一台手机/电脑要重新开账号。
>
> 若这些资料不能外流，需要改成有后端的架构（资料放服务器，验证通过才下发）。
