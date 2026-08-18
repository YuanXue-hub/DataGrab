<template>
  <div class="home" @mousemove="onMouseMove">
    <!-- 3D 透视舞台 -->
    <div class="stage" ref="stageRef">
      <!-- 粒子层 -->
      <div class="particles">
        <span
          v-for="n in 60"
          :key="n"
          class="particle"
          :style="particleStyle(n)"
        />
      </div>

      <!-- 网格地板 -->
      <div class="grid-floor">
        <div class="grid-lines" />
      </div>

      <!-- 中心 3D 节点 -->
      <div class="node-scene" :style="{ transform: nodeTransform }">
        <!-- 核心立方体 -->
        <div class="cube">
          <div class="cube-face cube-front" />
          <div class="cube-face cube-back" />
          <div class="cube-face cube-left" />
          <div class="cube-face cube-right" />
          <div class="cube-face cube-top" />
          <div class="cube-face cube-bottom" />
        </div>
        <!-- 轨道环 -->
        <div class="orbit orbit-1">
          <div class="orbit-node" />
        </div>
        <div class="orbit orbit-2">
          <div class="orbit-node" />
        </div>
        <div class="orbit orbit-3">
          <div class="orbit-node" />
        </div>
      </div>

      <!-- 扫描线 -->
      <div class="scanline" />

      <!-- 内容层 -->
      <div class="content">
        <div class="logo-badge">
          <img src="/datagrab-logo.jpg" alt="DataGrab" class="logo-img" />
          <span class="logo-pulse" />
        </div>
        <h1 class="title">
          <span class="title-line">DataGrab</span>
          <span class="title-subtitle">数据采集与情报分析平台</span>
        </h1>
        <p class="tagline">
          多源数据抓取 · 智能选择器配置 · 全格式导出
        </p>
        <div class="features">
          <div class="feature" v-for="f in features" :key="f.label">
            <span class="feature-icon" :style="{ color: f.color }">{{ f.icon }}</span>
            <span class="feature-label">{{ f.label }}</span>
          </div>
        </div>
        <button class="enter-btn" @click="enterSystem">
          <span class="btn-text">进入系统</span>
          <span class="btn-arrow">→</span>
          <span class="btn-glow" />
        </button>
        <div class="status-bar">
          <span class="status-item">
            <span class="status-dot" /> System Online
          </span>
          <span class="status-item">v1.0.0</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const stageRef = ref<HTMLElement>()
const mouseX = ref(0)
const mouseY = ref(0)

const features = [
  { icon: '◈', label: '18+ 数据源', color: '#00f0ff' },
  { icon: '⬡', label: '智能选择器', color: '#3b82f6' },
  { icon: '◆', label: 'JSON / CSV / DOCX', color: '#00f0ff' },
  { icon: '◉', label: '实时监控', color: '#3b82f6' },
]

const nodeTransform = ref('')

function onMouseMove(e: MouseEvent) {
  const cx = window.innerWidth / 2
  const cy = window.innerHeight / 2
  const dx = (e.clientX - cx) / cx
  const dy = (e.clientY - cy) / cy
  mouseX.value = dx
  mouseY.value = dy
  nodeTransform.value = `rotateY(${dx * 12}deg) rotateX(${-dy * 12}deg)`
}

function particleStyle(n: number) {
  const seed = n * 137.5
  const left = (Math.sin(seed) * 0.5 + 0.5) * 100
  const top = (Math.cos(seed * 1.3) * 0.5 + 0.5) * 100
  const delay = (n * 0.3) % 8
  const duration = 8 + (n % 6)
  const size = 1 + (n % 4)
  return {
    left: `${left}%`,
    top: `${top}%`,
    width: `${size}px`,
    height: `${size}px`,
    animationDelay: `${delay}s`,
    animationDuration: `${duration}s`,
  }
}

function enterSystem() {
  router.push('/app/sources')
}

let rafId = 0
onMounted(() => {
  // 入场动画
  document.body.style.overflow = 'hidden'
  rafId = requestAnimationFrame(() => {
    stageRef.value?.classList.add('loaded')
  })
})

onUnmounted(() => {
  document.body.style.overflow = ''
  cancelAnimationFrame(rafId)
})
</script>

<style scoped>
.home {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: #050810;
  position: relative;
}

/* ===== 舞台 ===== */
.stage {
  width: 100%;
  height: 100%;
  perspective: 1200px;
  perspective-origin: 50% 45%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  background:
    radial-gradient(ellipse 60% 40% at 50% 30%, rgba(0, 240, 255, 0.08), transparent),
    radial-gradient(ellipse 50% 35% at 70% 70%, rgba(59, 130, 246, 0.06), transparent),
    radial-gradient(ellipse 40% 30% at 30% 80%, rgba(0, 240, 255, 0.04), transparent),
    #050810;
}

/* ===== 粒子层 ===== */
.particles {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 1;
}
.particle {
  position: absolute;
  border-radius: 50%;
  background: var(--dg-cyan, #00f0ff);
  opacity: 0;
  animation: floatParticle linear infinite;
}
@keyframes floatParticle {
  0% { opacity: 0; transform: translateY(20px) scale(0.5); }
  10% { opacity: 0.6; }
  50% { opacity: 0.8; }
  90% { opacity: 0.4; }
  100% { opacity: 0; transform: translateY(-60px) scale(1.2); }
}

/* ===== 网格地板 ===== */
.grid-floor {
  position: absolute;
  bottom: 0;
  left: 50%;
  width: 200%;
  height: 45%;
  transform: translateX(-50%) rotateX(70deg);
  transform-origin: bottom center;
  z-index: 1;
  overflow: hidden;
  mask-image: linear-gradient(to top, rgba(0,0,0,0.5), transparent);
  -webkit-mask-image: linear-gradient(to top, rgba(0,0,0,0.5), transparent);
}
.grid-lines {
  width: 100%;
  height: 100%;
  background-image:
    linear-gradient(0deg, rgba(0, 240, 255, 0.12) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 240, 255, 0.08) 1px, transparent 1px);
  background-size: 60px 60px;
  animation: gridScroll 4s linear infinite;
}
@keyframes gridScroll {
  0% { background-position: 0 0; }
  100% { background-position: 0 60px; }
}

/* ===== 3D 节点场景 ===== */
.node-scene {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 0;
  height: 0;
  transform-style: preserve-3d;
  transition: transform 80ms ease-out;
  z-index: 2;
}

/* 立方体 */
.cube {
  position: absolute;
  transform-style: preserve-3d;
  animation: cubeRotate 20s linear infinite;
}
.cube-face {
  position: absolute;
  width: 120px;
  height: 120px;
  left: -60px;
  top: -60px;
  border: 1px solid rgba(0, 240, 255, 0.25);
  background: rgba(0, 240, 255, 0.03);
  backdrop-filter: blur(4px);
  box-shadow: inset 0 0 30px rgba(0, 240, 255, 0.08);
}
.cube-front  { transform: translateZ(60px); }
.cube-back   { transform: rotateY(180deg) translateZ(60px); }
.cube-left   { transform: rotateY(-90deg) translateZ(60px); }
.cube-right  { transform: rotateY(90deg) translateZ(60px); }
.cube-top    { transform: rotateX(90deg) translateZ(60px); }
.cube-bottom { transform: rotateX(-90deg) translateZ(60px); }

@keyframes cubeRotate {
  0%   { transform: rotateX(0deg) rotateY(0deg); }
  100% { transform: rotateX(360deg) rotateY(360deg); }
}

/* 轨道环 */
.orbit {
  position: absolute;
  left: 0;
  top: 0;
  border: 1px solid rgba(0, 240, 255, 0.12);
  border-radius: 50%;
  transform-style: preserve-3d;
}
.orbit-1 {
  width: 200px;
  height: 200px;
  left: -100px;
  top: -100px;
  animation: orbitSpin1 12s linear infinite;
}
.orbit-2 {
  width: 280px;
  height: 280px;
  left: -140px;
  top: -140px;
  border-color: rgba(59, 130, 246, 0.1);
  animation: orbitSpin2 18s linear infinite reverse;
}
.orbit-3 {
  width: 360px;
  height: 360px;
  left: -180px;
  top: -180px;
  border-color: rgba(0, 240, 255, 0.06);
  animation: orbitSpin1 24s linear infinite;
}
@keyframes orbitSpin1 {
  0%   { transform: rotateX(75deg) rotateZ(0deg); }
  100% { transform: rotateX(75deg) rotateZ(360deg); }
}
@keyframes orbitSpin2 {
  0%   { transform: rotateX(65deg) rotateY(10deg) rotateZ(0deg); }
  100% { transform: rotateX(65deg) rotateY(10deg) rotateZ(360deg); }
}

.orbit-node {
  position: absolute;
  top: -4px;
  left: 50%;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--dg-cyan, #00f0ff);
  box-shadow: 0 0 12px rgba(0, 240, 255, 0.8), 0 0 24px rgba(0, 240, 255, 0.4);
}
.orbit-2 .orbit-node {
  background: #3b82f6;
  box-shadow: 0 0 12px rgba(59, 130, 246, 0.8);
}
.orbit-3 .orbit-node {
  width: 5px;
  height: 5px;
  opacity: 0.5;
}

/* ===== 扫描线 ===== */
.scanline {
  position: absolute;
  left: 0;
  width: 100%;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(0, 240, 255, 0.5), transparent);
  z-index: 3;
  pointer-events: none;
  animation: scanMove 6s ease-in-out infinite;
}
@keyframes scanMove {
  0%   { top: 0%; opacity: 0; }
  10%  { opacity: 1; }
  90%  { opacity: 1; }
  100% { top: 100%; opacity: 0; }
}

/* ===== 内容层 ===== */
.content {
  position: relative;
  z-index: 10;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  text-align: center;
  padding: 40px;
  opacity: 0;
  transform: translateY(30px);
  animation: contentFadeIn 1.2s ease 0.5s forwards;
}
@keyframes contentFadeIn {
  to { opacity: 1; transform: translateY(0); }
}

.logo-badge {
  position: relative;
  width: 80px;
  height: 80px;
  margin-bottom: 8px;
}
.logo-img {
  width: 80px;
  height: 80px;
  border-radius: 16px;
  object-fit: cover;
  box-shadow:
    0 0 30px rgba(0, 240, 255, 0.3),
    0 0 60px rgba(0, 240, 255, 0.15);
  animation: logoFloat 4s ease-in-out infinite;
}
@keyframes logoFloat {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}
.logo-pulse {
  position: absolute;
  inset: -4px;
  border-radius: 18px;
  border: 1px solid rgba(0, 240, 255, 0.3);
  animation: logoPulse 2s ease-out infinite;
}
@keyframes logoPulse {
  0% { transform: scale(1); opacity: 0.8; }
  100% { transform: scale(1.3); opacity: 0; }
}

.title {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0;
}
.title-line {
  font-family: 'Outfit', sans-serif;
  font-size: 52px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #f1f5f9;
  text-shadow:
    0 0 20px rgba(0, 240, 255, 0.3),
    0 0 40px rgba(0, 240, 255, 0.15);
  background: linear-gradient(135deg, #f1f5f9 0%, #00f0ff 50%, #3b82f6 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.title-subtitle {
  font-family: 'Outfit', sans-serif;
  font-size: 16px;
  font-weight: 500;
  color: #94a3b8;
  letter-spacing: 0.04em;
}

.tagline {
  font-size: 14px;
  color: #64748b;
  margin: 0;
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: 0.02em;
}

.features {
  display: flex;
  gap: 24px;
  margin-top: 12px;
  flex-wrap: wrap;
  justify-content: center;
}
.feature {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 20px;
  background: rgba(17, 24, 39, 0.6);
  backdrop-filter: blur(8px);
}
.feature-icon {
  font-size: 14px;
}
.feature-label {
  font-size: 13px;
  color: #94a3b8;
  font-family: 'JetBrains Mono', monospace;
}

/* ===== 进入按钮 ===== */
.enter-btn {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 36px;
  margin-top: 20px;
  border: 1px solid rgba(0, 240, 255, 0.3);
  border-radius: 10px;
  background: rgba(0, 240, 255, 0.08);
  color: #00f0ff;
  font-family: 'Outfit', sans-serif;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  overflow: hidden;
  transition: all 300ms cubic-bezier(0.4, 0, 0.2, 1);
  backdrop-filter: blur(8px);
}
.enter-btn::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(0, 240, 255, 0.15), rgba(59, 130, 246, 0.1));
  opacity: 0;
  transition: opacity 300ms ease;
}
.enter-btn:hover {
  border-color: #00f0ff;
  color: #f1f5f9;
  box-shadow:
    0 0 20px rgba(0, 240, 255, 0.3),
    0 0 40px rgba(0, 240, 255, 0.15);
  transform: translateY(-2px);
}
.enter-btn:hover::before {
  opacity: 1;
}
.enter-btn:active {
  transform: translateY(0) scale(0.98);
}
.btn-text {
  position: relative;
  z-index: 1;
}
.btn-arrow {
  position: relative;
  z-index: 1;
  transition: transform 300ms ease;
}
.enter-btn:hover .btn-arrow {
  transform: translateX(4px);
}
.btn-glow {
  position: absolute;
  top: 50%;
  left: -100%;
  width: 60%;
  height: 200%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.08), transparent);
  transform: translateY(-50%) rotate(15deg);
  transition: left 600ms ease;
}
.enter-btn:hover .btn-glow {
  left: 120%;
}

/* ===== 状态栏 ===== */
.status-bar {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-top: 16px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #475569;
}
.status-item {
  display: flex;
  align-items: center;
  gap: 6px;
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.6);
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ===== 响应式 ===== */
@media (max-width: 768px) {
  .title-line { font-size: 36px; }
  .title-subtitle { font-size: 14px; }
  .features { gap: 12px; }
  .feature { padding: 4px 10px; }
  .feature-label { font-size: 12px; }
  .enter-btn { padding: 12px 28px; font-size: 14px; }
}
</style>
