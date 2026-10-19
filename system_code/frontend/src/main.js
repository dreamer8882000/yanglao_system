import { createApp } from 'vue';
import App from './App.vue';
import router from './router/index.js';
import { applyTheme, currentTheme } from './utils/theme.js';
import './assets/styles/tokens.css';
import './assets/styles/global-enhancements.css';
import './assets/styles/design-refine.css';
// 全局布局契约：根容器/页头/面板/栅格/表格的唯一真相来源。
// 放在最后引入，确保它覆盖各页面遗留的重复定义。
import './assets/styles/layout.css';

applyTheme(currentTheme());   // 亮色为默认，可在侧边栏切换

const app = createApp(App);

app.config.errorHandler = err => {
  window.dispatchEvent(
    new ErrorEvent('error', {
      error: err,
      message: err?.message || String(err),
      filename: location.href,
    })
  );
};

app.use(router);
app.mount('#app');
