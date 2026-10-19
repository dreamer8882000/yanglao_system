<template>
  <div class="page">
    <!-- ═══════ 页头 ═══════ -->
    <div class="page-header">
      <div class="page-header-left">
        <div>
          <h1>效果评测</h1>
          <p class="page-sub">
            这套系统在本院靠不靠得住、该往哪调 —— 仅机构管理员可见
          </p>
        </div>
      </div>
      <div class="page-actions">
        <div class="seg">
          <button
            v-for="d in RANGES" :key="d"
            class="seg-btn" :class="{ on: days === d }"
            @click="setDays(d)"
          >近 {{ d }} 天</button>
        </div>
      </div>
    </div>

    <!-- ═══════ 1. 结论先行 ═══════ -->
    <!-- 评测页此前是一排数字加一个 23 项的报告下拉框，看完不知道要做什么。
         现在第一屏就给结论：系统当前可不可信、下一步该动哪里。 -->
    <section class="panel verdict" :class="'v-' + verdict.tone">
      <div class="verdict-mark">{{ verdict.icon }}</div>
      <div class="verdict-body">
        <div class="verdict-title">{{ verdict.title }}</div>
        <div class="verdict-text">{{ verdict.text }}</div>
      </div>
      <div class="verdict-facts">
        <div v-for="f in verdict.facts" :key="f.label" class="vf">
          <div class="vf-v">{{ f.value }}</div>
          <div class="vf-l">{{ f.label }}</div>
        </div>
      </div>
    </section>

    <!-- ═══════ 2. 融合方案对比（本页最该先看的一张表）═══════ -->
    <!-- 证据模式由系统在告警时刻**实际拿到的证据源**决定：同一个人体目标同时
         拿到姿态与表情 → 双模态 D-S 融合；只拿到姿态（未定位到人脸）→ 单模态。
         这是整套融合方案在真实运行里到底有没有用的直接证据，所以放在结论卡
         之后的第一屏，而不是塞进归因表的角落。 -->
    <section class="panel">
      <div class="panel-head">
        <h2>证据模式对比：双模态（姿态 + 表情） vs 单模态（仅姿态）</h2>
        <span class="panel-sub">近 {{ days }} 天 · 护理员复核</span>
      </div>
      <div v-if="modeCards.length" class="mode-grid">
        <article v-for="m in modeCards" :key="m.key" class="mode-card">
          <div class="mc-name">{{ m.label }}</div>
          <div class="mc-rate" :class="m.rateCls">{{ pct1(m.rate) }}</div>
          <div class="mc-rate-l">误报率</div>
          <div class="mc-track">
            <div class="mc-fill" :class="m.rateCls" :style="{ width: (m.rate * 100) + '%' }"></div>
          </div>
          <div class="mc-facts">
            <div class="mcf"><div class="mcf-v">{{ m.total }}</div><div class="mcf-k">复核</div></div>
            <div class="mcf"><div class="mcf-v">{{ m.handled }}</div><div class="mcf-k">确认为真</div></div>
            <div class="mcf"><div class="mcf-v">{{ m.falseAlarms }}</div><div class="mcf-k">判为误报</div></div>
          </div>
          <div class="mc-sample" :class="'s-' + m.tier.cls">{{ m.tier.text }}</div>
        </article>
      </div>
      <div v-else class="empty">暂无已复核数据</div>

      <div v-if="modeCards.length" class="mode-delta" :class="modeDelta.tone">
        <div class="md-num">
          <span class="md-v">{{ modeDelta.value }}</span>
          <span v-if="modeDelta.unit" class="md-u">{{ modeDelta.unit }}</span>
        </div>
        <div class="md-text">{{ modeDelta.text }}</div>
      </div>
      <p v-if="modeCards.length" class="panel-note panel-note--wide">{{ modeDelta.caveat }}</p>
    </section>

    <!-- ═══════ 3. 本院的真实运行质量 ═══════ -->
    <div class="grid-2-1">
      <section class="panel">
        <div class="panel-head">
          <h2>各等级误报率</h2>
          <span class="panel-sub">近 {{ days }} 天 · 护理员复核</span>
        </div>
        <BarList :items="levelFpItems" />
        <p class="panel-note">
          某个等级的误报率明显偏高，说明该等级的阈值需要收紧 ——
          这是最直接可调的一环。
        </p>
      </section>

      <section class="panel">
        <div class="panel-head"><h2>复核情况</h2></div>
        <div class="stat-center">
          <div class="big-num" :class="(feedback.reviewCoverage || 0) >= 0.6 ? 'ok' : 'warn'">
            {{ pct(feedback.reviewCoverage) }}
          </div>
          <div class="big-sub">复核覆盖率</div>
        </div>
        <div class="rate-bar">
          <div class="rate-fill" :style="{ width: ((feedback.reviewCoverage || 0) * 100) + '%' }"></div>
        </div>
        <div class="kv-list">
          <div class="kv"><span class="k">已复核</span><span class="v">{{ feedback.reviewed || 0 }} 条</span></div>
          <div class="kv"><span class="k">待处理</span><span class="v warn">{{ feedback.pending || 0 }} 条</span></div>
          <div class="kv"><span class="k">确认为真</span><span class="v">{{ feedback.handled || 0 }} 条</span></div>
          <div class="kv"><span class="k">判为误报</span><span class="v">{{ feedback.falseAlarms || 0 }} 条</span></div>
        </div>
        <div class="pie-cap">全部告警的处置构成</div>
        <div class="review-pie">
          <PieChart :items="reviewPie" :size="116" :thickness="16" unit="告警" />
        </div>
        <p class="panel-note">
          覆盖率低时，下面的比率只代表已复核的那部分，不能当作全院结论。
        </p>
      </section>
    </div>

    <!-- ═══════ 4. 归因：该调什么 ═══════ -->
    <div class="grid-1-1">
      <section class="panel">
        <div class="panel-head">
          <h2>按姿态归因</h2>
          <span class="panel-sub">误报率降序</span>
        </div>
        <table class="tbl">
          <thead>
            <tr><th>姿态</th><th>复核</th><th>误报</th><th>误报率</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in feedback.byPosture || []" :key="r.posture">
              <td>{{ postureLabel(r.posture) }}</td>
              <td>{{ r.total }}</td>
              <td>{{ r.falseAlarms }}</td>
              <td>
                <span class="rate-chip" :class="rateClass(r.falseAlarmRate)">
                  {{ pct(r.falseAlarmRate) }}
                </span>
              </td>
            </tr>
            <tr v-if="!(feedback.byPosture || []).length">
              <td colspan="4" class="empty">暂无已复核数据</td>
            </tr>
          </tbody>
        </table>
        <p class="panel-note">
          姿态是主判据。「姿态不明」若误报率超过 <strong>60%</strong>，
          说明几何特征不足以支撑该判断，应收紧而不是继续报警。
        </p>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>按表情归因</h2>
          <span class="panel-sub">误报率降序</span>
        </div>
        <table class="tbl">
          <thead>
            <tr><th>主导表情</th><th>复核</th><th>误报</th><th>误报率</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in feedback.byExpression || []" :key="r.expression">
              <td>{{ emotionLabel(r.expression) }}</td>
              <td>{{ r.total }}</td>
              <td>{{ r.falseAlarms }}</td>
              <td>
                <span class="rate-chip" :class="rateClass(r.falseAlarmRate)">
                  {{ pct(r.falseAlarmRate) }}
                </span>
              </td>
            </tr>
            <tr v-if="!(feedback.byExpression || []).length">
              <td colspan="4" class="empty">暂无已复核数据</td>
            </tr>
          </tbody>
        </table>
        <p class="panel-note">
          表情只用于判断「是否痛苦」，<strong>不参与跌倒判定</strong>。
          这里偏高不会造成误报跌倒，但会抬高告警的紧急等级。
        </p>
      </section>
    </div>

    <!-- ═══════ 5. 定位：先查哪一路摄像头、先调哪个时段 ═══════ -->
    <!-- 上面两栏回答"错在哪一类告警"，这一栏回答"去哪里处理"：
         摄像头指向安装/取景，时段指向排班与分时段阈值 —— 都是能当天执行的运维动作。 -->
    <div class="grid-1-1">
      <section class="panel">
        <div class="panel-head">
          <h2>按摄像头定位</h2>
          <span class="panel-sub">误报率降序 · 仅已复核</span>
        </div>
        <p v-if="cameraFocus" class="focus-line">
          优先排查 <strong>{{ cameraFocus.cameraName }}</strong>：
          {{ cameraFocus.total }} 条已复核里 {{ cameraFocus.falseAlarms }} 条被判为误报（{{ pct(cameraFocus.falseAlarmRate) }}）
        </p>
        <table class="tbl">
          <thead>
            <tr><th>摄像头</th><th>复核</th><th>误报</th><th>误报率</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in cameraRows" :key="r.cameraName" :class="{ hot: r.hot }">
              <td>{{ r.cameraName }}</td>
              <td>{{ r.total }}</td>
              <td>{{ r.falseAlarms }}</td>
              <td>
                <span class="rate-chip" :class="[rateClass(r.falseAlarmRate), { weak: r.total < 2 }]">
                  {{ pct(r.falseAlarmRate) }}
                </span>
              </td>
            </tr>
            <tr v-if="!cameraRows.length">
              <td colspan="4" class="empty">暂无已复核数据</td>
            </tr>
          </tbody>
        </table>
        <p class="panel-note panel-note--wide">
          同一路摄像头反复误报，多半不是模型问题而是<strong>取景问题</strong>：
          床面被家具挡住、逆光、镜头离床太近，都会让「横卧」被误判。
          先去现场核对画面范围，再决定要不要动阈值。
          只复核过 1 条的摄像头（灰色标签）算不出比率，先补够复核数再看。
        </p>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>按时段分布</h2>
          <span class="panel-sub">24 小时 · 仅已复核</span>
        </div>
        <BarChart :data="hourBars" :height="300" />
        <div class="hour-facts">
          <div class="hf">
            <div class="hf-v">{{ hourPeakTotal && hourPeakTotal.total ? hourPeakTotal.hour + ':00' : '—' }}</div>
            <div class="hf-k">告警最集中（{{ hourPeakTotal ? hourPeakTotal.total : 0 }} 条）</div>
          </div>
          <div class="hf">
            <div class="hf-v">{{ hourPeakRate ? hourPeakRate.hour + ':00' : '—' }}</div>
            <div class="hf-k">误报率最高（{{ hourPeakRate ? pct(hourPeakRate.falseAlarmRate) : '无有效样本' }}）</div>
          </div>
          <div class="hf">
            <div class="hf-v">{{ hourActive }}/24</div>
            <div class="hf-k">有时段有复核数据</div>
          </div>
        </div>
        <p class="panel-note panel-note--wide">
          柱子按小时堆叠：钢蓝＝确认为真，红色＝误报。误报集中在少数时段，
          通常与那个时段的光线、人员在床状态有关 —— 先补光或做<strong>分时段阈值</strong>，
          比全局收紧更不容易漏掉真跌倒。
        </p>
      </section>
    </div>

    <!-- ═══════ 6. 离线基准（模型能力）═══════ -->
    <section class="panel">
      <div class="panel-head">
        <h2>模型能力基准（离线）</h2>
        <div class="seg">
          <button
            v-for="r in reports" :key="r.name"
            class="seg-btn" :class="{ on: currentReport === r.name }"
            @click="selectReport(r.name)"
          >{{ reportLabel(r.name) }}</button>
        </div>
      </div>

      <p class="panel-note panel-note--lead">
        在公开跌倒数据集 URFD 上的固定协议结果，衡量<strong>模型本身的能力上限</strong>；
        与本院运行质量是两回事 —— 前者决定能不能用，后者决定用得顺不顺。
      </p>

      <div v-if="report" class="metric-row">
        <div class="metric">
          <div class="m-v">{{ pct(report.summary?.recall) }}</div>
          <div class="m-l">跌倒召回</div>
          <div class="m-s">{{ report.fall?.hit }}/{{ report.fall?.total }} 段触发告警</div>
        </div>
        <div class="metric">
          <div class="m-v">{{ pct(precision) }}</div>
          <div class="m-l">精确率</div>
          <div class="m-s">告警中真实跌倒的占比</div>
        </div>
        <div class="metric">
          <div class="m-v">{{ pct(report.summary?.falsePositiveRate) }}</div>
          <div class="m-l">日常误报率</div>
          <div class="m-s">{{ report.adl?.hit }}/{{ report.adl?.total }} 段日常被误报</div>
        </div>
        <div class="metric">
          <div class="m-v warn">{{ pct(report.summary?.confirmRate) }}</div>
          <div class="m-l">确认跌倒率</div>
          <div class="m-s">{{ report.fall?.confirmed }}/{{ report.fall?.total }} 段进入已确认</div>
        </div>
        <div class="metric">
          <div class="m-v">{{ (report.fall?.total || 0) + (report.adl?.total || 0) }}</div>
          <div class="m-l">评测样本</div>
          <div class="m-s">跌倒 {{ report.fall?.total }} · 日常 {{ report.adl?.total }}</div>
        </div>
      </div>
      <div v-else class="empty">未找到评测报告</div>
    </section>

    <!-- ═══════ 7. 模型对比 ═══════ -->
    <section class="panel">
      <div class="panel-head">
        <h2>姿态模型对比</h2>
        <span class="panel-sub">同一协议下</span>
      </div>
      <table class="tbl">
        <thead>
          <tr><th>模型</th><th>样本</th><th>召回</th><th>精确</th><th>误报</th><th>确认率</th></tr>
        </thead>
        <tbody>
          <tr v-for="m in modelRows" :key="m.name" :class="{ current: m.current }">
            <td>
              {{ m.name }}
              <span v-if="m.current" class="badge-now">当前部署</span>
            </td>
            <td>{{ m.total }}</td>
            <td>{{ pct(m.recall) }}</td>
            <td>{{ pct(m.precision) }}</td>
            <td>{{ pct(m.fp) }}</td>
            <td>{{ pct(m.confirm) }}</td>
          </tr>
          <tr v-if="!modelRows.length"><td colspan="6" class="empty">暂无对比报告</td></tr>
        </tbody>
      </table>
      <p class="panel-note">
        部署取舍：养老场景里误报的代价是<strong>告警疲劳</strong>（护理员被假警拖垮后会忽略真警），
        累积后果重于单次漏检，因此当前选精确率更高的模型。
      </p>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { listReports, getReport } from '../api/evaluation.js';
import { getFeedbackStats } from '../api/alerts.js';
import { showToast } from '../utils/index.js';
import { LEVELS, levelColor } from '../utils/levelColors.js';
import BarList from '../components/BarList.vue';
import BarChart from '../components/BarChart.vue';
import PieChart from '../components/PieChart.vue';

const RANGES = [7, 30, 90];
const days = ref(30);
const reports = ref([]);
const currentReport = ref('');
const report = ref(null);
const feedback = ref({});

// 等级配色不再在页面里重复定义 —— 唯一来源是 utils/levelColors.js
// （它只返回 var(--level-x)，色值本身在 tokens.css 里按主题定义）。
const LEVEL_COLOR = Object.fromEntries(LEVELS.map((l) => [l, levelColor(l)]));
const POSTURE_LABEL = {
  fall_like: '横卧（跌倒样）', lying: '躺卧', sitting: '坐姿',
  standing: '站立', bending: '弯腰', unknown: '姿态不明',
  insufficient_body: '关键点不足',
};
const EMOTION_LABEL = {
  Anger: '愤怒', Contempt: '轻蔑', Disgust: '厌恶', Fear: '恐惧',
  Happy: '高兴', Neutral: '平静', Sad: '悲伤', Surprise: '惊讶',
};

// 证据模式（后端 evidence_mode）的取值语义见 expression_recognition/system.py
// _evidence_mode()：姿态与表情都拿到→pose_expression，只有姿态→pose_only。
const EVIDENCE_MODE_LABEL = {
  pose_expression: '姿态 + 表情（双模态融合）',
  pose_only: '仅姿态（未定位到人脸）',
  expression_only: '仅表情（身体关键点不足）',
  no_evidence: '无有效证据',
  unknown: '未知',
};
const MODE_ORDER = ['pose_expression', 'pose_only', 'expression_only', 'no_evidence', 'unknown'];
// 单类复核数低于此值就不足以支撑结论。按二项分布，30 条里 1 条误报的 95% 置信
// 区间仍宽达 0%~17%，两组各 30 条以内谈"谁比谁低几个百分点"基本是噪声。
const SAMPLE_MIN = 30;

const precision = computed(() => {
  const tp = report.value?.fall?.hit ?? 0;
  const fp = report.value?.adl?.hit ?? 0;
  return tp + fp ? tp / (tp + fp) : 0;
});

const levelFpItems = computed(() => (feedback.value.byLevel || []).map((r) => ({
  key: r.level, label: r.level, value: r.falseAlarms,
  color: LEVEL_COLOR[r.level] || 'var(--text-muted)',
})));

// ── 证据模式对比：整套融合方案在真实运行里到底有没有用 ────────────────
const evidenceRows = computed(() => {
  const rank = (m) => {
    const i = MODE_ORDER.indexOf(m.mode);
    return i < 0 ? MODE_ORDER.length : i;
  };
  return [...(feedback.value.byEvidenceMode || [])]
    .sort((a, b) => rank(a) - rank(b) || b.total - a.total);
});

function sampleTier(n) {
  if (n >= SAMPLE_MIN) return { cls: 'ok', text: `${n} 条复核 · 样本充足` };
  if (n >= 10) return { cls: 'mid', text: `${n} 条复核 · 样本偏少` };
  return { cls: 'low', text: `${n} 条复核 · 样本极少` };
}

const modeCards = computed(() => evidenceRows.value.map((r) => ({
  key: r.mode,
  label: EVIDENCE_MODE_LABEL[r.mode] || r.mode,
  rate: Number(r.falseAlarmRate) || 0,
  total: r.total, handled: r.handled, falseAlarms: r.falseAlarms,
  rateCls: rateClass(r.falseAlarmRate),
  tier: sampleTier(r.total),
})));

// 差值只陈述事实：数据说双模态更低就写低，说更高就写更高。
// 这里刻意不做"双模态一定更好"的单向措辞 —— 否则一旦样本反向就成了假结论。
const modeDelta = computed(() => {
  const dual = evidenceRows.value.find((r) => r.mode === 'pose_expression');
  const single = evidenceRows.value.find((r) => r.mode === 'pose_only');
  if (!dual || !single) {
    return {
      value: '—', unit: '', tone: 't-info',
      text: '本时段只有一种证据模式留下了已复核告警，无法对比',
      caveat: '对比需要双模态与单模态都有护理员复核过的告警，等两类样本齐了再看这张表。',
    };
  }
  // pp > 0 表示双模态误报率更低
  const pp = (Number(single.falseAlarmRate) - Number(dual.falseAlarmRate)) * 100;
  const abs = Math.abs(pp).toFixed(1);
  const text = Math.abs(pp) < 0.05
    ? '两种模式的误报率基本持平'
    : pp > 0
      ? `双模态误报率比单模态低 ${abs} 个百分点`
      : `双模态误报率比单模态高 ${abs} 个百分点`;
  const weak = Math.min(dual.total, single.total) < SAMPLE_MIN;
  const caveat = weak
    ? `样本提示：可用于对比的只有双模态 ${dual.total} 条、仅姿态 ${single.total} 条，都低于可下结论的量级（建议每类 ≥ ${SAMPLE_MIN} 条）。`
      + `这个差值由双模态 ${dual.falseAlarms} 条、仅姿态 ${single.falseAlarms} 条误报决定，再多复核十几条就可能反向，因此只当事实记录、不当融合方案的结论。`
      + '另外，证据模式取决于告警时刻能否定位到人脸，并非随机分组对照，两组的人群与场景本身可能不同。'
    : `可用于对比的双模态 ${dual.total} 条、仅姿态 ${single.total} 条，样本量已够作为本机构运行参考（但两组仍非随机对照）。`;
  return {
    value: abs, unit: '个百分点',
    tone: pp > 0.05 ? 't-ok' : pp < -0.05 ? 't-warn' : 't-info',
    text, caveat,
  };
});

// ── 摄像头定位：误报率降序，指向取景/安装问题 ─────────────────────────
const cameraRows = computed(() => (feedback.value.byCamera || [])
  .map((r) => ({ ...r, hot: (r.falseAlarmRate || 0) >= 0.5 && (r.total || 0) >= 2 }))
  .sort((a, b) => (b.falseAlarmRate || 0) - (a.falseAlarmRate || 0) || (b.total || 0) - (a.total || 0)));

// 只把 ≥2 条复核的摄像头当作"要排查"的对象：1 条样本的 100% 没有分量
const cameraFocus = computed(() => {
  const list = cameraRows.value.filter((r) => (r.total || 0) >= 2);
  if (!list.length) return null;
  const top = list.reduce((a, b) => ((b.falseAlarmRate || 0) > (a.falseAlarmRate || 0) ? b : a));
  return top.falseAlarms ? top : null;
});

// ── 时段分布：后端只返回有数据的时段，这里补成完整 24 小时 ─────────────
const hourRows = computed(() => {
  const map = new Map((feedback.value.byHour || []).map((r) => [Number(r.hour), r]));
  return Array.from({ length: 24 }, (_, h) => {
    const r = map.get(h);
    const total = r?.total || 0;
    const fp = r?.falseAlarms || 0;
    return { hour: h, total, falseAlarms: fp, handled: total - fp, falseAlarmRate: r?.falseAlarmRate || 0 };
  });
});

const hourBars = computed(() => hourRows.value.map((r) => ({
  label: String(r.hour),
  segments: [
    { key: 'ok', label: '确认为真', value: r.handled, color: 'var(--primary)' },
    { key: 'fp', label: '判为误报', value: r.falseAlarms, color: 'var(--level-high)' },
  ],
})));

const hourActive = computed(() => hourRows.value.filter((r) => r.total > 0).length);

// 只有 1 条复核的时段误报率非 0 即 100%，没有参考价值，因此峰值只在 ≥2 条里找
const hourPeakTotal = computed(() => hourRows.value.reduce((a, b) => (b.total > a.total ? b : a), hourRows.value[0]));
const hourPeakRate = computed(() => {
  const cand = hourRows.value.filter((r) => r.total >= 2);
  if (!cand.length) return null;
  const top = cand.reduce((a, b) => (b.falseAlarmRate > a.falseAlarmRate ? b : a));
  return top.falseAlarms ? top : null;
});

// ── 复核构成：还有多少告警没有人的结论 ────────────────────────────────
const reviewPie = computed(() => {
  const fb = feedback.value || {};
  return [
    { key: 'handled', label: '确认为真', value: fb.handled || 0, color: 'var(--level-normal)' },
    { key: 'fp', label: '判为误报', value: fb.falseAlarms || 0, color: 'var(--level-high)' },
    { key: 'pending', label: '待复核', value: fb.pending || 0, color: 'var(--level-medium)' },
  ];
});

// 只比对同一协议下的姿态模型报告
const modelRows = computed(() => reports.value
  .filter((r) => /yolo/i.test(r.name))
  .map((r) => {
    const tp = (r.summary?.recall || 0) * (r.fallTotal || 0);
    const fp = (r.summary?.falsePositiveRate || 0) * (r.adlTotal || 0);
    return {
      name: reportLabel(r.name),
      total: (r.fallTotal || 0) + (r.adlTotal || 0),
      recall: r.summary?.recall, fp: r.summary?.falsePositiveRate,
      confirm: r.summary?.confirmRate,
      precision: tp + fp ? tp / (tp + fp) : 0,
      current: /26l/i.test(r.name),
    };
  }));

// ── 结论：把数字翻译成「该不该动、动哪里」────────────────────────────────
const verdict = computed(() => {
  const fb = feedback.value || {};
  const cov = fb.reviewCoverage || 0;
  const worst = (fb.byPosture || []).find((r) => r.total >= 3 && r.falseAlarmRate >= 0.5);
  const fm = fb.falseAlarmRate || 0;

  if ((fb.reviewed || 0) < 5) {
    return {
      tone: 'info', icon: '📋', title: '复核样本不足，暂无法给出结论',
      text: '评测结论依赖护理员的复核反馈。当前已复核告警过少，建议先在告警中心完成处置与误报标注。',
      facts: [{ label: '已复核', value: `${fb.reviewed || 0} 条` },
              { label: '待处理', value: `${fb.pending || 0} 条` }],
    };
  }
  const facts = [
    { label: '真实误报率', value: pct(fm) },
    { label: '复核覆盖率', value: pct(cov) },
    { label: '离线召回', value: pct(report.value?.summary?.recall) },
  ];
  if (worst) {
    return {
      tone: 'warn', icon: '⚠️',
      title: `建议收紧「${postureLabel(worst.posture)}」的判据`,
      text: `该姿态下 ${worst.total} 条已复核告警中有 ${worst.falseAlarms} 条被判为误报（${pct(worst.falseAlarmRate)}）。`
          + '说明这些告警的几何证据不足以支撑跌倒判断，继续按当前阈值报警会消耗护理员的注意力。',
      facts,
    };
  }
  if (fm <= 0.15 && cov >= 0.5) {
    return {
      tone: 'ok', icon: '✅', title: '系统当前表现稳定',
      text: `真实误报率 ${pct(fm)}、复核覆盖率 ${pct(cov)}，各姿态的误报率均在可接受范围内，暂时无需调整判据。`,
      facts,
    };
  }
  return {
    tone: 'info', icon: '📊', title: '整体可用，建议继续积累复核数据',
    text: `真实误报率 ${pct(fm)}。当前各姿态的误报率差异不显著，建议再观察一段时间后重新评估。`,
    facts,
  };
});

function pct(v) { return v == null ? '—' : `${(Number(v) * 100).toFixed(0)}%`; }
// 对比卡片用一位小数：20% 与 33.3% 的差值要能一眼看出来
function pct1(v) { return v == null ? '—' : `${(Number(v) * 100).toFixed(1)}%`; }
function rateClass(r) { return r >= 0.5 ? 'r-high' : r >= 0.25 ? 'r-mid' : 'r-low'; }
function postureLabel(v) { return POSTURE_LABEL[v] || v || '未知'; }
function emotionLabel(v) { return EMOTION_LABEL[v] || v || '未识别'; }
// 把文件名变成可读标签：urfd_side_yolo26l-pose → YOLO26L
function reportLabel(name) {
  const m = String(name).match(/yolo(v?\d+)([nslmx])?/i);
  if (m) return `YOLO${m[1]}${(m[2] || '').toUpperCase()}`;
  if (/final|baseline/i.test(name)) return '当前基准';
  return String(name).replace(/^urfd_side_?/, '') || name;
}

async function selectReport(name) {
  currentReport.value = name;
  try {
    const res = await getReport(name);
    report.value = res.data?.data || res.data;
  } catch { showToast('加载报告失败', 'error'); }
}

function setDays(d) { days.value = d; loadFeedback(); }

async function loadFeedback() {
  try {
    const res = await getFeedbackStats(days.value);
    feedback.value = res.data?.data || {};
  } catch { /* 非管理员由路由守卫拦下，这里静默 */ }
}

onMounted(async () => {
  await loadFeedback();
  try {
    const res = await listReports();
    reports.value = res.data?.data || [];
    // 默认选中当前部署模型（yolo26l）的报告，否则取第一份
    const preferred = reports.value.find((r) => /26l/i.test(r.name)) || reports.value[0];
    if (preferred) await selectReport(preferred.name);
  } catch { showToast('加载评测报告失败', 'error'); }
});
</script>

<style scoped>
/* ══════ 结论卡 ══════ */
.verdict {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-4);
  border-left: 4px solid var(--primary);
}
.verdict.v-ok { border-left-color: var(--level-normal); }
.verdict.v-warn { border-left-color: var(--level-medium); }
.verdict.v-info { border-left-color: var(--primary); }
.verdict-mark { font-size: 30px; line-height: 1; }
.verdict-title { font-size: 16px; font-weight: 700; color: var(--text-primary); margin-bottom: 4px; }
.verdict-text { font-size: 13px; color: var(--text-secondary); line-height: 1.65; }
.verdict-facts { display: flex; gap: var(--space-4); flex-shrink: 0; }
.vf { text-align: center; }
.vf-v {
  font-size: 20px; font-weight: 800; color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}
.vf-l { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
@media (max-width: 1080px) {
  .verdict { grid-template-columns: auto minmax(0, 1fr); }
  .verdict-facts { grid-column: 1 / -1; justify-content: center; }
}

/* ══════ 指标行 ══════ */
.metric-row {
  display: grid; gap: var(--space-3);
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
}
.metric {
  text-align: center; padding: var(--space-3) var(--space-2);
  background: var(--tint-1); border-radius: var(--radius-md);
}
.m-v {
  font-size: 24px; font-weight: 800; color: var(--text-primary);
  font-variant-numeric: tabular-nums; line-height: 1.15;
}
.m-v.warn { color: var(--level-medium); }
.m-l { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }
.m-s { font-size: 10px; color: var(--text-muted); margin-top: 3px; line-height: 1.4; }

/* ══════ 键值列表 ══════ */
.kv-list { display: flex; flex-direction: column; gap: 6px; margin-top: var(--space-3); }
.kv { display: flex; justify-content: space-between; font-size: 12px; }
.kv .k { color: var(--text-muted); }
.kv .v { color: var(--text-primary); font-weight: 600; font-variant-numeric: tabular-nums; }
.kv .v.warn { color: var(--level-medium); }

/* ══════ 栅格内的面板顶边对齐 ══════ */
/* design-refine.css 的 `.panel + .panel { margin-top: var(--space-4) }` 是为竖向
   堆叠写的，可在栅格里第二列同样是"相邻兄弟"，于是每一行的右列被压下 16px、
   与左列顶边错开。属全站性问题，本页就地修正（只在本文件生效）。 */
.page .grid-1-1 > .panel + .panel,
.page .grid-2-1 > .panel + .panel { margin-top: 0; }

/* ══════ 证据模式对比 ══════ */
.mode-grid {
  display: grid; gap: var(--space-3);
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}
.mode-card {
  display: flex; flex-direction: column; align-items: center;
  padding: var(--space-4) var(--space-3);
  background: var(--tint-1); border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
}
.mc-name { font-size: 13px; font-weight: 700; color: var(--text-primary); text-align: center; }
.mc-rate {
  font-size: 32px; font-weight: 800; line-height: 1.15; margin-top: 4px;
  font-variant-numeric: tabular-nums; color: var(--text-primary);
}
.mc-rate.r-high { color: var(--danger-text); }
.mc-rate.r-mid { color: var(--warning-text); }
.mc-rate.r-low { color: var(--success-text); }
.mc-rate-l { font-size: 11px; color: var(--text-muted); }
.mc-track {
  width: 100%; max-width: 380px; height: 8px; margin-top: var(--space-2);
  border-radius: 4px; background: var(--tint-2); overflow: hidden;
}
.mc-fill { height: 100%; border-radius: 4px; transition: width .35s ease; }
.mc-fill.r-high { background: var(--level-high); }
.mc-fill.r-mid { background: var(--level-medium); }
.mc-fill.r-low { background: var(--level-normal); }
.mc-facts {
  display: grid; grid-template-columns: repeat(3, 1fr);
  width: 100%; max-width: 380px; gap: var(--space-2); margin-top: var(--space-3);
}
.mcf { text-align: center; }
.mcf-v {
  font-size: 17px; font-weight: 800; color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}
.mcf-k { font-size: 10px; color: var(--text-muted); margin-top: 1px; }
.mc-sample { font-size: 11px; font-weight: 600; margin-top: var(--space-2); text-align: center; max-width: 380px; }
.mc-sample.s-ok { color: var(--success-text); }
.mc-sample.s-mid { color: var(--warning-text); }
.mc-sample.s-low { color: var(--danger-text); }

/* 差值条：只有事实，没有倾向性措辞 */
.mode-delta {
  display: flex; align-items: center; justify-content: center;
  flex-wrap: wrap; gap: var(--space-4);
  margin-top: var(--space-3); padding: var(--space-3) var(--space-4);
  background: var(--tint-1); border-radius: var(--radius-md);
  border-left: 4px solid var(--primary);
}
.mode-delta.t-ok { border-left-color: var(--level-normal); }
.mode-delta.t-warn { border-left-color: var(--level-medium); }
.mode-delta.t-info { border-left-color: var(--primary); }
.md-num { display: flex; align-items: baseline; gap: 4px; }
.md-v {
  font-size: 30px; font-weight: 800; color: var(--text-primary);
  font-variant-numeric: tabular-nums; line-height: 1;
}
.md-u { font-size: 12px; color: var(--text-muted); }
.md-text { font-size: 13px; font-weight: 600; color: var(--text-secondary); text-align: center; }

/* ══════ 摄像头定位 / 时段分布 ══════ */
.focus-line {
  margin: 0 0 var(--space-3); padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm); background: var(--warning-soft);
  color: var(--warning-text); font-size: 12px; text-align: center;
}
.tbl tr.hot td { background: var(--danger-soft); }
.hour-facts {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: var(--space-2); margin-top: var(--space-3);
}
.hf {
  text-align: center; padding: var(--space-2);
  background: var(--tint-1); border-radius: var(--radius-sm);
}
.hf-v {
  font-size: 17px; font-weight: 800; color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}
.hf-k { font-size: 10px; color: var(--text-muted); margin-top: 2px; line-height: 1.4; }

/* ══════ 复核构成饼图 ══════ */
.pie-cap { font-size: 11px; color: var(--text-muted); text-align: center; margin-top: var(--space-3); }
.review-pie { margin-top: var(--space-2); }

/* ══════ 误报率标签 ══════ */
.rate-chip {
  display: inline-block; min-width: 46px; padding: 2px 8px;
  border-radius: 20px; font-size: 11px; font-weight: 700; text-align: center;
}
.rate-chip.r-high { background: var(--danger-soft); color: var(--danger-text); }
.rate-chip.r-mid { background: var(--warning-soft); color: var(--warning-text); }
.rate-chip.r-low { background: var(--success-soft); color: var(--success-text); }
/* 复核数不足 2 条时，误报率不是"好"也不是"坏"，而是"还看不出来" */
.rate-chip.weak { background: var(--tint-2); color: var(--text-muted); }

.badge-now {
  display: inline-block; margin-left: 6px; padding: 1px 7px;
  border-radius: 20px; font-size: 10px; font-weight: 700;
  background: var(--primary-soft, color-mix(in srgb, var(--primary) 12%, transparent)); color: var(--primary);
}
.tbl tr.current td { background: var(--tint-1); }
.panel-note--lead { max-width: 720px; margin: 0 auto var(--space-3); }
/* 较长的说明文字限宽居中，避免在 1440px 下一行拖成一条难以阅读的长线 */
.panel-note--wide { max-width: 900px; margin-left: auto; margin-right: auto; }
</style>
