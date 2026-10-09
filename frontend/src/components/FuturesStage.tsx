import { Line, OrbitControls } from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { Bloom, EffectComposer } from '@react-three/postprocessing'
import { Pause, Play, Shuffle } from '@phosphor-icons/react'
import { Component, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import * as THREE from 'three'

/* Interactive Monte Carlo explainer for the start screen.

   Hundreds of price paths are simulated with geometric Brownian motion
   (the same idea the engine uses for growth-stage valuation). Paths are
   laid out in depth by their final outcome, so the cloud reads as a cone
   of possible futures. The 10th-90th percentile ribbon is the "honest
   range"; the scrubber slices the cone at any month and reads out the
   distribution there. Prices are indexed to 100 today. */

const N = 220
const STEPS = 48 // months
const MU = 0.11 // annual drift
const SPAN_X = 6.4
const SPAN_Z = 3.4

type Sim = {
  values: Float32Array // N * (STEPS + 1)
  rank: Int32Array // final-outcome rank per path
  p10: number[]; p50: number[]; p90: number[]; below: number[]
}

function mulberry32(seed: number) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function simulate(sigma: number, seed: number): Sim {
  const rand = mulberry32(seed)
  const gauss = () => Math.sqrt(-2 * Math.log(rand() || 1e-9)) * Math.cos(2 * Math.PI * rand())
  const dt = 1 / 12
  const drift = (MU - 0.5 * sigma * sigma) * dt
  const shock = sigma * Math.sqrt(dt)
  const values = new Float32Array(N * (STEPS + 1))

  for (let p = 0; p < N; p++) {
    let s = 100
    values[p * (STEPS + 1)] = s
    for (let t = 1; t <= STEPS; t++) {
      s *= Math.exp(drift + shock * gauss())
      values[p * (STEPS + 1) + t] = s
    }
  }

  const order = Array.from({ length: N }, (_, p) => p)
    .sort((a, b) => values[a * (STEPS + 1) + STEPS] - values[b * (STEPS + 1) + STEPS])
  const rank = new Int32Array(N)
  order.forEach((p, r) => { rank[p] = r })

  const p10: number[] = [], p50: number[] = [], p90: number[] = [], below: number[] = []
  for (let t = 0; t <= STEPS; t++) {
    const col = Array.from({ length: N }, (_, p) => values[p * (STEPS + 1) + t]).sort((a, b) => a - b)
    p10.push(col[Math.floor(N * 0.1)])
    p50.push(col[Math.floor(N * 0.5)])
    p90.push(col[Math.floor(N * 0.9)])
    below.push(t === 0 ? 0 : col.filter((v) => v < 100).length / N)
  }
  return { values, rank, p10, p50, p90, below }
}

const X = (t: number) => (t / STEPS) * SPAN_X - SPAN_X / 2
const Y = (v: number) => Math.max(-2.6, Math.min(3.4, Math.log(v / 100) * 2.3))
const Z = (fraction: number) => (fraction - 0.5) * SPAN_Z

const LOW = new THREE.Color('#ff6a3d')
const MID = new THREE.Color('#8b9bb4')
const HIGH = new THREE.Color('#3f8ff0')
const TOP = new THREE.Color('#2fe0a6')

function outcomeColor(fraction: number) {
  if (fraction < 0.5) return LOW.clone().lerp(MID, fraction / 0.5)
  if (fraction < 0.85) return MID.clone().lerp(HIGH, (fraction - 0.5) / 0.35)
  return HIGH.clone().lerp(TOP, (fraction - 0.85) / 0.15)
}

function Scene({ sim, step, still }: { sim: Sim; step: number; still: boolean }) {
  const lines = useRef<THREE.LineSegments>(null)
  const comets = useRef<THREE.Points>(null)
  const slice = useRef<THREE.Points>(null)
  const reveal = useRef(0)

  // All path segments in one draw call, ordered by time so a draw range
  // "grows" the cone from today outwards.
  const { segments, colors, cometColors } = useMemo(() => {
    const segments = new Float32Array(N * STEPS * 6)
    const colors = new Float32Array(N * STEPS * 6)
    const cometColors = new Float32Array(N * 3)
    let i = 0
    for (let t = 0; t < STEPS; t++) {
      for (let p = 0; p < N; p++) {
        const f = sim.rank[p] / (N - 1)
        const c = outcomeColor(f)
        const fade = 0.35 + 0.65 * (t / STEPS)
        const a = sim.values[p * (STEPS + 1) + t]
        const b = sim.values[p * (STEPS + 1) + t + 1]
        segments.set([X(t), Y(a), Z(f), X(t + 1), Y(b), Z(f)], i)
        colors.set([c.r * fade, c.g * fade, c.b * fade, c.r * fade, c.g * fade, c.b * fade], i)
        i += 6
      }
    }
    for (let p = 0; p < N; p++) {
      const c = outcomeColor(sim.rank[p] / (N - 1)).lerp(new THREE.Color('#ffffff'), 0.35)
      cometColors.set([c.r, c.g, c.b], p * 3)
    }
    return { segments, colors, cometColors }
  }, [sim])

  const ribbon = useMemo(() => {
    const geo = new THREE.BufferGeometry()
    const pos: number[] = []
    for (let t = 0; t < STEPS; t++) {
      const a10 = [X(t), Y(sim.p10[t]), Z(0.1)], a90 = [X(t), Y(sim.p90[t]), Z(0.9)]
      const b10 = [X(t + 1), Y(sim.p10[t + 1]), Z(0.1)], b90 = [X(t + 1), Y(sim.p90[t + 1]), Z(0.9)]
      pos.push(...a10, ...a90, ...b90, ...a10, ...b90, ...b10)
    }
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3))
    return geo
  }, [sim])

  const curve = (key: 'p10' | 'p50' | 'p90', f: number) =>
    sim[key].map((v, t) => new THREE.Vector3(X(t), Y(v), Z(f)))

  useEffect(() => { reveal.current = still ? 1 : 0 }, [sim, still])

  useFrame((state, delta) => {
    if (reveal.current < 1) reveal.current = Math.min(1, reveal.current + delta / 1.8)
    const eased = 1 - Math.pow(1 - reveal.current, 3)
    lines.current?.geometry.setDrawRange(0, Math.floor(eased * STEPS) * N * 2)

    const pts = comets.current?.geometry.getAttribute('position') as THREE.BufferAttribute | undefined
    if (pts) {
      const time = still ? 0.999 : state.clock.elapsedTime
      for (let p = 0; p < N; p++) {
        const progress = still ? 1 : ((time * 0.12 + (p * 0.618) % 1) % 1) * eased
        const ft = progress * STEPS
        const t0 = Math.min(Math.floor(ft), STEPS - 1)
        const k = ft - t0
        const a = sim.values[p * (STEPS + 1) + t0]
        const b = sim.values[p * (STEPS + 1) + t0 + 1]
        const f = sim.rank[p] / (N - 1)
        pts.setXYZ(p, X(t0 + k), Y(a + (b - a) * k), Z(f))
      }
      pts.needsUpdate = true
    }

    const sl = slice.current?.geometry.getAttribute('position') as THREE.BufferAttribute | undefined
    if (sl) {
      for (let p = 0; p < N; p++) {
        sl.setXYZ(p, X(step), Y(sim.values[p * (STEPS + 1) + step]), Z(sim.rank[p] / (N - 1)))
      }
      sl.needsUpdate = true
    }
  })

  return (
    <group position={[0.4, -0.3, 0]}>
      <lineSegments ref={lines}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[segments, 3]} />
          <bufferAttribute attach="attributes-color" args={[colors, 3]} />
        </bufferGeometry>
        <lineBasicMaterial vertexColors transparent opacity={0.55} blending={THREE.AdditiveBlending} depthWrite={false} />
      </lineSegments>

      <mesh geometry={ribbon}>
        <meshBasicMaterial color="#3f8ff0" transparent opacity={0.07} side={THREE.DoubleSide} depthWrite={false} blending={THREE.AdditiveBlending} />
      </mesh>

      <Line points={curve('p90', 0.9)} color="#7fb6ff" lineWidth={1.6} transparent opacity={0.9} />
      <Line points={curve('p50', 0.5)} color="#ffffff" lineWidth={2.4} />
      <Line points={curve('p10', 0.1)} color="#ff8a63" lineWidth={1.6} transparent opacity={0.9} />

      <points ref={comets}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[new Float32Array(N * 3), 3]} />
          <bufferAttribute attach="attributes-color" args={[cometColors, 3]} />
        </bufferGeometry>
        <pointsMaterial size={0.055} vertexColors transparent opacity={0.95} blending={THREE.AdditiveBlending} depthWrite={false} sizeAttenuation />
      </points>

      {/* time scrubber: a thin glowing frame slicing the cone */}
      <Line points={[
        [X(step), -2.6, -SPAN_Z / 2 - 0.3], [X(step), 3.4, -SPAN_Z / 2 - 0.3],
        [X(step), 3.4, SPAN_Z / 2 + 0.3], [X(step), -2.6, SPAN_Z / 2 + 0.3], [X(step), -2.6, -SPAN_Z / 2 - 0.3],
      ]} color="#9cc4ff" lineWidth={1} transparent opacity={0.35} />
      <points ref={slice}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[new Float32Array(N * 3), 3]} />
        </bufferGeometry>
        <pointsMaterial size={0.07} color="#ffffff" transparent opacity={0.9} blending={THREE.AdditiveBlending} depthWrite={false} />
      </points>

      <mesh position={[X(0), Y(100), 0]}>
        <sphereGeometry args={[0.09, 24, 24]} />
        <meshBasicMaterial color="#ffffff" />
      </mesh>
      <gridHelper args={[12, 24, '#2b3a55', '#1a2333']} position={[0, -2.7, 0]} />
    </group>
  )
}

class GLBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? this.props.fallback : this.props.children }
}

export default function FuturesStage() {
  const host = useRef<HTMLDivElement>(null)
  const [sigma, setSigma] = useState(0.3)
  const [seed, setSeed] = useState(7)
  const [step, setStep] = useState(STEPS)
  const [playing, setPlaying] = useState(true)
  const [onScreen, setOnScreen] = useState(true)
  const [still] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)

  const sim = useMemo(() => simulate(sigma, seed), [sigma, seed])

  useEffect(() => {
    const el = host.current
    if (!el) return
    const io = new IntersectionObserver(([e]) => setOnScreen(e.isIntersecting))
    io.observe(el)
    return () => io.disconnect()
  }, [])

  // Auto-sweep the scrubber through time until the user takes over.
  useEffect(() => {
    if (!playing || still || !onScreen) return
    const id = window.setInterval(() => setStep((s) => (s >= STEPS ? 1 : s + 1)), 140)
    return () => window.clearInterval(id)
  }, [playing, still, onScreen])

  const fallback = <div className="stage-fallback">3D view needs WebGL, which this browser has turned off.</div>

  return (
    <div className="stage-canvas" ref={host}>
      <GLBoundary fallback={fallback}>
        <Canvas camera={{ position: [6.2, 2.6, 7.4], fov: 38 }} dpr={[1, 1.75]}
          frameloop={onScreen ? 'always' : 'never'} gl={{ antialias: true, alpha: true }}
          aria-label="Interactive 3D view of simulated price paths">
          <Scene sim={sim} step={step} still={still} />
          <OrbitControls enableZoom={false} enablePan={false} autoRotate={!still} autoRotateSpeed={0.35}
            enableDamping minPolarAngle={0.6} maxPolarAngle={1.55} />
          <EffectComposer>
            <Bloom intensity={0.9} luminanceThreshold={0.12} luminanceSmoothing={0.3} mipmapBlur />
          </EffectComposer>
        </Canvas>
      </GLBoundary>

      <div className="stage-controls" role="group" aria-label="Simulation controls">
        <button type="button" className="stage-btn" onClick={() => setPlaying((p) => !p)}
          aria-label={playing ? 'Pause time sweep' : 'Play time sweep'}>
          {playing ? <Pause size={16} weight="fill" /> : <Play size={16} weight="fill" />}
        </button>
        <label className="stage-slider">
          <span>Month <b>{step}</b></span>
          <input type="range" min={1} max={STEPS} value={step}
            onChange={(e) => { setPlaying(false); setStep(Number(e.target.value)) }} />
        </label>
        <label className="stage-slider">
          <span>Volatility <b>{Math.round(sigma * 100)}%</b></span>
          <input type="range" min={10} max={60} step={5} value={Math.round(sigma * 100)}
            onChange={(e) => setSigma(Number(e.target.value) / 100)} />
        </label>
        <button type="button" className="stage-btn" onClick={() => setSeed((s) => s + 1)} aria-label="Draw a new set of simulated paths" title="Resample">
          <Shuffle size={16} weight="bold" />
        </button>
      </div>
      <div className="stage-readout" aria-live="off">
        <div className="r-title">Month {step} of {STEPS}</div>
        <div><i className="k hi" />90th percentile <b>₹{Math.round(sim.p90[step])}</b></div>
        <div><i className="k mid" />Median <b>₹{Math.round(sim.p50[step])}</b></div>
        <div><i className="k lo" />10th percentile <b>₹{Math.round(sim.p10[step])}</b></div>
        <div className="r-foot">{Math.round(sim.below[step] * 100)}% of paths below the ₹100 start</div>
      </div>
      <p className="stage-hint" aria-hidden="true">Drag to rotate</p>
    </div>
  )
}
