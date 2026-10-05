# 欠贯钱计算系统（独立网页版）

不需要任何账号，手机浏览器打开即可使用，可加到主屏幕。历史记录只存在各自手机的浏览器里。

- `index.html`：界面
- `engine.js`：计算引擎，全部规则在 `defaultRules()`（改数字只改这里）
- `lunar.js`：万年历（lunar-javascript 1.7.7，MIT）
- `sw.js`：离线缓存，发布新版时把 `VERSION` 改一下
