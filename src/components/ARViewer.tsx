import { Suspense, useEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useGLTF } from '@react-three/drei'
import * as THREE from 'three'

// ─── Types ────────────────────────────────────────────────────────────────────

interface Orientation { alpha: number; beta: number; gamma: number }
type ARState = 'idle' | 'requesting' | 'active' | 'denied'

// ─── Three.js camera controller ───────────────────────────────────────────────
// Reads device orientation every frame and applies it to the Three.js camera,
// making the scene appear world-anchored as the user moves the device.

function DeviceCamera({ oRef, initialAlpha }: {
  oRef: { current: Orientation }
  initialAlpha: { current: number | null }
}) {
  const { camera, gl } = useThree()

  useEffect(() => {
    gl.setClearColor(0x000000, 0)  // transparent canvas — camera video shows through
    camera.rotation.order = 'YXZ'
  }, [camera, gl])

  useFrame(() => {
    const { alpha, beta, gamma } = oRef.current

    // First valid reading: record it as the "forward" heading
    if (initialAlpha.current === null && alpha !== 0) {
      initialAlpha.current = alpha
    }

    const headingOffset = initialAlpha.current ?? 0

    // Phone held in portrait, tilted to face user: beta ≈ 90 = looking straight ahead
    camera.rotation.x = THREE.MathUtils.degToRad(beta - 90)
    camera.rotation.y = THREE.MathUtils.degToRad(-(alpha - headingOffset))
    camera.rotation.z = THREE.MathUtils.degToRad(-gamma)
  })

  return null
}

// ─── GLB Car Model ────────────────────────────────────────────────────────────
// Normalises the model to a real-world car size (longest axis = 4.5 m) so the
// distance is consistent regardless of whether the GLB was exported in metres,
// centimetres, or any other unit. Then places it ~1.5 m (≈5 feet) in front.

// Desired distance from camera to the model's centre, in metres.
const DISTANCE_M = 1.5

function CarModel({ url }: { url: string }) {
  const { scene } = useGLTF(url)
  const groupRef = useRef<THREE.Group | null>(null)
  const positioned = useRef(false)

  useEffect(() => {
    positioned.current = false
  }, [url])

  useFrame(() => {
    if (positioned.current || !groupRef.current) return

    // Measure the model in its native unit
    const nativeBox = new THREE.Box3().setFromObject(groupRef.current)
    if (nativeBox.isEmpty()) return
    positioned.current = true

    const nativeSize = nativeBox.getSize(new THREE.Vector3())
    const nativeMax = Math.max(nativeSize.x, nativeSize.y, nativeSize.z)

    // Scale so the longest axis equals a real car length (~4.5 m).
    // This corrects cm/mm exports automatically.
    if (nativeMax > 0) {
      groupRef.current.scale.setScalar(4.5 / nativeMax)
    }

    // Recompute box now that scale is applied
    const box = new THREE.Box3().setFromObject(groupRef.current)
    const center = box.getCenter(new THREE.Vector3())

    // Bottom of car on ground (Y=0), centered on X, DISTANCE_M ahead on Z
    groupRef.current.position.set(
      -center.x,
      -box.min.y,
      -center.z - DISTANCE_M,
    )
  })

  return (
    <group ref={groupRef}>
      <primitive object={scene} />
    </group>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface ARViewerProps {
  glbUrl: string | null
}

export default function ARViewer({ glbUrl }: ARViewerProps) {
  const [arState, setArState] = useState<ARState>('idle')
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const orientationRef = useRef<Orientation>({ alpha: 0, beta: 0, gamma: 0 })
  const initialAlpha = useRef<number | null>(null)
  const orientHandlerRef = useRef<((e: DeviceOrientationEvent) => void) | null>(null)

  // Assign the stream to the video element once it renders (state → 'active')
  useEffect(() => {
    if (arState !== 'active' || !videoRef.current || !streamRef.current) return
    videoRef.current.srcObject = streamRef.current
    videoRef.current.play().catch(() => {})
  }, [arState])

  // Cleanup camera + orientation listener on unmount
  useEffect(() => {
    return () => {
      if (orientHandlerRef.current) {
        window.removeEventListener('deviceorientation', orientHandlerRef.current)
      }
      streamRef.current?.getTracks().forEach(t => t.stop())
    }
  }, [])

  const startLiveView = async () => {
    setArState('requesting')

    // iOS 13+ requires DeviceOrientationEvent.requestPermission() to be called
    // SYNCHRONOUSLY within a user-gesture handler — before any `await`.
    // After the first await the gesture context is gone and iOS throws SecurityError.
    // We fire the permission request here (before any await) and store the Promise.
    const DevOrient = DeviceOrientationEvent as unknown as {
      requestPermission?: () => Promise<PermissionState>
    }
    const orientPermPromise: Promise<PermissionState> =
      typeof DevOrient.requestPermission === 'function'
        ? DevOrient.requestPermission().catch(() => 'denied' as PermissionState)
        : Promise.resolve('granted' as PermissionState)

    try {
      // 1. Request rear camera; fall back to any camera (desktop / front-only devices)
      let stream: MediaStream
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } },
          audio: false,
        })
      } catch {
        // Retry with minimal constraints (handles some strict iOS camera policies)
        stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      }
      streamRef.current = stream

      // 2. Await orientation permission (already in-flight from above)
      await orientPermPromise
      // Orientation errors are non-fatal — model stays static if denied

      // 3. Listen for orientation updates
      const handler = (e: DeviceOrientationEvent) => {
        orientationRef.current = {
          alpha: e.alpha ?? 0,
          beta: e.beta ?? 0,
          gamma: e.gamma ?? 0,
        }
      }
      orientHandlerRef.current = handler
      window.addEventListener('deviceorientation', handler)

      setArState('active')
    } catch {
      // Camera truly unavailable — clean up any partial stream
      streamRef.current?.getTracks().forEach(t => t.stop())
      streamRef.current = null
      setArState('denied')
    }
  }

  // ── No GLB loaded ──────────────────────────────────────────────────────────
  if (!glbUrl) {
    return (
      <div style={centered}>
        <span style={{ fontSize: 36, opacity: 0.25 }}>◈</span>
        <span style={hint}>LOAD A GLB FILE TO ENABLE LIVE VIEW</span>
      </div>
    )
  }

  // ── Idle ──────────────────────────────────────────────────────────────────
  if (arState === 'idle') {
    return (
      <div style={centered}>
        <button style={primaryBtn} onClick={startLiveView}>
          START LIVE VIEW
        </button>
        <span style={hint}>CAMERA + MOTION ACCESS REQUIRED</span>
      </div>
    )
  }

  // ── Requesting permissions ─────────────────────────────────────────────────
  if (arState === 'requesting') {
    return (
      <div style={centered}>
        <span style={{ ...hint, color: 'rgba(255,255,255,0.6)' }}>ENABLING CAMERA…</span>
      </div>
    )
  }

  // ── Denied ────────────────────────────────────────────────────────────────
  if (arState === 'denied') {
    return (
      <div style={{ ...centered, gap: 12 }}>
        <span style={{ fontSize: '0.78rem', color: '#D93025', letterSpacing: '0.04em' }}>
          CAMERA UNAVAILABLE
        </span>
        <span style={{ ...hint, textAlign: 'center', maxWidth: 220 }}>
          Allow camera access in your browser settings, then reload the page.
        </span>
        <button style={primaryBtn} onClick={startLiveView}>
          TRY AGAIN
        </button>
      </div>
    )
  }

  // ── Active — live camera + AR overlay ─────────────────────────────────────
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden', background: '#000' }}>

      {/* Live camera feed as background */}
      <video
        ref={videoRef}
        muted
        playsInline
        autoPlay
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
        }}
      />

      {/* Transparent Three.js canvas — GLB model rendered on top of camera */}
      <Canvas
        gl={{ alpha: true, antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}
        camera={{ fov: 62, near: 0.1, far: 500, position: [0, 1.6, 0] }}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
      >
        {/* Lighting */}
        <ambientLight intensity={0.8} />
        <directionalLight position={[5, 10, 5]} intensity={1.5} castShadow />
        <directionalLight position={[-4, 4, -5]} intensity={0.4} />

        {/* Applies device orientation to camera every frame */}
        <DeviceCamera oRef={orientationRef} initialAlpha={initialAlpha} />

        {/* The GLB car model, life-sized (1 unit = 1 m) */}
        <Suspense fallback={null}>
          <CarModel key={glbUrl} url={glbUrl} />
        </Suspense>
      </Canvas>

      {/* Instruction hint */}
      <span style={{
        position: 'absolute',
        bottom: 12,
        left: 0,
        right: 0,
        textAlign: 'center',
        fontSize: '0.56rem',
        color: 'rgba(255,255,255,0.55)',
        letterSpacing: '0.08em',
        pointerEvents: 'none',
      }}>
        MOVE AROUND TO EXPLORE THE VEHICLE
      </span>

    </div>
  )
}

// ─── Shared styles ────────────────────────────────────────────────────────────

const centered: CSSProperties = {
  width: '100%',
  height: '100%',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  flexDirection: 'column',
  gap: 14,
}

const hint: CSSProperties = {
  fontSize: '0.62rem',
  color: 'rgba(255,255,255,0.38)',
  letterSpacing: '0.08em',
}

const primaryBtn: CSSProperties = {
  background: '#FFAA6E',
  color: '#1a0e00',
  border: 'none',
  borderRadius: 100,
  padding: '12px 28px',
  fontSize: '0.75rem',
  fontWeight: 700,
  letterSpacing: '0.06em',
  cursor: 'pointer',
  WebkitTapHighlightColor: 'transparent',
}
