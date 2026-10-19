import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';
import tracker from 'vite-plugin-tracker';
import observe from 'vite-plugin-observe';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  
  return {
    base: env.VITE_BASE_PATH || '/',
    plugins: [
      tracker({ baseUrl: env.VITE_API_BASE_URL || '' }),
      vue(),
      observe({
        serverPrefix: env.VITE_BASE_PATH || '/'
      })
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },
    server: {
      host: env.HOST || '0.0.0.0',
      port: parseInt(env.PORT) || 8070,
      allowedHosts: (env.VITE_ALLOWED_HOSTS || 'localhost,127.0.0.1').split(','),
      proxy: {
        '/api': {
          target: env.VITE_API_BASE_URL || 'http://localhost:8090',
          changeOrigin: true,
          ws: true,
          timeout: 0,
          proxyTimeout: 0
        }
      }
    }
  };
});
