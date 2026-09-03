<script setup lang="ts">
import { theme } from 'ant-design-vue'

const themeConfig = {
  algorithm: theme.defaultAlgorithm,
  token: {
    colorPrimary: '#0c66e4',
    colorInfo: '#0c66e4',
    colorSuccess: '#216e4e',
    colorWarning: '#7f5f01',
    colorError: '#ae2e24',
    colorText: '#172b4d',
    colorTextSecondary: '#44546f',
    colorBorder: '#dfe1e6',
    colorBgLayout: '#f7f8fa',
    borderRadius: 6,
    controlHeight: 40,
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
  },
}
</script>

<template>
  <a-config-provider :theme="themeConfig">
    <router-view />
  </a-config-provider>
</template>
