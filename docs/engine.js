/* 欠贯钱计算引擎
 * 规则来源：用户提供的《六十甲子寿生钱表》书页照片（IMG_1275–1295 及补拍原图）。
 * 所有金额单位：贯。只在最后一步向上进位到整万。
 * 依赖：lunar-javascript（全局 Solar / Lunar），只用于阳历农历换算和查万年历。
 */
(function (root) {
  var GAN = '甲乙丙丁戊己庚辛壬癸';
  var ZHI = '子丑寅卯辰巳午未申酉戌亥';
  var LUNAR_MONTH = ['', '正月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'];
  var LUNAR_DAY = ['', '初一', '初二', '初三', '初四', '初五', '初六', '初七', '初八', '初九', '初十',
    '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十',
    '廿一', '廿二', '廿三', '廿四', '廿五', '廿六', '廿七', '廿八', '廿九', '三十'];

  // 年份表：干支, 欠钱, 看经卷数, 第几库, 曹官姓, 来源, 曹官姓是否需要核对
  // 金额已用原图逐行核对。曹官姓为行书，标 true 的需对照原书确认。
  var YEAR_ROWS = [
    ['甲子', 53000, 18, 3, '元', 'IMG_1275', false],
    ['乙丑', 280000, 94, 13, '田', 'IMG_1275', true],
    ['丙寅', 80000, 27, 10, '马', '原图 p.2', true],
    ['丁卯', 23000, 8, 12, '许', '原图 p.2', true],
    ['戊辰', 54000, 18, 14, '冯', '原图 p.2', true],
    ['己巳', 72000, 24, 21, '曹', '原图 p.2', false],
    ['庚午', 62000, 21, 42, '陈', '原图 p.3', false],
    ['辛未', 102000, 34, 59, '常', '原图 p.3', true],
    ['壬申', 42000, 14, 49, '王', '原图 p.3', false],
    ['癸酉', 50000, 17, 12, '申', '原图 p.3', true],
    ['甲戌', 27000, 9, 17, '林', '原图 p.4', true],
    ['乙亥', 48000, 16, 42, '成', '原图 p.4', true],
    ['丙子', 73000, 25, 9, '汪', '原图 p.4', false],
    ['丁丑', 42000, 15, 3, '崔', '原图 p.4', true],
    ['戊寅', 60000, 20, 11, '郭', '原图 p.5', true],
    ['己卯', 80000, 27, 26, '宋', '原图 p.5', true],
    ['庚辰', 57000, 19, 24, '刘', '原图 p.5', true],
    ['辛巳', 57000, 19, 37, '高', '原图 p.5', true],
    ['壬午', 70000, 24, 44, '李', '原图 p.6', true],
    ['癸未', 52000, 18, 49, '朱', '原图 p.6', true],
    ['甲申', 70000, 24, 56, '侯', '原图 p.6', true],
    ['乙酉', 40000, 14, 2, '伍', '原图 p.6', true],
    ['丙戌', 80000, 27, 3, '汪', '原图 p.7', true],
    ['丁亥', 39000, 13, 40, '古', '原图 p.7', true],
    ['戊子', 63000, 21, 6, '伍', '原图 p.7', true],
    ['己丑', 80000, 27, 7, '周', '原图 p.7', true],
    ['庚寅', 51000, 17, 15, '毛', '原图 p.8', true],
    ['辛卯', 80000, 27, 4, '张', '原图 p.8', true],
    ['壬辰', 45000, 15, 1, '赵', '原图 p.8', true],
    ['癸巳', 39000, 13, 50, '付', '原图 p.8', true],
    ['甲午', 40000, 14, 21, '仲', '原图 p.9', true],
    ['乙未', 40000, 14, 51, '全', '原图 p.9', true],
    ['丙申', 33000, 11, 52, '钮', '原图 p.9', true],
    ['丁酉', 170000, 57, 29, '胡', '原图 p.9', true],
    ['戊戌', 42000, 14, 36, '管', '原图 p.10', true],
    ['己亥', 72000, 24, 50, '宋', '原图 p.10', true],
    ['庚子', 110000, 37, 9, '李', '原图 p.10', true],
    ['辛丑', 110000, 37, 18, '古', '原图 p.10', true],
    ['壬寅', 96000, 32, 11, '孙', '原图 p.11', true],
    ['癸卯', 33000, 11, 22, '王', '原图 p.11', false],
    ['甲辰', 29000, 10, 19, '董', '原图 p.11', true],
    ['乙巳', 90000, 30, 21, '杨', '原图 p.11', true],
    ['丙午', 53000, 18, 60, '萧', '原图 p.12', true],
    ['丁未', 91000, 31, 52, '朱', '原图 p.12', true],
    ['戊申', 80000, 27, 58, '柴', '原图 p.12', true],
    ['己酉', 90000, 30, 23, '孙', '原图 p.12', true],
    ['庚戌', 110000, 37, 2, '辛', '原图 p.13', true],
    ['辛亥', 72000, 24, 40, '宋', '原图 p.13', true],
    ['壬子', 70000, 24, 3, '温', '原图 p.13', true],
    ['癸丑', 27000, 9, 8, '刁', '原图 p.13', false],
    ['甲寅', 33000, 11, 11, '杜', '原图 p.14', true],
    ['乙卯', 80000, 27, 18, '柳', '原图 p.14', true],
    ['丙辰', 32000, 11, 33, '寅', '原图 p.14', true],
    ['丁巳', 70000, 24, 16, '程', '原图 p.14', true],
    ['戊午', 90000, 30, 39, '史', '原图 p.15', true],
    ['己未', 43000, 15, 5, '卞', '原图 p.15', true],
    ['庚申', 61000, 21, 42, '胡', '原图 p.15', true],
    ['辛酉', 27000, 9, 15, '丁', 'IMG_1290', false],
    ['壬戌', 72000, 24, 40, '彭', '原图 p.15', true],
    ['癸亥', 75000, 25, 43, '仇', 'IMG_1290', true]
  ];

  function defaultRules() {
    return {
      version: 1,
      pricePerWan: 28, // RM，每 1 万贯
      years: YEAR_ROWS.map(function (r) {
        return { ganzhi: r[0], amount: r[1], juan: r[2], ku: r[3], caoguan: r[4], source: r[5], caoguanCheck: r[6] };
      }),
      // 月干 / 时干 共用同一张天干表（IMG_1291 月份天干算法、IMG_1294 时辰天干算法）
      monthStem: { '甲': 10000, '乙': 20000, '丙': 30000, '丁': 40000, '戊': 50000, '己': 6000, '庚': 7000, '辛': 8000, '壬': 9000, '癸': 12000 },
      hourStem: { '甲': 10000, '乙': 20000, '丙': 30000, '丁': 40000, '戊': 50000, '己': 6000, '庚': 7000, '辛': 8000, '壬': 9000, '癸': 12000 },
      monthNumberUnit: 1000, // IMG_1292：正月 1000 … 十二月 12000
      dayUnit: 1000,         // IMG_1293：初一 1000 … 三十 30000
      // IMG_1295 地支算法：子 1000 … 亥 12000
      hourBranch: { '子': 1000, '丑': 2000, '寅': 3000, '卯': 4000, '辰': 5000, '巳': 6000, '午': 7000, '未': 8000, '申': 9000, '酉': 10000, '戌': 11000, '亥': 12000 }
    };
  }

  // 公历年份 → 干支（按年份数字查表，已与用户确认）
  function yearGanzhiByNumber(y) {
    var i = ((y - 4) % 60 + 60) % 60;
    return GAN[i % 10] + ZHI[i % 12];
  }

  // 出生时间 → 时支序号；23:00 以后仍算当天的子时（已与用户确认）
  function hourBranchIndex(h) {
    if (h === 23) return 0;
    return Math.floor((h + 1) / 2);
  }
  // 时辰 → 用于查万年历的代表钟点
  var HOUR_OF_BRANCH = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22];

  /**
   * input: { name, calendar: 'solar'|'lunar', year, month, day, leap(bool), hour, minute, branch(可选，时辰序号) }
   */
  function calculate(input, rules, lib) {
    rules = rules || defaultRules();
    lib = lib || root;
    var errors = [];
    if (!input.name || !String(input.name).trim()) errors.push('姓名');
    if (!input.year || !input.month || !input.day) errors.push('出生日期');
    if (input.branch == null && input.hour == null) errors.push('出生时间');
    if (errors.length) return { ok: false, error: '请完整填写出生资料：' + errors.join('、') };

    var hour = input.hour != null ? input.hour : HOUR_OF_BRANCH[input.branch];
    var minute = input.minute || 0;
    var lunar, solar;
    try {
      if (input.calendar === 'lunar') {
        lunar = lib.Lunar.fromYmdHms(input.year, input.leap ? -input.month : input.month, input.day, hour, minute, 0);
        solar = lunar.getSolar();
      } else {
        solar = lib.Solar.fromYmdHms(input.year, input.month, input.day, hour, minute, 0);
        lunar = solar.getLunar();
      }
    } catch (e) {
      return { ok: false, error: '这个日期不存在，请检查（例如该年没有这个闰月，或农历这个月没有三十）。' };
    }

    var steps = [];
    var manual = [];

    // A 年份：按阳历出生年份查表
    var sy = solar.getYear();
    var ygz = yearGanzhiByNumber(sy);
    var yrow = null;
    for (var i = 0; i < rules.years.length; i++) if (rules.years[i].ganzhi === ygz) yrow = rules.years[i];
    if (!yrow || yrow.amount == null) {
      manual.push('年份 ' + ygz + ' 规则缺失，请检查原书');
    }
    var A = yrow ? yrow.amount : 0;
    steps.push({ key: 'A', label: '年份', detail: '阳历 ' + sy + ' 年 → ' + ygz + '（六十年循环）', amount: A, source: yrow ? yrow.source : '' });

    // B 月份：月干（万年历当天月柱）+ 农历月份 × 1000
    var monthGz = lunar.getMonthInGanZhi();
    var mStem = monthGz.charAt(0);
    var lm = Math.abs(lunar.getMonth());
    var mStemAmt = rules.monthStem[mStem];
    var mNumAmt = lm * rules.monthNumberUnit;
    if (mStemAmt == null) manual.push('月干 ' + mStem + ' 规则缺失');
    var B = (mStemAmt || 0) + mNumAmt;
    steps.push({ key: 'B', label: '月份', detail: monthGz + '月：' + mStem + '月 ' + fmt(mStemAmt || 0) + ' ＋ 农历' + LUNAR_MONTH[lm] + (lunar.getMonth() < 0 ? '（闰月按同月）' : '') + ' ' + fmt(mNumAmt), amount: B, source: 'IMG_1291 / IMG_1292' });

    // C 日期：农历日 × 1000
    var ld = lunar.getDay();
    var C = ld * rules.dayUnit;
    steps.push({ key: 'C', label: '日期', detail: '农历' + LUNAR_DAY[ld], amount: C, source: 'IMG_1293' });

    // D 时辰：日上起时诀定时干 + 时支
    var dayGz = lunar.getDayInGanZhi();
    var dStem = GAN.indexOf(dayGz.charAt(0));
    var bi = input.branch != null ? input.branch : hourBranchIndex(hour);
    var hStem = GAN.charAt(((dStem % 5) * 2 + bi) % 10);
    var hBranch = ZHI.charAt(bi);
    var hsAmt = rules.hourStem[hStem], hbAmt = rules.hourBranch[hBranch];
    if (hsAmt == null || hbAmt == null) manual.push('时辰 ' + hStem + hBranch + ' 规则缺失');
    var D = (hsAmt || 0) + (hbAmt || 0);
    steps.push({ key: 'D', label: '时辰', detail: dayGz + '日 → ' + hStem + hBranch + '时：' + hStem + '时 ' + fmt(hsAmt || 0) + ' ＋ ' + hBranch + '时 ' + fmt(hbAmt || 0), amount: D, source: 'IMG_1293 / 1294 / 1295' });

    var raw = A + B + C + D;
    var finalAmt = Math.ceil(raw / 10000) * 10000;
    var wan = finalAmt / 10000;
    return {
      ok: manual.length === 0,
      needsManual: manual,
      name: String(input.name).trim(),
      solarText: solar.toYmd() + ' ' + pad(hour) + ':' + pad(minute),
      lunarText: '农历 ' + lunar.getYear() + ' 年 ' + (lunar.getMonth() < 0 ? '闰' : '') + LUNAR_MONTH[lm] + LUNAR_DAY[ld],
      bazi: { year: lunar.getYearInGanZhiByLiChun(), month: monthGz, day: dayGz, hour: hStem + hBranch },
      hourName: hBranch + '时',
      tableYear: ygz,
      steps: steps,
      raw: raw,
      final: finalAmt,
      wan: wan,
      price: wan * rules.pricePerWan,
      pricePerWan: rules.pricePerWan,
      juan: yrow ? yrow.juan : null,
      ku: yrow ? yrow.ku : null,
      caoguan: yrow ? yrow.caoguan : null
    };
  }

  function fmt(n) { return Number(n).toLocaleString('en-US'); }
  function pad(n) { return (n < 10 ? '0' : '') + n; }

  var api = { defaultRules: defaultRules, calculate: calculate, yearGanzhiByNumber: yearGanzhiByNumber, GAN: GAN, ZHI: ZHI, LUNAR_MONTH: LUNAR_MONTH, LUNAR_DAY: LUNAR_DAY, fmt: fmt };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.QianGuan = api;
})(this);
