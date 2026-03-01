import { Suspense, useCallback, useEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useGLTF, ContactShadows, Environment } from '@react-three/drei'
import { ImageSegmenter, FilesetResolver } from '@mediapipe/tasks-vision'
import * as THREE from 'three'

// ─── Constants ────────────────────────────────────────────────────────────────

const REAL_CAR_M = 4.5   // normalised car length in metres
const V_FOV      = 65    // vertical FOV matching a typical phone rear camera
const EYE_HEIGHT = 1.6   // camera height above ground in metres
const CAR_Z      = -5    // initial car distance in front of camera in metres

// WASM assets must match the installed npm package version (0.10.32)
const MP_WASM_URL  = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.32/wasm'
const MP_MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite'

// ─── CameraRig ────────────────────────────────────────────────────────────────
// Positions the Three.js camera at eye height and smoothly tilts it each frame
// to match the horizon line MediaPipe estimated from the real camera feed.

function CameraRig({ tiltRef }: { tiltRef: React.RefObject<number> }) {
  const { camera } = useThree()

  useEffect(() => {
    camera.position.set(0, EYE_HEIGHT, 0)
    camera.rotation.order = 'YXZ'
    camera.rotation.set(0, 0, 0)
  }, [camera])

  useFrame(() => {
    // Negative rotation.x = looking downward in Three.js
    const target = -THREE.MathUtils.degToRad(tiltRef.current)
    camera.rotation.x = THREE.MathUtils.lerp(camera.rotation.x, target, 0.06)
  })

  return null
}

// ─── CarModel ────────────────────────────────────────────────────────────────
// Loads the GLB, normalises it to real-world car size (REAL_CAR_M), and parks
// its bottom face at Y = 0 (the virtual ground plane).

function CarModel({
  url,
  rotYRef,
  scaleRef,
}: {
  url: string
  rotYRef: React.RefObject<number>
  scaleRef: React.RefObject<number>
}) {
  const { scene } = useGLTF(url)
  const worldRef  = useRef<THREE.Group>(null)
  const offsetRef = useRef<THREE.Group>(null)
  const ready     = useRef(false)
  const baseScale = useRef(1)

  // Reset sizing when a new GLB is loaded
  useEffect(() => { ready.current = false }, [url])

  useFrame(() => {
    if (!worldRef.current || !offsetRef.current) return

    // One-time sizing: runs on the first frame that the scene has geometry
    if (!ready.current) {
      const box = new THREE.Box3().setFromObject(offsetRef.current)
      if (box.isEmpty()) return
      ready.current = true

      const size = box.getSize(new THREE.Vector3())
      baseScale.current = REAL_CAR_M / Math.max(size.x, size.y, size.z)

      // Shift the scene so bottom face sits at local Y=0, centred on XZ
      const c = box.getCenter(new THREE.Vector3())
      offsetRef.current.position.set(-c.x, -box.min.y, -c.z)
    }

    worldRef.current.scale.setScalar(baseScale.current * scaleRef.current)
    worldRef.current.rotation.y = rotYRef.current
  })

  return (
    <group ref={worldRef} position={[0, 0, CAR_Z]}>
      <group ref={offsetRef}>
        <primitive object={scene} />
      </group>
    </group>
  )
}

// ─── LiveARViewer ─────────────────────────────────────────────────────────────

interface LiveARViewerProps {
  glbUrl: string | null
}

export default function LiveARViewer({ glbUrl }: LiveARViewerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const segRef   = useRef<ImageSegmenter | null>(null)

  // MediaPipe writes here; CameraRig reads it each frame — no re-render needed
  const tiltRef  = useRef(15)  // start with a slight downward tilt
  const rotYRef  = useRef(0)
  const scaleRef = useRef(1)

  const [statusMsg, setStatusMsg]   = useState('STARTING CAMERA…')
  const [mpReady,   setMpReady]     = useState(false)
  const [camReady,  setCamReady]    = useState(false)
  const [error,     setError]       = useState<string | null>(null)

  const pointerMap = useRef(new Map<number, { x: number; y: number }>())

  // ── Camera stream ───────────────────────────────────────────────────────────
  // Depends on glbUrl: the <video> element only mounts after a model is loaded,
  // so we must wait until glbUrl is set before calling getUserMedia.
  useEffect(() => {
    if (!glbUrl) return

    let stream: MediaStream | null = null
    setCamReady(false)
    setError(null)
    setStatusMsg('STARTING CAMERA…')

    navigator.mediaDevices
      .getUserMedia({
        video: {
          facingMode: { ideal: 'environment' },  // prefer rear, falls back on desktop
          width:  { ideal: 1280 },
          height: { ideal: 720 },
        },
      })
      .then(s => {
        stream = s
        const v = videoRef.current
        if (!v) return
        v.srcObject = s
        v.onloadedmetadata = () => {
          v.play()
            .then(() => { setCamReady(true); setStatusMsg('INITIALIZING AI…') })
            .catch(() => setError('VIDEO PLAYBACK BLOCKED'))
        }
      })
      .catch(() => setError('CAMERA ACCESS DENIED'))

    return () => { stream?.getTracks().forEach(t => t.stop()) }
  }, [glbUrl])

  // ── MediaPipe segmenter init ────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false

    ;(async () => {
      try {
        const vision = await FilesetResolver.forVisionTasks(MP_WASM_URL)
        const seg = await ImageSegmenter.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: MP_MODEL_URL,
            delegate: 'GPU',
          },
          outputCategoryMask: true,
          outputConfidenceMasks: false,
          runningMode: 'VIDEO',
        })
        if (!cancelled) {
          segRef.current = seg
          setMpReady(true)
          setStatusMsg('DRAG TO ROTATE · PINCH TO RESIZE')
        }
      } catch {
        if (!cancelled) setError('AI INIT FAILED — check network connection')
      }
    })()

    return () => { cancelled = true }
  }, [])

  // ── Segmentation loop ───────────────────────────────────────────────────────
  // Runs at ~5 fps to estimate the horizon line from the camera feed.
  // The background class (0) in the lower frame is used as a ground proxy.
  // The topmost row where ≥65 % of sampled pixels are background = horizon.
  useEffect(() => {
    if (!mpReady || !camReady) return

    let rafId: number
    let lastMs = 0

    const loop = (now: number) => {
      rafId = requestAnimationFrame(loop)
      if (now - lastMs < 200) return   // 5 fps ceiling for the segmenter
      lastMs = now

      const seg = segRef.current
      const v   = videoRef.current
      if (!seg || !v || v.readyState < 2) return

      const result = seg.segmentForVideo(v, now)
      const mask   = result.categoryMask
      if (!mask) return

      const { width, height } = mask
      const data = mask.getAsUint8Array()

      // Sample ~40 columns per row to stay fast
      const step   = Math.max(1, Math.floor(width / 40))
      const topRow = Math.floor(height * 0.35)
      const botRow = Math.floor(height * 0.80)
      let horizonNorm = 0.60  // fallback: 60 % down

      for (let row = topRow; row <= botRow; row++) {
        let bg = 0, total = 0
        for (let col = 0; col < width; col += step) {
          if (data[row * width + col] === 0) bg++
          total++
        }
        if (bg / total >= 0.65) {
          horizonNorm = row / height
          break
        }
      }

      mask.close()

      // horizon at 0.5 → camera level (0°); each % below = proportional tilt
      tiltRef.current = (horizonNorm - 0.5) * V_FOV
    }

    rafId = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(rafId)
  }, [mpReady, camReady])

  // ── Pointer gestures ────────────────────────────────────────────────────────
  const onPointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId)
    pointerMap.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
  }, [])

  const onPointerMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    const prev = pointerMap.current.get(e.pointerId)
    if (!prev) return
    const pts = [...pointerMap.current]

    if (pts.length === 1) {
      // Single finger / mouse drag → Y-rotate
      rotYRef.current += (e.clientX - prev.x) * 0.012
    } else if (pts.length >= 2) {
      // Two fingers → pinch-to-scale
      const other = pts.find(([id]) => id !== e.pointerId)
      if (other) {
        const o       = other[1]
        const curDist = Math.hypot(e.clientX - o.x, e.clientY - o.y)
        const prvDist = Math.hypot(prev.x    - o.x, prev.y    - o.y)
        if (prvDist > 0) {
          scaleRef.current = Math.max(0.1, Math.min(5, scaleRef.current * (curDist / prvDist)))
        }
      }
    }

    pointerMap.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
  }, [])

  const onPointerUp = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    e.currentTarget.releasePointerCapture(e.pointerId)
    pointerMap.current.delete(e.pointerId)
  }, [])

  // ── Empty state ─────────────────────────────────────────────────────────────
  if (!glbUrl) {
    return (
      <div style={css.empty}>
        <span style={{ fontSize: 36, opacity: 0.25 }}>◈</span>
        <span style={css.hint}>LOAD A GLB FILE TO ENABLE LIVE VIEW</span>
      </div>
    )
  }

  // ── AR view ─────────────────────────────────────────────────────────────────
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden', background: '#000' }}>

      {/* ── Real-world camera feed (background) ─────────────────────────── */}
      <video
        ref={videoRef}
        muted
        playsInline
        autoPlay
        style={css.video}
      />

      {/* ── Three.js overlay (transparent canvas on top of video) ────────── */}
      <Canvas
        shadows
        dpr={[1, 1.5]}
        camera={{ fov: V_FOV, near: 0.01, far: 500 }}
        gl={{
          alpha: true,
          antialias: true,
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.0,
        }}
        style={css.canvas}
      >
        {/* Adjusts camera pitch to align virtual ground with real horizon */}
        <CameraRig tiltRef={tiltRef} />

        {/* Outdoor-style lighting */}
        <ambientLight intensity={0.75} />
        <directionalLight
          position={[6, 12, 4]}
          intensity={1.4}
          castShadow
          shadow-mapSize={[2048, 2048]}
          shadow-camera-near={0.5}
          shadow-camera-far={60}
          shadow-camera-left={-12}
          shadow-camera-right={12}
          shadow-camera-top={12}
          shadow-camera-bottom={-12}
        />
        <directionalLight position={[-5, 6, -4]} intensity={0.3} />

        <Suspense fallback={null}>
          {/* Shadow-receiving ground plane (invisible except for shadows) */}
          <mesh rotation-x={-Math.PI / 2} position-y={0.001} receiveShadow>
            <planeGeometry args={[200, 200]} />
            <shadowMaterial opacity={0.28} transparent />
          </mesh>

          <CarModel url={glbUrl} rotYRef={rotYRef} scaleRef={scaleRef} />

          {/* Soft contact shadow anchored beneath the car */}
          <ContactShadows
            position={[0, 0.002, CAR_Z]}
            opacity={0.5}
            scale={24}
            blur={2.2}
            far={10}
            color="#000000"
          />

          <Environment preset="city" />
        </Suspense>
      </Canvas>

      {/* ── Gesture capture + status overlay ─────────────────────────────── */}
      <div
        style={css.gestureLayer}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
      >
        {/* Status / hint banner */}
        {!error && (
          <span style={css.banner}>{statusMsg}</span>
        )}

        {/* AI indicator while initialising */}
        {!mpReady && !error && (
          <div style={css.aiPill}>
            <span style={css.aiDot} />
            AI GROUND DETECTION LOADING
          </div>
        )}

        {/* Error overlay */}
        {error && (
          <div style={css.errorOverlay}>
            <span style={css.errorText}>{error}</span>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const css: Record<string, CSSProperties> = {
  empty: {
    width: '100%', height: '100%',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    flexDirection: 'column', gap: 12,
  },
  hint: {
    fontSize: '0.62rem',
    color: 'rgba(255,255,255,0.38)',
    letterSpacing: '0.08em',
  },
  video: {
    position: 'absolute', inset: 0,
    width: '100%', height: '100%',
    objectFit: 'cover',
    zIndex: 0,
  },
  canvas: {
    position: 'absolute', inset: 0,
    zIndex: 1,
    pointerEvents: 'none',
  },
  gestureLayer: {
    position: 'absolute', inset: 0,
    zIndex: 2,
  },
  banner: {
    position: 'absolute',
    top: 14, left: 0, right: 0,
    textAlign: 'center',
    fontSize: '0.55rem',
    color: 'rgba(255,255,255,0.8)',
    letterSpacing: '0.08em',
    pointerEvents: 'none',
  },
  aiPill: {
    position: 'absolute',
    bottom: 20, left: '50%',
    transform: 'translateX(-50%)',
    display: 'flex', alignItems: 'center', gap: 6,
    background: 'rgba(0,0,0,0.55)',
    border: '1px solid rgba(255,255,255,0.15)',
    borderRadius: 100,
    padding: '6px 14px',
    fontSize: '0.55rem',
    color: 'rgba(255,255,255,0.75)',
    letterSpacing: '0.08em',
    pointerEvents: 'none',
    backdropFilter: 'blur(8px)',
  },
  aiDot: {
    width: 6, height: 6,
    borderRadius: '50%',
    background: '#FFAA6E',
    animation: 'pulse 1.4s ease-in-out infinite',
  },
  errorOverlay: {
    position: 'absolute', inset: 0,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: 'rgba(0,0,0,0.65)',
  },
  errorText: {
    fontSize: '0.78rem',
    color: '#D93025',
    letterSpacing: '0.04em',
  },
}
