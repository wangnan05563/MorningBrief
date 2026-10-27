<template>
  <!-- T02613：卡片本体抽到 components/EmergencyStopCard.vue，由本页（移动端 /m/manage/alert）
       与 PC 的「系统维护」页共用；这里只保留移动端路由入口。 -->
  <EmergencyStopCard />
</template>

<script setup>
import EmergencyStopCard from '../../components/EmergencyStopCard.vue'
</script>
