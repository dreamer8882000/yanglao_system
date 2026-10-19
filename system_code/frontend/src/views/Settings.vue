<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1>系统设置</h1>
        <div class="page-sub">配置 AI 检测参数、设备与账号管理</div>
      </div>
    </div>

    <div class="tabs">
      <button v-for="tab in tabs" :key="tab.key" class="tab-btn"
        :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key">
        {{ tab.label }}
      </button>
    </div>

    <!-- AI 参数 -->
    <div v-if="activeTab === 'ai'" class="settings-section">
      <!-- ── 这一段用「一条真实的决策链」替代原来的假区间 ──────────────────
           原界面把 alert_bounds 的四个**边界点**画成了三个"区间"（LOW 20~50、
           MEDIUM 50~80），但 lowMax / mediumMax 后端根本不读 —— 只有两个起点生效。
           照着"区间"去调，永远调不出预期效果，这正是"不知道在这里要做什么"的来源。
           现在按引擎真实的判定顺序摆放：上游是跌倒判据的触发线，下游是融合信念的分级线。-->
      <div class="section-title">AI 判定参数</div>

      <div class="chain-intro">
        引擎的判定是一条链，下面三段分别对应链上的三个位置：
        <div class="chain-flow">
          <span class="chain-node pose">姿态 <b>fall_score</b></span>
          <span class="chain-arrow">→<em>①触发线</em></span>
          <span class="chain-node expr">表情分支</span>
          <span class="chain-arrow">→<em>D-S 融合</em></span>
          <span class="chain-node fuse">跌倒信念 <b>m(F)</b></span>
          <span class="chain-arrow">→<em>②分级线</em></span>
          <span class="chain-node alert">5 级告警</span>
        </div>
      </div>

      <!-- ① 跌倒判据触发线 -->
      <div class="setting-group">
        <div class="group-title">① 跌倒判据触发线 <span class="group-hint">决定"这一帧算不算跌倒样、要不要调表情分支"</span></div>
        <div class="setting-item">
          <div class="setting-info">
            <div class="setting-name">姿态跌倒分触发阈值</div>
            <div class="setting-desc">
              姿态 <b>fall_score</b> 达到此值才算"跌倒样"，并触发表情分支做二次确认。
              调低 → 更敏感（召回↑、误报↑）；调高 → 更保守。
            </div>
          </div>
          <div class="slider-wrap">
            <input type="range" v-model.number="aiConfig.fallThreshold" min="10" max="90" step="5" class="slider" />
            <span class="slider-val">{{ aiConfig.fallThreshold }}%</span>
          </div>
        </div>
      </div>

      <!-- ② 告警分级边界 -->
      <div class="setting-group">
        <div class="group-title">② 告警分级边界 <span class="group-hint">把融合后的跌倒信念 m(F) 切成 5 档</span></div>
        <div class="bound-strip">
          <!-- 每段宽度 = 该档的实际区间长度，五个边界点依次是
               m(F) 达到 lowMin / mediumMin / highMin / urgentMin 时的分档。
               写成 flex 之后各段按比例分配整条宽度，拖动滑块即时变化。 -->
          <div class="bound-seg" :style="{ flex: Math.max(1, aiConfig.lowMin) }"><span class="bs-name normal">NORMAL</span></div>
          <div class="bound-seg" :style="{ flex: Math.max(1, aiConfig.mediumMin - aiConfig.lowMin) }"><span class="bs-name low">LOW</span></div>
          <div class="bound-seg" :style="{ flex: Math.max(1, aiConfig.highMin - aiConfig.mediumMin) }"><span class="bs-name medium">MEDIUM</span></div>
          <div class="bound-seg" :style="{ flex: Math.max(1, aiConfig.urgentMin - aiConfig.highMin) }"><span class="bs-name high">HIGH</span></div>
          <div class="bound-seg" :style="{ flex: Math.max(1, 100 - aiConfig.urgentMin) }"><span class="bs-name urgent">URGENT</span></div>
        </div>
        <div class="bound-note">
          条形的宽度就是各档的**实际范围**（由四个边界点决定）。拖动下面的边界点，
          上面这条会立刻跟着变。
        </div>
        <div class="setting-item" v-for="b in bounds" :key="b.key">
          <div class="setting-info">
            <div class="setting-name">{{ b.label }} 边界</div>
            <div class="setting-desc">m(F) 高于 <b>{{ aiConfig[b.key] }}%</b> 时判为 {{ b.label }} 及以上</div>
          </div>
          <div class="slider-wrap">
            <input type="range" v-model.number="aiConfig[b.key]" :min="b.min" :max="b.max" step="5" class="slider" />
            <span class="slider-val">{{ aiConfig[b.key] }}%</span>
          </div>
        </div>
        <div v-if="boundWarning" class="group-warn">⚠ {{ boundWarning }}</div>
      </div>

      <!-- ③ 表情分支 -->
      <div class="setting-group">
        <div class="group-title">③ 表情分支 <span class="group-hint">它不决定"是否跌倒"，只决定"是否痛苦"</span></div>
        <div class="setting-item">
          <div class="setting-info">
            <div class="setting-name">表情模型置信度阈值</div>
            <div class="setting-desc">
              低于此值的检测框会被丢弃，该帧记为<b>「表情证据未知」</b>——
              注意是"未知"，不是"无痛苦"。它<b>不直接决定告警是否触发</b>：
              跌倒与否由姿态轴判定，表情只在已确认跌倒后决定紧急程度。
            </div>
          </div>
          <div class="slider-wrap">
            <input type="range" v-model.number="aiConfig.minConfidence" min="5" max="90" step="5" class="slider" />
            <span class="slider-val">{{ aiConfig.minConfidence }}%</span>
          </div>
        </div>
      </div>

      <!-- 全局推理模型 -->
      <div class="model-section">
        <div class="model-section-header">
          <div>
            <div class="model-section-title">全局 AI 推理模型</div>
            <div class="model-section-desc">配置摄像头是否启用后台本地 AI 推理，统一应用到本机构所有摄像头</div>
          </div>
          <span class="model-cam-count">{{ cameras.length }} 台摄像头</span>
        </div>
        <div class="yolo-model-grid">
          <button v-for="m in yoloModels" :key="m.value"
            class="yolo-model-card"
            :class="{ active: globalYoloModels.includes(m.value), disabled: m.value === 'none' && globalYoloModels.length > 1 }"
            type="button"
            @click="toggleYoloModel(m.value)"
            :disabled="m.value === 'none' && globalYoloModels.length > 1">
            <span class="yolo-card-icon">{{ m.icon }}</span>
            <span class="yolo-card-label">{{ m.label }}</span>
            <span class="yolo-card-desc">{{ m.desc }}</span>
            <span v-if="globalYoloModels.includes(m.value)" class="yolo-card-check">✓</span>
          </button>
        </div>
        <div class="model-effect-bar">
          <div v-if="globalYoloModels.length" class="model-effect-dots">
            <span v-for="model in globalYoloModels" :key="model"
              class="model-effect-dot" :class="model"></span>
          </div>
          <span v-else class="model-effect-dot none"></span>
          <span class="model-effect-text">
            当前选择：<strong v-if="globalYoloModels.length">{{ globalYoloModels.map(m => yoloModelLabel(m)).join(' + ') }}</strong>
            <strong v-else>未选择模型</strong>
            <span v-if="globalYoloModels.length === 2" class="model-limit-hint">（已达上限）</span>
          </span>
        </div>
      </div>

      <div class="save-row">
        <button class="btn-save" :disabled="aiSaving || !!aiLoadError" @click="saveAiConfig">
          {{ aiSaving ? '保存中…' : '保存 AI 配置' }}
        </button>
        <!-- 保存后回显**实际生效**的参数：后端返回 appliedAiParams，
             原先前端没用它。没有这个回显，用户无法判断"到底改生效了没有"——
             而页面之前恰好有几个控件是保存成功但不生效的。 -->
        <span v-if="appliedParams.length" class="save-applied">
          已生效：{{ appliedParams.join('、') }}
        </span>
      </div>
      <div v-if="aiLoadError" class="load-error">{{ aiLoadError }}</div>
    </div>

    <!-- 摄像头管理 -->
    <div v-if="activeTab === 'camera'" class="settings-section">
      <div class="section-title">摄像头设备管理</div>
      <div class="camera-list">
        <div v-for="(cam, i) in camPaged" :key="cam.id || i" class="camera-row">
          <div class="cam-status-dot" :class="cam.status === 1 ? 'online' : 'offline'"></div>
          <div class="cam-type-badge">{{ srcTypeIcon(cam.sourceType) }}</div>
          <div class="cam-info">
            <div class="cam-name">{{ cam.name }}</div>
            <div class="cam-room">{{ cam.roomNo ? cam.roomNo + '室' : '未绑定' }} · {{ srcTypeText(cam.sourceType) }} · {{ cam.status === 1 ? '在线' : '离线' }}</div>
            <div class="cam-url" v-if="cam.streamUrl">{{ cam.streamUrl }}</div>
          </div>
          <div class="cam-actions">
            <button class="btn-sm" @click="editCamera(cam)">编辑</button>
            <button class="btn-sm danger" @click="deleteCamera(cam)">删除</button>
          </div>
        </div>
        <div v-if="!cameras.length && !loadErrors.camera" class="empty-cam">暂无摄像头，点击下方添加</div>
        <div v-if="loadErrors.camera" class="load-error">{{ loadErrors.camera }}</div>
      </div>
      <button class="btn-add" @click="openAddCamera">+ 添加摄像头</button>
        <Pagination
          v-model:page="camPage" v-model:pageSize="camPageSize"
          :total="camTotal"
        />
    </div>

    <!-- 通知配置 -->
    <!-- 告警通知 -->
    <div v-if="activeTab === 'notify'" class="settings-section">
      <div class="section-title-row">
        <div class="section-title">告警通知渠道</div>
      </div>
      <div class="notify-intro">
        告警在这里通过外部渠道把人<b>叫醒</b>——企业微信/钉钉群、邮件。
        页面内的实时推送（SSE）只在有人开着这个系统时才有效，而跌倒告警最需要
        送达的恰恰是<b>护士不在电脑前</b>的时刻。
        <br />
        <span class="notify-intro-dim">
          未配置的渠道会明确记为「未发送」并写明原因，<b>不会假装成功</b>——
          一个静默失败的通知系统比没有通知更危险，它让人以为已经有人被叫醒了。
        </span>
      </div>

      <div class="toolbar">
        <span class="toolbar-label">共 {{ notifyChannels.length }} 个渠道</span>
        <button class="toolbar-reset" @click="loadNotifyLogs()" :disabled="logsLoading">刷新投递记录</button>
        <div class="toolbar-actions">
          <button class="btn-add-user" @click="openChannelModal()">+ 新增渠道</button>
        </div>
      </div>

      <div v-if="loadErrors.channel" class="load-error">{{ loadErrors.channel }}</div>
      <div v-else-if="!notifyChannels.length" class="empty-cam">
        还没有通知渠道。只靠页面内推送的话，护士离开电脑就收不到任何告警。
      </div>
      <div v-else class="channel-list">
        <div class="channel-header">
          <span>渠道</span><span>类型</span><span>最低等级</span><span>状态</span><span>操作</span>
        </div>
        <div v-for="c in notifyChannels" :key="c.id" class="channel-row">
          <span class="ch-name">
            {{ c.name }}
            <span v-if="!c.enabled" class="ch-off">已停用</span>
          </span>
          <span class="ch-type">{{ typeLabel(c.type) }}</span>
          <span><span class="lvl" :class="'lvl-' + (c.minLevel || '').toLowerCase()">{{ levelLabel(c.minLevel) }}</span></span>
          <span class="ch-target" :title="c.config && c.config.webhook ? c.config.webhook : ''">
            {{ channelTarget(c) }}
          </span>
          <span class="ch-ops row-actions">
            <button class="btn-sm" :disabled="c._testing" @click="testChannel(c)">
              {{ c._testing ? '发送中…' : '测试发送' }}
            </button>
            <button class="btn-sm" @click="toggleChannel(c)">{{ c.enabled ? '停用' : '启用' }}</button>
            <button class="btn-sm" @click="openChannelModal(c)">编辑</button>
            <button class="btn-sm danger" @click="removeChannel(c)">删除</button>
          </span>
        </div>
      </div>

      <!-- 投递记录：排查"我没收到告警"的唯一依据 -->
      <div class="section-title" style="margin-top:24px">投递记录</div>
      <div class="notify-intro">
        每一次投递都留痕：渠道、目标、成败、错误原文、耗时、触发原因、当时的等级。
        没有这张表，"我没收到告警"就永远查不出原因。
      </div>
      <div class="toolbar">
        <select v-model="logFilters.status" class="toolbar-field" @change="resetLogPage">
          <option value="">全部状态</option>
          <option value="success">成功</option>
          <option value="failed">失败</option>
          <option value="skipped">未发送</option>
        </select>
        <select v-model="logFilters.channelType" class="toolbar-field" @change="resetLogPage">
          <option value="">全部渠道类型</option>
          <option value="wecom">企业微信</option>
          <option value="dingtalk">钉钉</option>
          <option value="email">邮件</option>
        </select>
        <span v-if="logStats" class="toolbar-label">
          成功 {{ logStats.success || 0 }} · 失败 {{ logStats.failed || 0 }} · 未发送 {{ logStats.skipped || 0 }}
        </span>
        <button class="toolbar-reset" :disabled="!logFilterActive" @click="resetLogFilters">重置</button>
      </div>

      <div v-if="logsLoading" class="empty-cam">加载中...</div>
      <div v-else-if="loadErrors.log" class="load-error">{{ loadErrors.log }}</div>
      <div v-else-if="!notifyLogs.length" class="empty-cam">暂无投递记录</div>
      <div v-else class="log-list">
        <div class="log-header">
          <span>时间</span><span>渠道</span><span>目标</span><span>状态</span><span>说明</span><span>耗时</span>
        </div>
        <div v-for="l in notifyLogs" :key="l.id" class="log-row">
          <span class="log-time">{{ formatTime(l.createdAt) }}</span>
          <span>{{ l.channelName || l.channelType }}</span>
          <span class="log-target" :title="l.target">{{ l.target || '—' }}</span>
          <span><span class="log-status" :class="'ls-' + l.status">{{ statusLabel(l.status) }}</span></span>
          <span class="log-err" :title="l.error">
            {{ l.error || reasonLabel(l.reason) }}
          </span>
          <span class="log-ms">{{ l.durationMs != null ? l.durationMs + 'ms' : '—' }}</span>
        </div>
      </div>
      <Pagination v-if="!logsLoading" v-model:page="logPagination.page"
                  v-model:pageSize="logPagination.pageSize" :total="logPagination.total"
                  @change="loadNotifyLogs" />

      <!-- 渠道弹框 -->
      <div v-if="channelModal.show" class="modal-mask" @click.self="channelModal.show = false">
        <div class="modal-box wide">
          <h3>{{ channelModal.isEdit ? '编辑通知渠道' : '新增通知渠道' }}</h3>
          <div class="field-group">
            <label>渠道类型 <span class="req">*</span></label>
            <select v-model="channelModal.form.type" :disabled="channelModal.isEdit">
              <option v-for="t in notifyTypes" :key="t.type" :value="t.type">{{ t.label }}</option>
            </select>
            <div v-if="currentTypeHint" class="field-hint">{{ currentTypeHint }}</div>
          </div>
          <div class="field-group">
            <label>渠道名称 <span class="req">*</span></label>
            <input v-model="channelModal.form.name" placeholder="如：夜班值班群" />
          </div>
          <div class="field-group">
            <label>最低触发等级 <span class="req">*</span></label>
            <select v-model="channelModal.form.minLevel">
              <option v-for="l in notifyLevels" :key="l.value" :value="l.value">
                {{ l.label }}（{{ l.value }}）及以上
              </option>
            </select>
            <div class="field-hint">低于该等级的告警不会发到这个渠道，但仍会记一条「未发送」。</div>
          </div>
          <!-- 字段清单由后端 /notifications/types 提供，避免前后端各写一份 -->
          <div class="field-group" v-for="f in currentTypeFields" :key="f.key">
            <label>{{ f.label }}<span v-if="f.required" class="req"> *</span></label>
            <select v-if="f.type === 'bool'" v-model="channelModal.form.config[f.key]">
              <option :value="false">否</option>
              <option :value="true">是</option>
            </select>
            <input v-else v-model="channelModal.form.config[f.key]"
                   :type="f.secret ? 'password' : 'text'"
                   :placeholder="f.key === 'webhook' ? 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=…' : ''" />
          </div>
          <div class="modal-actions">
            <button class="btn-cancel" @click="channelModal.show = false">取消</button>
            <button class="btn-confirm" :disabled="channelModal.saving" @click="submitChannel">
              {{ channelModal.saving ? '保存中…' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </div>


    <!-- 账号权限 -->
    <div v-if="activeTab === 'account'" class="settings-section">
      <div class="section-title-row">
        <div class="section-title">账号与权限管理</div>
      </div>

      <div class="toolbar">
        <input v-model="accFilters.keyword" class="toolbar-search"
          placeholder="账号 / 姓名 / 科室" @input="applyAccFilters(true)" />
        <select v-model="accFilters.role" class="toolbar-field" @change="applyAccFilters()">
          <option value="">全部角色</option>
          <option value="admin">机构管理员</option>
          <option value="nurse">护理管理员</option>
        </select>
        <button class="toolbar-reset" :disabled="!accFilterActive" @click="resetAccFilters">重置</button>
        <div class="toolbar-actions">
          <button v-if="currentUserRole === 'admin'" class="btn-add-user" @click="openAddUser">+ 新建账号</button>
        </div>
      </div>

      <div v-if="accountLoading" class="empty-cam">加载中...</div>
      <div v-else class="account-list">
        <div class="account-header">
          <span>账号</span><span>姓名</span><span>部门</span><span>角色</span><span>操作</span>
        </div>
        <div v-for="acc in accounts" :key="acc.id" class="account-row">
          <span class="acc-username">{{ acc.username }}</span>
          <span class="acc-name">{{ acc.name || '-' }}</span>
          <span class="acc-dept">{{ acc.deptName || '-' }}</span>
          <span>
            <select v-model="acc.role" class="role-select" @change="updateRole(acc)">
              <option value="admin">机构管理员</option>
              <option value="nurse">护理管理员</option>
            </select>
          </span>
          <span class="acc-ops row-actions">
            <button class="btn-del-user" @click="confirmDeleteUser(acc)">删除</button>
          </span>
        </div>
        <div v-if="!accounts.length && !loadErrors.account" class="empty-cam">暂无账号数据</div>
      </div>
      <div v-if="loadErrors.account" class="load-error">{{ loadErrors.account }}</div>
      <div v-if="!accountLoading" class="account-mobile">
        <div v-for="acc in accounts" :key="'m'+acc.id" class="acc-card">
          <div class="acc-card-top">
            <span class="acc-username">{{ acc.username }}</span>
            <span class="acc-role-badge" :class="acc.role">{{ acc.role === 'admin' ? 'admin' : 'nurse' }}</span>
          </div>
          <div class="acc-card-info">{{ acc.name || '-' }} · {{ acc.deptName || '-' }}</div>
          <div class="acc-card-actions">
            <select v-model="acc.role" class="role-select full" @change="updateRole(acc)">
              <option value="admin">机构管理员</option>
              <option value="nurse">护理管理员</option>
            </select>
            <button class="btn-del-user" @click="confirmDeleteUser(acc)">删除</button>
          </div>
        </div>
      </div>
      <!-- 分页放在桌面/移动两套视图之外：放进 .account-list 里的话，
           窄屏下它会被 display:none 一起隐藏，手机上就没法翻页了。 -->
      <Pagination
        v-if="!accountLoading"
        v-model:page="accPage" v-model:pageSize="accPageSize"
        :total="accTotal" @change="loadAccounts"
      />
    </div>

    <!-- 摄像头弹框 -->
    <div v-if="cameraModal.show" class="modal-mask" @click.self="cameraModal.show = false">
      <div class="modal-box wide">
        <div class="modal-header">
          <h3>{{ cameraModal.isEdit ? '编辑摄像头' : '添加摄像头' }}</h3>
          <button class="close-btn" @click="cameraModal.show = false">×</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <div class="field-group">
              <label>摄像头名称 <span class="req">*</span></label>
              <input v-model="cameraForm.name" placeholder="如：走廊-东侧" />
            </div>
            <div class="field-group">
              <label>绑定房间号 <span class="req">*</span></label>
              <input v-model="cameraForm.roomNo" placeholder="如：101" />
            </div>
          </div>
          <div class="field-group">
            <label>视频源类型 <span class="req">*</span></label>
            <div class="src-type-grid">
              <button v-for="t in srcTypes" :key="t.value"
                class="src-type-card" :class="{ active: cameraForm.sourceType === t.value }"
                type="button" @click="selectSrcType(t.value)">
                <span class="src-card-icon">{{ t.icon }}</span>
                <span class="src-card-label">{{ t.label }}</span>
                <span class="src-card-desc">{{ t.desc }}</span>
              </button>
            </div>
          </div>
          <div v-if="cameraForm.sourceType && cameraForm.sourceType !== 'local'" class="field-group">
            <label>流地址 <span class="req">*</span></label>
            <input v-model="cameraForm.streamUrl" :placeholder="urlPlaceholder" />
          </div>
          <div v-if="cameraForm.sourceType === 'local'" class="src-config-block local-block">
            <div class="local-tip-box">
              <span class="tip-icon">🖥️</span>
              <div>
                <div class="tip-title">使用本机摄像头</div>
                <div class="tip-body">系统将通过浏览器调用本机摄像头（需授权），无需填写地址。</div>
              </div>
            </div>
          </div>
          <div class="field-group">
            <label>备注</label>
            <input v-model="cameraForm.note" placeholder="可选备注信息" />
          </div>
          <!-- 提示：模型统一在 AI 参数中配置 -->
          <div class="model-tip-box">
            <span class="model-tip-icon">🤖</span>
            <div>
              <div class="model-tip-title">AI 推理模型由全局配置统一决定</div>
              <div class="model-tip-body">当前全局模型：<strong>{{ globalYoloModels.length ? globalYoloModels.map(m => yoloModelLabel(m)).join(' + ') : '未配置' }}</strong>，如需更改请前往「AI 参数」tab 配置。</div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="cameraModal.show = false">取消</button>
          <button class="btn-primary" @click="saveCamera">保存</button>
        </div>
      </div>
    </div>

    <!-- 新建用户弹框 -->
    <div v-if="userModal.show" class="modal-mask" @click.self="userModal.show = false">
      <div class="modal-box">
        <div class="modal-header">
          <h3>新建账号</h3>
          <button class="close-btn" @click="userModal.show = false">×</button>
        </div>
        <div class="modal-body">
          <div class="field-group">
            <label>登录账号 <span class="req">*</span></label>
            <input v-model="userForm.username" placeholder="英文账号，如：zhangsan" />
          </div>
          <div class="field-group">
            <label>姓名 <span class="req">*</span></label>
            <input v-model="userForm.name" placeholder="真实姓名" />
          </div>
          <div class="field-group">
            <label>初始密码 <span class="req">*</span></label>
            <input v-model="userForm.password" type="password" placeholder="至少 6 位" />
          </div>
          <div class="field-group">
            <label>角色</label>
            <select v-model="userForm.role">
              <option value="nurse">护理管理员</option>
              <option value="admin">机构管理员</option>
            </select>
          </div>
          <div class="field-group">
            <label>邮箱</label>
            <input v-model="userForm.email" placeholder="可选" type="email" />
          </div>
          <div class="field-group">
            <label>部门</label>
            <input v-model="userForm.deptName" placeholder="可选" />
          </div>
          <div v-if="userModal.error" class="form-error">{{ userModal.error }}</div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="userModal.show = false">取消</button>
          <button class="btn-primary" @click="submitAddUser" :disabled="userModal.loading">
            {{ userModal.loading ? '创建中...' : '创建账号' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { usePaging } from '../composables/usePaging.js';
import Pagination from '../components/Pagination.vue';
import { getCameraList, createCamera, updateCamera, deleteCamera as deleteCameraApi } from '../api/cameras.js';
import { getSettings, saveSettings, setGlobalYoloModel, getUserList, updateUserRole, createUser, deleteUser,
         getNotifyTypes, getNotifyChannels, createNotifyChannel, updateNotifyChannel,
         deleteNotifyChannel, testNotifyChannel, getNotifyLogs } from '../api/users.js';
import { showToast } from '../utils/index.js';

const activeTab = ref('ai');
const aiSaving = ref(false);

// ── 加载失败必须说出来 ──────────────────────────────────────────────
// 这几个区块原来都是 `catch {}`：加载失败后仍然渲染**默认值**。
// 其中 AI 参数页最危险 —— 默认值和数据库里的真实值长得一模一样，
// 管理员看不出任何异常，此时点「保存 AI 配置」就是**用默认值覆盖真实配置**。
// 所以失败时 (i) 显式报错、(ii) 禁用保存；只做其一会留下破坏路径。
const loadErrors = ref({ ai: '', camera: '', account: '', channel: '', log: '' });
function setLoadError(key, message) {
  loadErrors.value = { ...loadErrors.value, [key]: message };
}
const aiLoadError = computed(() => loadErrors.value.ai);
function failText(e, fallback) {
  return e?.friendlyMessage || fallback;
}
const currentUserRole = computed(() => {
  try { return JSON.parse(sessionStorage.getItem('current_user') || '{}').role || 'nurse'; } catch { return 'nurse'; }
});
const tabs = [
  { key: 'ai', label: '🤖 AI 参数' },
  { key: 'camera', label: '📷 摄像头' },
  { key: 'notify', label: '🔔 通知' },
  { key: 'account', label: '👤 账号' },
];

const srcTypes = [
  { value: 'local', icon: '🖥️', label: '本地', desc: '浏览器摄像头' },
  { value: 'hls', icon: '📡', label: 'HLS', desc: 'M3U8 直播流' },
  { value: 'webrtc', icon: '⚡', label: 'WebRTC', desc: '超低延迟' },
  { value: 'rtsp', icon: '🔌', label: 'RTSP', desc: 'IP摄像头协议' },
  { value: 'mjpeg', icon: '📷', label: 'MJPEG', desc: '树莓派/手机' },
  { value: 'mp4', icon: '🎬', label: 'MP4', desc: '视频文件' },
];

const urlPlaceholders = {
  hls: 'http://192.168.1.100:8080/live/stream.m3u8',
  rtsp: 'rtsp://user:pass@192.168.1.100:554/stream',
  mjpeg: 'http://192.168.1.100:8080/?action=stream',
  mp4: 'http://example.com/video.mp4',
  webrtc: 'ws://192.168.1.100:8080/webrtc/stream',
};
const urlPlaceholder = computed(() => urlPlaceholders[cameraForm.value.sourceType] || '请输入流地址');

function srcTypeIcon(type) { return srcTypes.find(t => t.value === type)?.icon || '📹'; }
function srcTypeText(type) { return srcTypes.find(t => t.value === type)?.label || '未知'; }

const yoloModels = [
  { value: 'pose', icon: '🦴', label: '融合推理', desc: '姿态估计 + 表情识别 + D-S 风险融合' },
  { value: 'face', icon: '😶', label: '表情辅助', desc: '跌倒风险触发后裁剪人脸并识别表情' },
  { value: 'none', icon: '⭕', label: '不启用',   desc: '仅视频流，不推理' },
];
function yoloModelLabel(m) { return yoloModels.find(x => x.value === m)?.label || '融合推理'; }

// AI 判定参数。键名与后端 apply_ai_config 的入参一一对应 ——
// 这里**不再有 lowMax / mediumMax**：它们只是被存进 settings，后端从不读取，
// 留着会让人以为在配"区间"。真正的四个边界点是下面这四条。
const aiConfig = ref({ fallThreshold: 30, lowMin: 20, mediumMin: 40, highMin: 60,
                       urgentMin: 80, minConfidence: 25 });

// 保存后实际生效的参数名（后端 appliedAiParams）
const appliedParams = ref([]);

// 四个边界点。min/max 只是滑块范围，真正的约束是"必须严格递增"（见 boundWarning）。
const bounds = [
  { key: 'lowMin', label: 'LOW', min: 5, max: 95 },
  { key: 'mediumMin', label: 'MEDIUM', min: 5, max: 95 },
  { key: 'highMin', label: 'HIGH', min: 5, max: 95 },
  { key: 'urgentMin', label: 'URGENT', min: 5, max: 95 },
];

// 边界必须严格递增：否则某个档位会得到"空区间"，永远不会被判定到，
// 界面上那条分级条也会出现宽度为 0 的段 —— 那时告警等级会静默地少一档。
const boundWarning = computed(() => {
  const v = aiConfig.value;
  const seq = [['LOW', v.lowMin], ['MEDIUM', v.mediumMin], ['HIGH', v.highMin], ['URGENT', v.urgentMin]];
  for (let i = 1; i < seq.length; i++) {
    if (seq[i][1] <= seq[i - 1][1]) {
      return `${seq[i][0]} 边界（${seq[i][1]}%）必须高于 ${seq[i - 1][0]} 边界（${seq[i - 1][1]}%），否则该档位永远不会被判定到`;
    }
  }
  return '';
});
const globalYoloModels = ref([]);
const notifyConfig = ref({ hiEnabled: true, smsEnabled: true, receivers: '' });
const cameras = ref([]);
const accounts = ref([]);
// 摄像头仍旧是客户端分页：接口一次返回全部，数据量小但同样需要翻页能力。
const { page: camPage, pageSize: camPageSize, total: camTotal, paged: camPaged }
  = usePaging(cameras, 10);
// 账号改为服务端分页：筛选条件必须和 page/pageSize 一起发给后端，
// 否则只会筛当前这一页，total 也会是全部账号数，翻页全是错的。
const accPage = ref(1);
const accPageSize = ref(10);
const accTotal = ref(0);
const accFilters = ref({ keyword: '', role: '' });
/** 去掉空条件，避免把 keyword= 这类空值发到后端 */
const cleanParams = (o) => Object.fromEntries(
  Object.entries(o).filter(([, v]) => v !== '' && v !== null && v !== undefined));
const accFilterActive = computed(() => !!(accFilters.value.keyword || accFilters.value.role));
const accountLoading = ref(false);
const cameraModal = ref({ show: false, isEdit: false, editIndex: -1 });
const cameraForm = ref({ name: '', roomNo: '', sourceType: 'rtsp', streamUrl: '', note: '' });
const userModal = ref({ show: false, loading: false, error: '' });
const userForm = ref({ username: '', name: '', password: '', role: 'nurse', email: '', deptName: '' });

function selectSrcType(val) { cameraForm.value.sourceType = val; if (val === 'local') cameraForm.value.streamUrl = ''; }

function toggleYoloModel(value) {
  if (value === 'none') {
    globalYoloModels.value = ['none'];
    return;
  }
  const index = globalYoloModels.value.indexOf(value);
  if (index > -1) {
    globalYoloModels.value.splice(index, 1);
  } else if (globalYoloModels.value.length < 2) {
    globalYoloModels.value = globalYoloModels.value.filter(m => m !== 'none');
    globalYoloModels.value.push(value);
  }
}

async function loadSettings() {
  try {
    const res = await getSettings();
    if (res.data.success && res.data.data) {
      const s = res.data.data;
      const aiRaw = typeof s.aiConfig === 'string' ? JSON.parse(s.aiConfig) : s.aiConfig;
      const notifyRaw = typeof s.notifyConfig === 'string' ? JSON.parse(s.notifyConfig) : s.notifyConfig;
      if (aiRaw) {
        // 只接纳**页面真正认识**的键。库里的历史配置还留着 lowMax / mediumMax
        // （它们后端从不读取），直接展开合并会把这些死键一路带着、每次保存又写回去，
        // 于是"已经删掉的控件"永远留在数据里，下次有人看到又以为它有用。
        const known = Object.keys(aiConfig.value);
        const clean = Object.fromEntries(
          Object.entries(aiRaw).filter(([k, v]) => known.includes(k) && v !== null && v !== ''));
        aiConfig.value = { ...aiConfig.value, ...clean };
      }
      if (notifyRaw) notifyConfig.value = { ...notifyConfig.value, ...notifyRaw };
      if (s.globalYoloModels) {
        const models = typeof s.globalYoloModels === 'string' ? JSON.parse(s.globalYoloModels) : s.globalYoloModels;
        if (Array.isArray(models)) globalYoloModels.value = models.filter(m => ['pose', 'face', 'none'].includes(m));
      } else if (!globalYoloModels.value.length) {
        globalYoloModels.value = ['pose'];
      }
    }
    setLoadError('ai', '');
  } catch (e) {
    console.error('加载 AI 配置失败', e);
    setLoadError('ai', `AI 配置未能从服务端加载（${failText(e, '未知错误')}）。`
      + '当前显示的是页面默认值，不是数据库里的真实配置，因此已禁用保存。');
  }
}

async function loadCameras() {
  try {
    const res = await getCameraList({ page: 1, pageSize: 100 });
    // /cameras/ 现在返回 {data,total,page,pageSize}（与全站列表契约一致）
    if (res.data.success) cameras.value = res.data.data?.data || [];
    setLoadError('camera', '');
  } catch (e) {
    console.error('加载摄像头列表失败', e);
    // 关键：**不能**让"接口挂了"显示成"设备没了"。这两个结论对使用者
    // 的行动完全不同：前者去查服务，后者以为真的没装摄像头。
    setLoadError('camera', `摄像头列表加载失败：${failText(e, '未知错误')}`);
  }
}

async function loadAccounts() {
  accountLoading.value = true;
  try {
    // /settings/users 是分页接口，返回 { data:[...], total, page, pageSize }。
    // 原实现把分页对象直接赋给 accounts，数组判定失败 —— 账号列表因此是错的；
    // 后来改成"一次取 100 条再切片"的客户端分页，筛选条件就只能在当前页里找，
    // 换成服务端分页后 keyword / role 与 total 由后端一起算，翻页才正确。
    const res = await getUserList({
      ...cleanParams(accFilters.value),
      page: accPage.value, pageSize: accPageSize.value
    });
    if (res.data.success) {
      const d = res.data.data;
      accounts.value = Array.isArray(d) ? d : (d?.data || []);
      accTotal.value = Array.isArray(d) ? d.length : (d?.total || 0);
    }
    setLoadError('account', '');
  } catch (e) {
    console.error('加载账号列表失败', e);
    setLoadError('account', `账号列表加载失败：${failText(e, '未知错误')}`);
  } finally { accountLoading.value = false; }
}

/**
 * 条件变化 → 回到第 1 页再取数。
 * Pagination 只在换每页条数时自动回第 1 页；条件变化不在它的职责里，
 * 不回第 1 页就会停在越界页（例如筛完只剩 1 页却停在第 2 页）显示空白。
 */
let accTimer = null;
function applyAccFilters(debounced = false) {
  clearTimeout(accTimer);
  const run = () => { accPage.value = 1; loadAccounts(); };
  if (debounced) accTimer = setTimeout(run, 300); else run();
}
function resetAccFilters() {
  clearTimeout(accTimer);
  accFilters.value = { keyword: '', role: '' };
  accPage.value = 1;
  loadAccounts();
}

async function saveAiConfig() {
  if (aiSaving.value) return;
  // 校验必须放在置位 aiSaving **之前**。
  // 先置位再 return 会跳过下面的 finally，aiSaving 永远停在 true ——
  // 保存按钮就此永久变灰显示"保存中…"，用户只能刷新页面才能再点。
  // （这个写法是本次改动引入的，被浏览器测试抓了出来。）
  if (boundWarning.value) {
    showToast('分级边界必须严格递增，请先修正', 'warning');
    return;
  }
  // 加载失败时页面显示的是默认值。此时保存 = 用默认值覆盖数据库里的真实配置，
  // 而且没有任何撤销路径（覆盖前不会备份原值）。宁可拒绝保存。
  if (aiLoadError.value) {
    showToast('AI 配置尚未从服务端加载成功，已阻止保存以免覆盖真实配置。请先刷新页面。', 'error');
    return;
  }
  aiSaving.value = true;
  try {
    // 同步保存 AI 参数 + 全局模型选择（数组）
    const res = await saveSettings({ aiConfig: aiConfig.value, globalYoloModels: globalYoloModels.value });
    // 后端返回"实际被引擎接受的参数名"。原先前端丢弃了它，于是
    // "保存成功"与"真的生效"在界面上没有任何区别 —— 而这页以前恰好有几个
    // 控件是存得下、不生效的。现在把结果明确回显出来。
    appliedParams.value = res.data?.appliedAiParams || [];
    // 批量更新所有摄像头的 yolo_models 字段
    await setGlobalYoloModel(globalYoloModels.value);
    showToast(appliedParams.value.length
      ? `已保存并生效：${appliedParams.value.join('、')}`
      : '已保存（引擎未在运行，参数将在下次加载引擎时应用）', 'success');
    await loadCameras();
  } catch {
    showToast('保存失败', 'error');
  } finally {
    aiSaving.value = false;
  }
}

async function saveNotifyConfig() {
  try { await saveSettings({ notifyConfig: notifyConfig.value }); showToast('通知配置已保存', 'success'); }
  catch { showToast('保存失败', 'error'); }
}

function openAddCamera() {
  cameraForm.value = { name: '', roomNo: '', sourceType: 'rtsp', streamUrl: '', note: '' };
  cameraModal.value = { show: true, isEdit: false, editIndex: -1 };
}

function editCamera(cam) {
  const i = cameras.value.findIndex(c => (cam.id && c.id === cam.id) || c === cam);
  cameraForm.value = { ...cam, sourceType: cam.sourceType || 'rtsp', note: cam.note || '' };
  cameraModal.value = { show: true, isEdit: true, editIndex: i, id: cam.id };
}

async function deleteCamera(cam) {
  if (!confirm(`确认删除摄像头【${cam.name}】？`)) return;
  const i = cameras.value.findIndex(c => (cam.id && c.id === cam.id) || c === cam);
  if (i < 0) return;
  try {
    if (cam.id) { const res = await deleteCameraApi(cam.id); if (res.data.success) { cameras.value.splice(i, 1); showToast('删除成功', 'success'); } }
    else { cameras.value.splice(i, 1); }
  } catch { showToast('删除失败', 'error'); }
}

async function saveCamera() {
  if (!cameraForm.value.name?.trim() || !cameraForm.value.roomNo?.trim()) { showToast('名称和房间号为必填项', 'warning'); return; }
  if (!cameraForm.value.sourceType) { showToast('请选择视频源类型', 'warning'); return; }
  if (cameraForm.value.sourceType !== 'local' && !cameraForm.value.streamUrl?.trim()) { showToast('请填写视频地址', 'warning'); return; }
  try {
    const payload = { ...cameraForm.value, yoloModels: globalYoloModels.value };
    if (cameraModal.value.isEdit && cameraModal.value.id) {
      const res = await updateCamera(cameraModal.value.id, payload);
      if (res.data.success) { cameras.value[cameraModal.value.editIndex] = res.data.data; showToast('更新成功', 'success'); }
    } else {
      const res = await createCamera(payload);
      if (res.data.success) { cameras.value.push(res.data.data); showToast('添加成功', 'success'); }
    }
    cameraModal.value.show = false;
  } catch { showToast('操作失败', 'error'); }
}

async function updateRole(acc) {
  try {
    const res = await updateUserRole(acc.id, acc.role);
    if (res.data.success) showToast(`${acc.name || acc.username} 权限已更新`, 'success');
    else showToast(res.data.message || '更新失败', 'error');
  } catch { showToast('更新失败，请确认您有管理员权限', 'error'); }
}

function openAddUser() {
  userForm.value = { username: '', name: '', password: '', role: 'nurse', email: '', deptName: '' };
  userModal.value = { show: true, loading: false, error: '' };
}

async function submitAddUser() {
  userModal.value.error = '';
  if (!userForm.value.username.trim()) { userModal.value.error = '请输入账号'; return; }
  if (!userForm.value.name.trim()) { userModal.value.error = '请输入姓名'; return; }
  if (!userForm.value.password || userForm.value.password.length < 6) { userModal.value.error = '密码至少 6 位'; return; }
  userModal.value.loading = true;
  try {
    const res = await createUser(userForm.value);
    if (res.data.success) {
      showToast('账号创建成功', 'success');
      userModal.value.show = false;
      await loadAccounts();
    } else { userModal.value.error = res.data.message || '创建失败'; }
  } catch (e) { userModal.value.error = e.response?.data?.message || '创建失败'; }
  finally { userModal.value.loading = false; }
}

async function confirmDeleteUser(acc) {
  if (!confirm(`确认删除账号【${acc.username}】？此操作不可撤销。`)) return;
  try {
    const res = await deleteUser(acc.id);
    if (res.data.success) { showToast('账号已删除', 'success'); await loadAccounts(); }
    else showToast(res.data.message || '删除失败', 'error');
  } catch (e) { showToast(e.response?.data?.message || '删除失败', 'error'); }
}

// ── 告警通知渠道 ────────────────────────────────────────────────────────
const notifyTypes = ref([]);
const notifyLevels = ref([]);
const notifyChannels = ref([]);
const notifyLogs = ref([]);
const logStats = ref(null);
const logsLoading = ref(false);
const logFilters = ref({ status: '', channelType: '' });
const logFilterActive = computed(() =>
  Boolean(logFilters.value.status) || Boolean(logFilters.value.channelType));
const logPagination = ref({ page: 1, pageSize: 20, total: 0 });
const channelModal = ref({ show: false, isEdit: false, saving: false,
                           form: { id: null, type: 'wecom', name: '', minLevel: 'HIGH', config: {} } });

const LEVEL_LABEL = { LOW: '低危', MEDIUM: '中危', HIGH: '高危', URGENT: '紧急' };
function levelLabel(v) { return LEVEL_LABEL[v] || v || '—'; }
function typeLabel(t) { return (notifyTypes.value.find((x) => x.type === t) || {}).label || t; }
const STATUS_LABEL = { success: '成功', failed: '失败', skipped: '未发送' };
function statusLabel(v) { return STATUS_LABEL[v] || v; }
const REASON_LABEL = { new: '新告警', escalated: '升级', escalated_timeout: '超时升级',
                       confirmed: '已处置', test: '测试发送' };
function reasonLabel(v) { return REASON_LABEL[v] || v || ''; }

const currentTypeFields = computed(() =>
  (notifyTypes.value.find((x) => x.type === channelModal.value.form.type) || {}).fields || []);
const currentTypeHint = computed(() =>
  (notifyTypes.value.find((x) => x.type === channelModal.value.form.type) || {}).hint || '');

function channelTarget(c) {
  const cfg = c.config || {};
  if (cfg.webhook) return cfg.webhook;
  if (cfg.to) return cfg.to;
  const t = notifyTypes.value.find((x) => x.type === c.type);
  return t ? `未配置（${typeLabel(c.type)}）` : '—';
}

async function loadNotifyMeta() {
  try {
    const res = await getNotifyTypes();
    if (res.data.success) {
      notifyTypes.value = res.data.data || [];
      notifyLevels.value = res.data.levels || [];
    }
    setLoadError('channel', '');
  } catch (e) {
    // 渠道类型元数据拿不到，「新增渠道」的弹框会是空的下拉 —— 说出来，
    // 否则用户点开只看到一个没有选项的类型框，不知道是坏了还是本来如此。
    console.error('加载通知渠道类型失败', e);
    setLoadError('channel', `通知渠道类型加载失败：${failText(e, '未知错误')}`);
  }
}

async function loadNotifyChannels() {
  try {
    const res = await getNotifyChannels();
    if (res.data.success) notifyChannels.value = (res.data.data || []).map((c) => ({ ...c, _testing: false }));
    setLoadError('channel', '');
  } catch (e) {
    // 「一个渠道都没有」和「渠道列表读不出来」是两件完全不同的事：
    // 前者是配置状态，后者意味着告警可能根本没人在被叫醒。
    console.error('加载通知渠道失败', e);
    setLoadError('channel', `通知渠道加载失败：${failText(e, '未知错误')}`);
  }
}

async function loadNotifyLogs() {
  logsLoading.value = true;
  try {
    const res = await getNotifyLogs({ page: logPagination.value.page,
                                      pageSize: logPagination.value.pageSize,
                                      ...logFilters.value });
    if (res.data.success) {
      const d = res.data.data;
      notifyLogs.value = d.data || [];
      logPagination.value.total = d.total || 0;
      logStats.value = d.byStatus || null;
    }
    setLoadError('log', '');
  } catch (e) {
    console.error('加载投递记录失败', e);
    setLoadError('log', `投递记录加载失败：${failText(e, '未知错误')}`);
  } finally { logsLoading.value = false; }
}
function resetLogPage() { logPagination.value.page = 1; loadNotifyLogs(); }
function resetLogFilters() {
  logFilters.value = { status: '', channelType: '' };
  logPagination.value.page = 1;
  loadNotifyLogs();
}

function openChannelModal(c = null) {
  if (c) {
    channelModal.value = { show: true, isEdit: true, saving: false,
      form: { id: c.id, type: c.type, name: c.name, minLevel: c.minLevel || 'HIGH',
              // 后端把凭据脱敏成 ******；原样回传时后端会保留库里的真实值
              config: JSON.parse(JSON.stringify(c.config || {})) } };
  } else {
    const first = notifyTypes.value[0] || { type: 'wecom' };
    channelModal.value = { show: true, isEdit: false, saving: false,
      form: { id: null, type: first.type, name: '', minLevel: 'HIGH', config: {} } };
  }
}

async function submitChannel() {
  const f = channelModal.value.form;
  if (!f.name.trim()) { showToast('请填写渠道名称', 'warning'); return; }
  channelModal.value.saving = true;
  try {
    const payload = { type: f.type, name: f.name.trim(), minLevel: f.minLevel, config: f.config };
    const res = f.id ? await updateNotifyChannel(f.id, payload) : await createNotifyChannel(payload);
    if (res.data.success) {
      showToast(res.data.message || '已保存', 'success');
      channelModal.value.show = false;
      await loadNotifyChannels();
    } else {
      showToast(res.data.message || '保存失败', 'error');
    }
  } catch (e) {
    showToast(e.response?.data?.detail || '保存失败', 'error');
  } finally { channelModal.value.saving = false; }
}

async function toggleChannel(c) {
  try {
    const res = await updateNotifyChannel(c.id, { enabled: !c.enabled });
    if (res.data.success) { showToast(c.enabled ? '已停用' : '已启用', 'success'); await loadNotifyChannels(); }
  } catch { showToast('操作失败', 'error'); }
}

async function removeChannel(c) {
  if (!window.confirm(`删除通知渠道「${c.name}」？投递记录会保留。`)) return;
  try {
    const res = await deleteNotifyChannel(c.id);
    if (res.data.success) { showToast('已删除', 'success'); await loadNotifyChannels(); }
  } catch { showToast('删除失败', 'error'); }
}

/** 真发一条测试消息。**如实展示后端返回的结果**——包括失败原因。 */
async function testChannel(c) {
  c._testing = true;
  try {
    const res = await testNotifyChannel(c.id);
    // 注意用 res.data.success 判断：未配置/失败时后端返回 success=false，
    // 这里不能因为 HTTP 200 就报"成功"
    if (res.data.success) showToast(res.data.message || '已发送', 'success');
    else showToast(res.data.message || '发送失败', 'error');
    await loadNotifyLogs();
  } catch (e) {
    showToast(e.response?.data?.detail || '测试失败', 'error');
  } finally { c._testing = false; }
}

onMounted(() => {
  loadSettings();
  loadCameras();
  loadAccounts();
  // 通知元数据（渠道类型/等级）必须最先取：渠道弹框的字段清单由它驱动。
  // 使用 async IIFE 是为了按顺序加载，避免弹框先于元数据打开而字段为空。
  (async () => {
    await loadNotifyMeta();
    await loadNotifyChannels();
    await loadNotifyLogs();
  })();
});
</script>

<style scoped>
.page { padding: 24px; min-height: calc(100vh - var(--header-h)); }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 20px; }
h1 { font-size: 22px; font-weight: 800; color: var(--text-primary); }
.page-sub { font-size: 13px; color: var(--text-muted); margin-top: 3px; }
.tabs { display: flex; gap: 6px; margin-bottom: 22px; flex-wrap: wrap; }
.tab-btn { padding: 8px 18px; border-radius: 10px; border: 1px solid var(--tint-4); background: transparent; color: var(--text-tertiary); cursor: pointer; font-size: 13px; transition: all .2s; white-space: nowrap; }
.tab-btn.active { border-color: color-mix(in srgb, var(--primary) 50%, transparent); background: color-mix(in srgb, var(--primary) 10%, transparent); color: var(--primary-hover); }
/* ── AI 判定参数：决策链示意 + 分级条 ────────────────────────────────
   这一段的目的是让"这个参数作用在哪一步"一眼可见。原界面把四个边界点画成
   三个区间，既不符合引擎的真实逻辑，也让人不知道调了会怎样。 */
.chain-intro { font-size: 13px; color: var(--text-secondary); margin-bottom: 14px; line-height: 1.7; }
.chain-flow {
  display: flex; align-items: center; flex-wrap: wrap; gap: 6px;
  margin-top: 10px; padding: 12px 14px;
  background: var(--bg-surface-2, var(--tint-1));
  border: 1px solid var(--tint-3); border-radius: var(--radius-md);
}
.chain-node {
  padding: 4px 10px; border-radius: var(--radius-sm, 6px);
  font-size: 12px; background: var(--bg-surface);
  border: 1px solid var(--border-default); color: var(--text-secondary);
}
.chain-node.pose   { border-color: var(--level-normal); color: var(--level-normal); }
.chain-node.expr   { border-color: var(--level-medium); color: var(--level-medium); }
.chain-node.fuse   { border-color: var(--primary); color: var(--primary); font-weight: 600; }
.chain-node.alert  { border-color: var(--level-high); color: var(--level-high); }
.chain-arrow { font-size: 12px; color: var(--text-muted); display: inline-flex; align-items: center; gap: 4px; }
.chain-arrow em { font-style: normal; font-size: 11px; }

.group-title {
  display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap;
  font-size: 14px; font-weight: 700; color: var(--text-primary);
  margin: 0 0 10px; padding-bottom: 8px; border-bottom: 1px solid var(--tint-3);
}
.group-hint { font-size: 12px; font-weight: 400; color: var(--text-muted); }
.group-warn {
  margin-top: 10px; padding: 8px 12px; font-size: 12px; line-height: 1.6;
  color: var(--level-medium);
  background: var(--level-medium-soft);
  border: 1px solid var(--level-medium); border-radius: var(--radius-sm, 6px);
}

/* 分级条：每段宽度 == 该档的实际范围，拖动边界点时实时变化 */
.bound-strip {
  display: flex; height: 40px; border-radius: var(--radius-sm, 6px);
  overflow: hidden; margin-bottom: 8px; border: 1px solid var(--tint-3);
}
.bound-seg { display: flex; align-items: center; justify-content: center; transition: flex .2s; }
.bound-seg:nth-child(1) { background: var(--tint-1); }
.bound-seg:nth-child(2) { background: var(--level-normal-soft); }
.bound-seg:nth-child(3) { background: var(--level-medium-soft); }
.bound-seg:nth-child(4) { background: var(--level-high-soft); }
.bound-seg:nth-child(5) { background: var(--level-high); }
.bs-name { font-size: 11px; font-weight: 700; color: var(--text-secondary); }
.bound-seg:nth-child(5) .bs-name { color: var(--text-on-color); }
.bound-note { font-size: 12px; color: var(--text-muted); margin-bottom: 14px; line-height: 1.6; }

.save-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.save-applied {
  font-size: 12px; color: var(--level-normal);
  padding: 4px 10px; border-radius: var(--radius-full, 999px);
  background: var(--level-normal-soft);
}

/* ── 告警通知 ────────────────────────────────────────────────────────
   渠道与投递记录都用"表头 + 行"的紧凑布局，不用卡片：这张表要能被**扫读**，
   排查"为什么没收到"时一屏能看十几行比看几张卡片有用得多。 */
.notify-intro {
  font-size: 13px; line-height: 1.8; color: var(--text-secondary);
  margin-bottom: 14px; padding: 12px 14px;
  background: var(--bg-surface-2, var(--tint-1));
  border: 1px solid var(--tint-3); border-radius: var(--radius-md);
}
.notify-intro-dim { color: var(--text-muted); font-size: 12px; }

.channel-list, .log-list { border: 1px solid var(--tint-3); border-radius: var(--radius-md); overflow: hidden; }
.channel-header, .channel-row { display: grid; grid-template-columns: 1.6fr 1fr 0.8fr 1.6fr 2fr; gap: 10px; align-items: center; }
.log-header, .log-row { display: grid; grid-template-columns: 1.2fr 1.2fr 1.4fr 0.8fr 2.4fr 0.7fr; gap: 10px; align-items: center; }
.channel-header, .log-header {
  padding: 10px 14px; font-size: 12px; font-weight: 600;
  color: var(--text-tertiary); background: var(--bg-inset);
  border-bottom: 1px solid var(--tint-3);
}
.channel-header span, .log-header span { text-align: center; }
.channel-row, .log-row {
  padding: 10px 14px; font-size: 13px; color: var(--text-secondary);
  border-bottom: 1px solid var(--tint-2);
}
.channel-row:last-child, .log-row:last-child { border-bottom: none; }
.channel-row:hover, .log-row:hover { background: var(--tint-1); }
.channel-row > span, .log-row > span { text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ch-name { font-weight: 600; color: var(--text-primary); }
.ch-off { margin-left: 6px; font-size: 11px; font-weight: 400; color: var(--text-muted); }
.ch-type { color: var(--text-tertiary); }
.ch-target, .log-target { font-size: 12px; color: var(--text-muted); }
.log-time { font-size: 12px; color: var(--text-tertiary); font-variant-numeric: tabular-nums; }
.log-err { font-size: 12px; text-align: left !important; }
.log-ms { font-size: 12px; color: var(--text-muted); font-variant-numeric: tabular-nums; }

.log-status { padding: 2px 8px; border-radius: var(--radius-full, 999px); font-size: 11px; font-weight: 600; }
.ls-success { background: var(--success-soft); color: var(--success-text); }
.ls-failed { background: var(--danger-soft); color: var(--danger-text); }
.ls-skipped { background: var(--warning-soft); color: var(--warning-text); }

.lvl-low { background: var(--success-soft); color: var(--success-text); border-color: var(--tint-3); }
.lvl-medium { background: var(--warning-soft); color: var(--warning-text); border-color: var(--tint-3); }
.lvl-high { background: var(--danger-soft); color: var(--danger-text); border-color: var(--tint-3); }
.lvl-urgent { background: var(--level-urgent-soft); color: var(--level-urgent); border-color: var(--tint-3); }
.btn-sm {
  padding: 4px 10px; font-size: 12px; cursor: pointer;
  border: 1px solid var(--border-default); border-radius: 6px;
  background: var(--bg-surface); color: var(--text-secondary);
}
.btn-sm:hover:not(:disabled) { border-color: var(--primary); color: var(--primary); }
.btn-sm:disabled { opacity: .5; cursor: not-allowed; }
.btn-sm.danger:hover { border-color: var(--danger); color: var(--danger); }
.field-hint { margin-top: 4px; font-size: 12px; color: var(--text-muted); line-height: 1.6; }

@media (max-width: 900px) {
  .channel-header, .log-header { display: none; }
  .channel-row, .log-row { grid-template-columns: 1fr; gap: 4px; text-align: left; }
  .channel-row > span, .log-row > span { text-align: left; }
}

.settings-section { background: var(--tint-1); border: 1px solid var(--tint-3); border-radius: 16px; padding: 22px; }
.section-title-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
.section-title { font-size: 14px; font-weight: 700; color: var(--text-tertiary); margin-bottom: 18px; }
.section-title-row .section-title { margin-bottom: 0; }
.btn-add-user { padding: 6px 14px; border-radius: 8px; border: 1px solid color-mix(in srgb, var(--primary) 30%, transparent); background: color-mix(in srgb, var(--primary) 8%, transparent); color: var(--primary-hover); cursor: pointer; font-size: 12px; font-weight: 600; white-space: nowrap; }
.btn-add-user:hover { background: color-mix(in srgb, var(--primary) 15%, transparent); }
/* 工具栏右侧操作与条件控件同高（契约里 .toolbar-search/.toolbar-field 统一 34px） */
.toolbar-actions .btn-add-user { height: 34px; padding: 0 14px; }
.setting-group { display: flex; flex-direction: column; gap: 1px; }
.setting-item { display: flex; align-items: center; justify-content: space-between; padding: 16px 0; border-bottom: 1px solid var(--tint-2); gap: 16px; }
.setting-item.vertical { flex-direction: column; align-items: flex-start; gap: 8px; }
.setting-item:last-child { border-bottom: none; }
.setting-info { flex: 1; }
.setting-name { font-size: 14px; font-weight: 600; color: var(--text-secondary); margin-bottom: 3px; }
.setting-desc { font-size: 12px; color: var(--text-muted); }
.slider-wrap { display: flex; align-items: center; gap: 10px; }
.slider { width: 160px; accent-color: var(--primary); cursor: pointer; }
.slider-val { font-size: 14px; font-weight: 700; color: var(--primary-hover); width: 40px; text-align: right; }
.range-inputs { display: flex; align-items: center; gap: 6px; color: var(--text-tertiary); font-size: 13px; }
.num-input { width: 64px; background: var(--tint-3); border: 1px solid var(--tint-4); border-radius: 8px; padding: 6px 10px; color: var(--text-secondary); font-size: 13px; text-align: center; outline: none; }
.toggle-switch { position: relative; width: 44px; height: 24px; cursor: pointer; flex-shrink: 0; }
.toggle-switch input { opacity: 0; width: 0; height: 0; }
.toggle-slider { position: absolute; inset: 0; background: var(--tint-4); border-radius: 24px; transition: .3s; }
.toggle-slider::before { content: ''; position: absolute; width: 18px; height: 18px; left: 3px; bottom: 3px; background: var(--tint-4); border-radius: 50%; transition: .3s; }
.toggle-switch input:checked + .toggle-slider { background: color-mix(in srgb, var(--primary) 40%, transparent); }
.toggle-switch input:checked + .toggle-slider::before { transform: translateX(20px); background: var(--primary); }
.notify-input { width: 100%; background: var(--tint-3); border: 1px solid var(--tint-4); border-radius: 8px; padding: 9px 12px; color: var(--text-secondary); font-size: 13px; resize: none; outline: none; font-family: inherit; box-sizing: border-box; }
.btn-save { margin-top: 20px; padding: 9px 24px; border-radius: 10px; border: none; background: var(--primary); color: var(--text-on-color); cursor: pointer; font-weight: 600; font-size: 13px; min-height: 44px; transition: opacity .2s; }
.btn-save:disabled { opacity: .5; cursor: not-allowed; }
.btn-add { margin-top: 20px; padding: 9px 24px; border-radius: 10px; background: var(--tint-2); border: 1px solid var(--tint-4); color: var(--text-tertiary); cursor: pointer; font-weight: 600; font-size: 13px; min-height: 44px; }

/* 全局模型配置区 */
.model-section { margin-top: 24px; padding-top: 20px; border-top: 1px solid var(--tint-3); }
.model-section-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 14px; gap: 12px; }
.model-section-title { font-size: 14px; font-weight: 700; color: var(--text-secondary); margin-bottom: 3px; }
.model-section-desc { font-size: 12px; color: var(--text-muted); }
.model-cam-count { flex-shrink: 0; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; background: color-mix(in srgb, var(--primary) 10%, transparent); border: 1px solid color-mix(in srgb, var(--primary) 20%, transparent); color: var(--primary-hover); white-space: nowrap; margin-top: 2px; }
.yolo-model-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.yolo-model-card { display: flex; flex-direction: column; align-items: center; gap: 5px; padding: 16px 10px; border-radius: var(--radius-md); border: 1px solid var(--tint-3); background: var(--tint-1); cursor: pointer; transition: all .18s; }
.yolo-model-card:hover { border-color: color-mix(in srgb, var(--primary) 30%, transparent); background: color-mix(in srgb, var(--primary) 6%, transparent); transform: translateY(-1px); }
.yolo-model-card.active { border-color: color-mix(in srgb, var(--primary) 60%, transparent); background: color-mix(in srgb, var(--primary) 12%, transparent); box-shadow: 0 0 0 1px color-mix(in srgb, var(--primary) 30%, transparent); position: relative; }
.yolo-model-card.disabled { opacity: 0.4; cursor: not-allowed; }
.yolo-model-card.disabled:hover { transform: none; border-color: var(--tint-3); background: var(--tint-1); }
.yolo-card-icon { font-size: 26px; line-height: 1; }
.yolo-card-label { font-size: 13px; font-weight: 700; color: var(--text-secondary); }
.yolo-card-desc { font-size: 11px; color: var(--text-muted); text-align: center; line-height: 1.4; }
.yolo-card-check { 
  position: absolute; top: 8px; right: 8px; 
  width: 20px; height: 20px; border-radius: 50%; 
  background: var(--primary); color: var(--text-on-color); font-size: 12px; font-weight: 700; 
  display: flex; align-items: center; justify-content: center;
}
.yolo-model-card.active .yolo-card-label { color: var(--primary-hover); }
.model-effect-bar { display: flex; align-items: center; gap: 8px; margin-top: 12px; padding: 10px 14px; background: var(--tint-1); border: 1px solid var(--tint-3); border-radius: 9px; }
.model-effect-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.model-effect-dot.pose { background: var(--primary); box-shadow: 0 0 6px color-mix(in srgb, var(--primary) 60%, transparent); }
.model-effect-dot.face { background: var(--violet); box-shadow: 0 0 6px color-mix(in srgb, var(--violet) 60%, transparent); }
.model-effect-dot.none { background: var(--text-muted); }
.model-effect-text { font-size: 12px; color: var(--text-tertiary); flex: 1; }
.model-effect-dots { display: flex; gap: 6px; }
.model-limit-hint { color: var(--warning); margin-left: 6px; }
.model-effect-text strong { color: var(--text-secondary); }

/* 摄像头模型提示 */
.model-tip-box { display: flex; gap: 12px; align-items: flex-start; padding: 12px 14px; background: color-mix(in srgb, var(--primary) 4%, transparent); border: 1px solid color-mix(in srgb, var(--primary) 15%, transparent); border-radius: 10px; }
.model-tip-icon { font-size: 20px; flex-shrink: 0; margin-top: 1px; }
.model-tip-title { font-size: 13px; font-weight: 600; color: var(--primary-hover); margin-bottom: 3px; }
.model-tip-body { font-size: 12px; color: var(--text-muted); line-height: 1.6; }
.model-tip-body strong { color: var(--primary-hover); }

/* 摄像头列表 */
.camera-list { display: flex; flex-direction: column; gap: 8px; }
.camera-row { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: var(--tint-1); border-radius: 10px; border: 1px solid var(--tint-3); }
.cam-status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.cam-status-dot.online { background: var(--success); box-shadow: 0 0 6px var(--success)80; }
.cam-status-dot.offline { background: var(--danger); }
.cam-type-badge { font-size: 18px; flex-shrink: 0; }
.cam-info { flex: 1; min-width: 0; }
.cam-name { font-size: 14px; font-weight: 600; color: var(--text-secondary); }
.cam-room { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
.cam-url { font-size: 11px; color: var(--text-muted); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cam-actions { display: flex; gap: 8px; flex-shrink: 0; }
.btn-sm { padding: 5px 12px; border-radius: 6px; border: 1px solid var(--tint-4); background: transparent; color: var(--text-tertiary); cursor: pointer; font-size: 12px; min-height: 36px; }
.btn-sm.danger { border-color: color-mix(in srgb, var(--danger) 30%, transparent); color: var(--danger-text); }
.empty-cam { padding: 24px; text-align: center; color: var(--text-muted); font-size: 13px; }

/* 账号管理 */
.account-list { display: flex; flex-direction: column; gap: 1px; }
.account-header { display: grid; grid-template-columns: 2fr 2fr 2.5fr 2fr 1fr; gap: 10px; padding: 10px 14px; font-size: 12px; font-weight: 600; color: var(--text-muted); }
.account-row { display: grid; grid-template-columns: 2fr 2fr 2.5fr 2fr 1fr; gap: 10px; align-items: center; padding: 12px 14px; background: var(--tint-1); border-radius: 8px; border: 1px solid var(--tint-2); margin-bottom: 6px; }
.acc-username { font-size: 13px; color: var(--primary-hover); font-weight: 600; }
.acc-name { font-size: 13px; color: var(--text-tertiary); }
.acc-dept { font-size: 12px; color: var(--text-muted); overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.acc-ops { display: flex; gap: 6px; justify-content: flex-end; }
.role-select { background: var(--tint-3); border: 1px solid var(--tint-4); border-radius: 7px; padding: 5px 10px; color: var(--text-secondary); font-size: 12px; outline: none; cursor: pointer; padding-right: 26px; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%2364748b'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 8px center; }
.role-select.full { flex: 1; padding: 8px 12px; font-size: 13px; padding-right: 32px; background-position: right 10px center; }
.btn-del-user { padding: 4px 10px; border-radius: 6px; border: 1px solid color-mix(in srgb, var(--danger) 30%, transparent); background: transparent; color: var(--danger-text); cursor: pointer; font-size: 11px; white-space: nowrap; }
.btn-del-user:hover { background: color-mix(in srgb, var(--danger) 8%, transparent); }
.account-mobile { display: none; }

/* 弹框 */
.modal-mask { position: fixed; inset: 0; background: var(--bg-overlay); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-box { background: var(--bg-surface-2); border: 1px solid var(--tint-4); border-radius: 16px; width: 420px; max-width: 95vw; max-height: 90vh; overflow-y: auto; }
.modal-box.wide { width: 520px; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid var(--tint-3); position: sticky; top: 0; background: var(--bg-surface-2); z-index: 1; }
.modal-header h3 { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.close-btn { background: none; border: none; color: var(--text-tertiary); font-size: 22px; cursor: pointer; }
.modal-body { padding: 20px; display: flex; flex-direction: column; gap: 16px; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.field-group { display: flex; flex-direction: column; gap: 6px; }
.field-group label { font-size: 12px; font-weight: 600; color: var(--text-tertiary); }
.req { color: var(--danger); }
.field-group input, .field-group select { background: var(--tint-3); border: 1px solid var(--tint-4); border-radius: 8px; padding: 9px 12px; color: var(--text-secondary); font-size: 13px; outline: none; width: 100%; box-sizing: border-box; }
.field-group input:focus, .field-group select:focus { border-color: color-mix(in srgb, var(--primary) 50%, transparent); }
.field-group select { padding-right: 32px; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' viewBox='0 0 10 6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%2364748b'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 12px center; }
.src-type-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.src-type-card { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 12px 8px; border-radius: 10px; border: 1px solid var(--tint-4); background: var(--tint-2); cursor: pointer; transition: all .2s; }
.src-type-card.active { border-color: color-mix(in srgb, var(--primary) 60%, transparent); background: color-mix(in srgb, var(--primary) 12%, transparent); }
.src-card-icon { font-size: 22px; }
.src-card-label { font-size: 12px; font-weight: 700; color: var(--text-secondary); }
.src-card-desc { font-size: 10px; color: var(--text-muted); text-align: center; }
.src-config-block { background: var(--tint-1); border: 1px solid var(--tint-3); border-radius: 10px; padding: 14px; }
.local-block { border-color: color-mix(in srgb, var(--success) 15%, transparent); background: color-mix(in srgb, var(--success) 3%, transparent); }
.local-tip-box { display: flex; gap: 12px; align-items: flex-start; }
.tip-icon { font-size: 28px; flex-shrink: 0; }
.tip-title { font-size: 13px; font-weight: 700; color: var(--text-secondary); margin-bottom: 4px; }
.tip-body { font-size: 12px; color: var(--text-tertiary); line-height: 1.6; }
.form-error { padding: 8px 12px; background: color-mix(in srgb, var(--danger) 8%, transparent); border: 1px solid color-mix(in srgb, var(--danger) 20%, transparent); border-radius: 8px; color: var(--danger-text); font-size: 12px; }
.modal-footer { display: flex; justify-content: flex-end; gap: 10px; padding: 16px 20px; border-top: 1px solid var(--tint-3); position: sticky; bottom: 0; background: var(--bg-surface-2); }
.btn-cancel { padding: 8px 20px; border-radius: 8px; border: 1px solid var(--tint-4); background: transparent; color: var(--text-tertiary); cursor: pointer; }
.btn-primary { padding: 8px 20px; border-radius: 8px; border: none; background: var(--primary); color: var(--text-on-color); cursor: pointer; font-weight: 600; }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }

@media (max-width: 768px) {
  .page { padding: 14px; padding-bottom: 80px; }
  h1 { font-size: 18px; }
  .tabs { gap: 6px; overflow-x: auto; flex-wrap: nowrap; padding-bottom: 4px; }
  .tab-btn { padding: 8px 14px; font-size: 12px; flex-shrink: 0; }
  .settings-section { padding: 16px; }
  .setting-item { flex-direction: column; align-items: flex-start; gap: 10px; }
  .slider-wrap { width: 100%; }
  .slider { flex: 1; }
  .range-inputs { flex-wrap: wrap; gap: 8px; }
  .num-input { width: 56px; min-height: 44px; }
  .yolo-model-grid { grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .camera-row { flex-wrap: wrap; }
  .cam-actions { width: 100%; margin-top: 6px; }
  .btn-sm { flex: 1; min-height: 44px; text-align: center; }
  .account-list, .account-header { display: none; }
  .account-mobile { display: block; margin-top: 8px; }
  .acc-card { background: var(--tint-1); border: 1px solid var(--tint-3); border-radius: 12px; padding: 14px; margin-bottom: 10px; }
  .acc-card-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
  .acc-card-info { font-size: 12px; color: var(--text-tertiary); margin-bottom: 8px; }
  .acc-card-actions { display: flex; gap: 8px; align-items: center; }
  .acc-role-badge { padding: 2px 8px; border-radius: 5px; font-size: 11px; font-weight: 600; }
  .acc-role-badge.admin { background: color-mix(in srgb, var(--violet) 12%, transparent); color: var(--violet-text); }
  .acc-role-badge.nurse { background: color-mix(in srgb, var(--primary) 10%, transparent); color: var(--primary-hover); }
  .modal-box { width: 100% !important; max-width: 100% !important; border-radius: 20px 20px 0 0; max-height: 92vh; }
  .modal-box.wide { width: 100% !important; }
  .modal-mask { align-items: flex-end; }
  .form-row { grid-template-columns: 1fr; }
  .src-type-grid { grid-template-columns: repeat(3, 1fr); gap: 6px; }
  .src-card-desc { display: none; }
  .model-section-header { flex-direction: column; gap: 6px; }
}
</style>
