<template>
  <div class="page">
    <!-- ══ 机位适用性提示（来自真实评测结论，属产品责任）══ -->
    <div class="placement-notice">
      <div class="pn-head">
        <span class="pn-icon">⚠️</span>
        <span class="pn-title">机位安装建议：请优先采用侧视机位</span>
      </div>
      <div class="pn-body">
        <p>
          本系统的跌倒判定依赖姿态关键点。实测在 <strong>天花板俯视</strong>机位下，
          姿态模型有 <strong>76%</strong> 的画面帧无法提取到有效关键点（人体躺卧时尤其严重），
          会导致告警只能停在"疑似"而无法确认。
        </p>
        <p>
          <strong>推荐</strong>：与地面平行、略高的侧视安装（走廊/房间墙角），
          人体直立与躺卧均可见全身，实测姿态质量可达 0.87–0.99。
        </p>
      </div>
    </div>

    <div class="page-header">
      <div class="header-left">
        <h1>系统监控</h1>
        <div class="page-sub">
          <span class="now-time">{{ lastUpdateTime }}</span>
          <span v-if="autoRefresh" class="auto-badge">🔄 自动刷新</span>
        </div>
      </div>
      <div class="header-actions">
        <button class="action-btn" @click="refreshData" :disabled="loading">
          {{ loading ? '⏳' : '↻' }} {{ loading ? '加载中' : '刷新' }}
        </button>
        <button class="action-btn" @click="toggleAutoRefresh">
          {{ autoRefresh ? '⏸' : '▶' }}
        </button>
      </div>
    </div>

    <div class="monitor-grid">
      <div class="panel panel-health">
        <div class="panel-header">
          <span class="panel-title">🏥 系统健康</span>
        </div>
        <div v-if="health" class="health-content">
          <div :class="['status-badge', 'status-' + health.status]">
            <span class="status-icon">{{ health.status === 'healthy' ? '✅' : health.status === 'degraded' ? '⚠️' : '❌' }}</span>
            <span class="status-text">{{ health.status === 'healthy' ? '健康' : health.status === 'degraded' ? '降级' : '异常' }}</span>
          </div>
          <div class="health-details">
            <div class="health-item">
              <span class="hi-label">数据库</span>
              <span :class="['hi-value', health.components?.database?.status === 'healthy' ? 'val-ok' : 'val-err']">
                {{ health.components?.database?.status === 'healthy' ? '✅ 正常' : '❌ 异常' }}
              </span>
            </div>
            <div class="health-item">
              <span class="hi-label">AI 引擎</span>
              <span :class="['hi-value', health.components?.aiEngine?.status === 'healthy' ? 'val-ok' : 'val-warn']">
                {{ health.components?.aiEngine?.status === 'healthy' ? '✅ 正常' : '⚠️ 未就绪' }}
              </span>
            </div>
            <div class="health-item">
              <span class="hi-label">推理设备</span>
              <span class="hi-value val-ok">{{ health.components?.aiEngine?.device || '-' }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="panel panel-metrics">
        <div class="panel-header">
          <span class="panel-title">📊 性能指标</span>
        </div>
        <div v-if="metrics" class="metrics-grid">
          <div class="metric-item">
            <div class="mi-label">CPU 使用率</div>
            <div class="mi-value">{{ (metrics.cpu?.usage || 0).toFixed(1) }}<span class="mi-unit">%</span></div>
            <div class="mi-bar">
              <div class="mi-bar-fill" :style="{ width: (metrics.cpu?.usage || 0) + '%' }"></div>
            </div>
          </div>
          <div class="metric-item">
            <div class="mi-label">内存使用</div>
            <div class="mi-value">{{ formatBytes(metrics.memory?.used || 0) }}<span class="mi-sub"> / {{ formatBytes(metrics.memory?.total || 0) }}</span></div>
            <div class="mi-bar">
              <div class="mi-bar-fill" :style="{ width: (metrics.memory?.used / metrics.memory?.total * 100 || 0) + '%' }"></div>
            </div>
          </div>
          <div class="metric-item">
            <div class="mi-label">数据库连接</div>
            <div class="mi-value">{{ metrics.database?.activeConnections || 0 }}<span class="mi-sub"> / {{ metrics.database?.maxConnections || 0 }}</span></div>
          </div>
          <div class="metric-item">
            <div class="mi-label">平均响应时间</div>
            <div class="mi-value">{{ (metrics.performance?.avgResponseTime || 0).toFixed(2) }}<span class="mi-unit">ms</span></div>
          </div>
        </div>
      </div>

      <div class="panel panel-requests">
        <div class="panel-header">
          <span class="panel-title">📈 请求统计</span>
        </div>
        <div v-if="metrics?.requests" class="req-grid">
          <div class="req-item">
            <div class="req-label">总请求数</div>
            <div class="req-value">{{ metrics.requests.total || 0 }}</div>
          </div>
          <div class="req-item">
            <div class="req-label">成功</div>
            <div class="req-value val-ok">{{ metrics.requests.success || 0 }}</div>
          </div>
          <div class="req-item">
            <div class="req-label">失败</div>
            <div class="req-value val-err">{{ metrics.requests.error || 0 }}</div>
          </div>
          <div class="req-item">
            <div class="req-label">成功率</div>
            <div class="req-value">{{ ((metrics.requests.success / metrics.requests.total * 100) || 0).toFixed(1) }}%</div>
          </div>
        </div>
      </div>

      <div class="panel panel-system">
        <div class="panel-header">
          <span class="panel-title">💻 系统信息</span>
        </div>
        <div v-if="metrics?.system" class="system-info">
          <div class="si-item"><span class="si-label">操作系统</span><span class="si-value">{{ metrics.system.platform || '-' }}</span></div>
          <div class="si-item"><span class="si-label">运行环境</span><span class="si-value">{{ metrics.system.runtimeVersion || metrics.system.nodeVersion || '-' }}</span></div>
          <div class="si-item"><span class="si-label">运行时长</span><span class="si-value">{{ formatUptime(metrics.system.uptime || 0) }}</span></div>
          <div class="si-item"><span class="si-label">环境</span><span class="si-value">{{ metrics.system.env || '-' }}</span></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import api from '../api/request';

const loading = ref(false);
const health = ref(null);
const metrics = ref(null);
const autoRefresh = ref(true);
const lastUpdateTime = ref('');
let refreshTimer = null;

const refreshData = async () => {
  loading.value = true;
  try {
    const [healthRes, metricsRes] = await Promise.all([
      api.get('/health/detailed'),
      api.get('/monitor/performance')
    ]);
    health.value = healthRes.data;
    metrics.value = metricsRes.data;
    lastUpdateTime.value = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  } catch (error) {
    console.error('获取监控数据失败:', error);
  } finally {
    loading.value = false;
  }
};

const toggleAutoRefresh = () => {
  autoRefresh.value = !autoRefresh.value;
  if (autoRefresh.value) {
    startAutoRefresh();
  } else {
    stopAutoRefresh();
  }
};

const startAutoRefresh = () => {
  refreshTimer = setInterval(refreshData, 10000);
};

const stopAutoRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
};

const formatBytes = (bytes) => {
  if (!bytes) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i];
};

const formatUptime = (seconds) => {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${days}天 ${hours}小时 ${minutes}分钟`;
};

onMounted(() => {
  refreshData();
  if (autoRefresh.value) {
    startAutoRefresh();
  }
});

onUnmounted(() => {
  stopAutoRefresh();
});
</script>

<style scoped>
.page { padding: 24px; min-height: calc(100vh - var(--header-h)); }
.placement-notice { background: var(--warning-soft); border: 1px solid var(--warning); border-radius: var(--radius-md); padding: var(--space-4) var(--space-5); margin-bottom: var(--space-4); }
.pn-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.pn-icon { font-size: 15px; }
.pn-title { font-size: var(--text-md); font-weight: 650; color: var(--warning-text); }
.pn-body p { font-size: var(--text-base); color: var(--text-secondary); line-height: 1.85; margin: 0 0 6px; }
.pn-body p:last-child { margin-bottom: 0; }
.pn-body strong { color: var(--text-primary); }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 22px; gap: 12px; }
.header-left { flex: 1; min-width: 0; }
h1 { font-size: 22px; font-weight: 800; color: var(--text-primary); letter-spacing: -.3px; }
.page-sub { font-size: 12px; color: var(--text-muted); margin-top: 4px; display: flex; align-items: center; gap: 8px; }
.now-time { color: var(--text-muted); }
.auto-badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 20px; font-size: 11px; font-weight: 600; background: color-mix(in srgb, var(--success) 12%, transparent); color: var(--success); border: 1px solid color-mix(in srgb, var(--success) 20%, transparent); }

.header-actions { display: flex; gap: 8px; }
.action-btn { 
  padding: 8px 16px; 
  border-radius: 9px; 
  border: 1px solid var(--tint-4); 
  background: var(--tint-1); 
  color: var(--text-tertiary); 
  cursor: pointer; 
  font-size: 12px; 
  transition: all .2s; 
  white-space: nowrap; 
  flex-shrink: 0; 
  font-weight: 500; 
}
.action-btn:hover:not(:disabled) { background: var(--tint-3); color: var(--text-tertiary); border-color: var(--tint-5); }
.action-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.monitor-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
.panel { background: var(--tint-1); border: 1px solid var(--tint-3); border-radius: var(--radius-md); padding: 16px; }
.panel-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; border-bottom: 1px solid var(--tint-2); padding-bottom: 10px; }
.panel-title { font-size: 12px; font-weight: 700; color: var(--text-tertiary); letter-spacing: .3px; text-transform: uppercase; }

.health-content { display: flex; flex-direction: column; gap: 16px; }
.status-badge { 
  display: flex; 
  align-items: center; 
  justify-content: center; 
  gap: 10px; 
  padding: 16px 24px; 
  border-radius: 12px; 
  border: 1px solid var(--tint-3);
  background: var(--tint-1);
}
.status-badge.status-healthy { border-color: color-mix(in srgb, var(--success) 30%, transparent); background: color-mix(in srgb, var(--success) 8%, transparent); }
.status-badge.status-degraded { border-color: color-mix(in srgb, var(--warning) 30%, transparent); background: color-mix(in srgb, var(--warning) 8%, transparent); }
.status-badge.status-unhealthy { border-color: color-mix(in srgb, var(--danger) 30%, transparent); background: color-mix(in srgb, var(--danger) 8%, transparent); }
.status-icon { font-size: 28px; }
.status-text { font-size: 18px; font-weight: 700; color: var(--text-secondary); }

.health-details { display: flex; flex-direction: column; gap: 8px; }
.health-item { 
  display: flex; 
  justify-content: space-between; 
  align-items: center; 
  padding: 10px 14px; 
  background: var(--tint-1); 
  border-radius: 10px; 
  border: 1px solid var(--tint-2);
}
.hi-label { font-size: 13px; color: var(--text-tertiary); }
.hi-value { font-size: 13px; font-weight: 600; }
.hi-value.val-ok { color: var(--success); }
.hi-value.val-warn { color: var(--warning); }
.hi-value.val-err { color: var(--danger); }

.metrics-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.metric-item { 
  padding: 14px; 
  background: var(--tint-1); 
  border-radius: 10px; 
  border: 1px solid var(--tint-2);
}
.mi-label { font-size: 11px; color: var(--text-tertiary); margin-bottom: 6px; }
.mi-value { 
  font-size: 22px; 
  font-weight: 800; 
  color: var(--text-primary); 
  margin-bottom: 8px; 
  letter-spacing: -.5px;
}
.mi-unit { font-size: 14px; color: var(--text-tertiary); margin-left: 2px; }
.mi-sub { font-size: 13px; color: var(--text-muted); font-weight: 500; }
.mi-bar { height: 6px; background: var(--tint-2); border-radius: 3px; overflow: hidden; }
.mi-bar-fill { 
  height: 100%; 
  background: linear-gradient(90deg, var(--primary) 0%, var(--violet) 100%); 
  border-radius: 3px; 
  transition: width .4s ease;
}

.req-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
.req-item { 
  text-align: center; 
  padding: 14px; 
  background: var(--tint-1); 
  border-radius: 10px; 
  border: 1px solid var(--tint-2);
}
.req-label { font-size: 11px; color: var(--text-tertiary); margin-bottom: 6px; }
.req-value { 
  font-size: 24px; 
  font-weight: 800; 
  color: var(--text-primary); 
  letter-spacing: -.5px;
}
.req-value.val-ok { color: var(--success); }
.req-value.val-err { color: var(--danger); }

.system-info { display: flex; flex-direction: column; gap: 8px; }
.si-item { 
  display: flex; 
  justify-content: space-between; 
  align-items: center; 
  padding: 10px 14px; 
  background: var(--tint-1); 
  border-radius: 10px; 
  border: 1px solid var(--tint-2);
}
.si-label { font-size: 13px; color: var(--text-tertiary); }
.si-value { font-size: 13px; font-weight: 600; color: var(--text-secondary); }

@media (max-width: 1200px) {
  .monitor-grid { grid-template-columns: 1fr; }
  .metrics-grid { grid-template-columns: 1fr; }
}

@media (max-width: 768px) {
  .page { padding: 16px; }
  h1 { font-size: 19px; }
  .page-header { flex-wrap: wrap; gap: 8px; align-items: flex-start; }
  .header-actions {
    width: 100%;
  }
  .action-btn {
    flex: 1;
  }
  .monitor-grid { grid-template-columns: 1fr; gap: 12px; }
  .metrics-grid { grid-template-columns: 1fr; }
  .req-grid { grid-template-columns: 1fr; }
  .status-badge { 
    padding: 14px 20px; 
    gap: 8px; 
  }
  .status-icon { font-size: 24px; }
  .status-text { font-size: 16px; }
  .mi-value { font-size: 20px; }
  .req-value { font-size: 22px; }
}
</style>
