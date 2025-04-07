


<script setup>
import VehicleList from './components/VehicleList.vue';
</script>

<template>
  <!-- 仅保留车辆列表组件 -->
  <div class="app-container">
    <VehicleList />
  </div>
</template>

<style>
/* 基础全局样式 */
.app-container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 2rem;
}

/* 响应式布局 */
@media (max-width: 768px) {
  .app-container {
    padding: 1rem;
  }
}
</style>