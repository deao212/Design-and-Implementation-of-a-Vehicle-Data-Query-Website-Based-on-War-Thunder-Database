
import { createRouter, createWebHistory } from 'vue-router'
import VehicleList from '../components/VehicleList.vue' // 根据实际路径调整

const routes = [
  {
    path: '/',
    name: 'Home',
    component: VehicleList // 或你的主组件
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router