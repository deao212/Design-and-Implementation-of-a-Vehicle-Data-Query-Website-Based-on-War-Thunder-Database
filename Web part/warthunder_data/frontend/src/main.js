// main.js
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import vuetify from '@/plugins/vuetify' // 从独立插件文件导入
const app = createApp(App)
app.use(vuetify) // 挂载 Vuetify 实例
app.use(router)
app.mount('#app')