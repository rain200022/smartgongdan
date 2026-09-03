import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import 'ant-design-vue/dist/reset.css'
import './styles/tokens.css'
import './styles/base.css'

createApp(App).use(router).mount('#app')
