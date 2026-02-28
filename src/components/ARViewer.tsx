import { Suspense, useCallback, useEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { useGLTF } from '@react-three/drei'
import { XR, createXRStore, useXR } from '@react-three/xr'
import * as THREE from 'three'

// ─── Types ────────────────────────────────────────────────────────────────────

type ARStatus = 'idle' | 'requesting' | 'active' | 'denied' | 'unsupported'

// ─── XR Store (module-level singleton) ────────────────────────────────────────
// createXRStore must not be called inside render. It configures the WebXR session:
// - 'immersive-ar': the browser enters AR mode using the device camera + SLAM tracking
// - 'local-floor': reference space where Y=0 is the real-world floor and the origin
//   is directly below where the user stood when the session started.
//
// This gives us true 6DoF tracking: the camera's position AND orientation update as
// the user physically moves, so the model appears anchored in the real world.

const xrStore = createXRStore({
  hand: false,
  controller: false,
})

// ─── GLB Car Model ────────────────────────────────────────────────────────────
// The model is placed ONCE at a fixed world-space position and never moved again.
// Because the XR camera pose updates as the user physically walks, the model:
//   • Gets bigger as you walk toward it (closer in world space → larger projection)
//   • Gets smaller as you walk away
//   • Reveals different sides as you walk around it
//
// Origin: where the user was standing when AR started, projected to the floor.
// Model placement: bottom sits on the floor (Y=0), DISTANCE_M metres ahead on -Z.

const DISTANCE_M = 4.5

function CarModel({ url }: { url: string }) {
  const { scene } = useGLTF(url)
  const groupRef = useRef<THREE.Group | null>(null)
  const positioned = useRef(false)

  useEffect(() => {
    positioned.current = false
  }, [url])

  useFrame(() => {
    if (positioned.current || !groupRef.current) return

    const nativeBox = new THREE.Box3().setFromObject(groupRef.current)
    if (nativeBox.isEmpty()) return
    positioned.current = true

    const nativeSize = nativeBox.getSize(new THREE.Vector3())
    const nativeMax = Math.max(nativeSize.x, nativeSize.y, nativeSize.z)

    // Normalise to real car length (~4.5 m) regardless of export units (m/cm/mm)
    if (nativeMax > 0) {
      groupRef.current.scale.setScalar(4.5 / nativeMax)
    }

    // Recompute bounds after scale
    const box = new THREE.Box3().setFromObject(groupRef.current)
    const center = box.getCenter(new THREE.Vector3())

    // Bottom of car on the virtual ground plane (Y=0), centred on X, DISTANCE_M ahead
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

// ─── XR Session Bridge ────────────────────────────────────────────────────────
// Runs inside the Canvas/XR tree so it can access XR state via useXR(), then
// propagates the session-active flag back to the parent React component.

function XRSessionSync({ onActive }: { onActive: (active: boolean) => void }) {
  const session = useXR(s => s.session)
  useEffect(() => { onActive(!!session) }, [session, onActive])
  return null
}

// ─── Main Component ───────────────────────────────────────────────────────────

interface ARViewerProps {
  glbUrl: string | null
}

export default function ARViewer({ glbUrl }: ARViewerProps) {
  const [status, setStatus] = useState<ARStatus>('idle')

  // Probe WebXR AR support once on mount
  useEffect(() => {
    const xrNav = (navigator as { xr?: { isSessionSupported: (t: string) => Promise<boolean> } }).xr
    if (!xrNav?.isSessionSupported) { setStatus('unsupported'); return }
    xrNav.isSessionSupported('immersive-ar')
      .then(ok => { if (!ok) setStatus('unsupported') })
      .catch(() => setStatus('unsupported'))
  }, [])

  // Called by XRSessionSync whenever the XR session starts or ends
  const handleSessionActive = useCallback((active: boolean) => {
    setStatus(prev => {
      if (active) return 'active'
      return prev === 'active' ? 'idle' : prev   // session ended → back to idle
    })
  }, [])

  const startAR = async () => {
    setStatus('requesting')
    try {
      await xrStore.enterAR()
      // XRSessionSync will set status → 'active' once the session is live
    } catch {
      setStatus('denied')
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

  // ── WebXR AR not supported (desktop, iOS Safari, etc.) ────────────────────
  if (status === 'unsupported') {
    return (
      <div style={{ ...centered, gap: 12 }}>
        <span style={{ fontSize: '0.78rem', color: '#D93025', letterSpacing: '0.04em' }}>
          AR NOT SUPPORTED
        </span>
        <span style={{ ...hint, textAlign: 'center', maxWidth: 260 }}>
          Walk-around AR requires WebXR. Use Chrome on Android or another WebXR-compatible browser.
        </span>
      </div>
    )
  }

  // ── AR view ───────────────────────────────────────────────────────────────
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', background: '#000' }}>

      {/* Three.js canvas with WebXR enabled.
          In AR mode the XR compositor renders the real camera feed behind the canvas,
          and the transparent canvas overlays only the 3D model on top. */}
      <Canvas
        camera={{ fov: 62, near: 0.01, far: 1000 }}
        gl={{ alpha: true, antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
      >
        <XR store={xrStore}>
          {/* Bridge XR session state to parent */}
          <XRSessionSync onActive={handleSessionActive} />

          {/* Lighting */}
          <ambientLight intensity={0.8} />
          <directionalLight position={[5, 10, 5]} intensity={1.5} castShadow />
          <directionalLight position={[-4, 4, -5]} intensity={0.4} />

          {/* World-anchored car model — placed once, never moved */}
          <Suspense fallback={null}>
            <CarModel key={glbUrl} url={glbUrl} />
          </Suspense>
        </XR>
      </Canvas>

      {/* Overlay UI — hidden once the XR session takes over the display */}
      {status === 'idle' && (
        <div style={{ ...centered, position: 'absolute', inset: 0 }}>
          <button style={primaryBtn} onClick={startAR}>
            START AR
          </button>
          <span style={hint}>CAMERA ACCESS REQUIRED</span>
        </div>
      )}

      {status === 'requesting' && (
        <div style={{ ...centered, position: 'absolute', inset: 0 }}>
          <span style={{ ...hint, color: 'rgba(255,255,255,0.6)' }}>STARTING AR…</span>
        </div>
      )}

      {status === 'denied' && (
        <div style={{ ...centered, position: 'absolute', inset: 0, gap: 12 }}>
          <span style={{ fontSize: '0.78rem', color: '#D93025', letterSpacing: '0.04em' }}>
            AR UNAVAILABLE
          </span>
          <span style={{ ...hint, textAlign: 'center', maxWidth: 220 }}>
            Allow camera access in your browser settings, then reload the page.
          </span>
          <button style={primaryBtn} onClick={startAR}>
            TRY AGAIN
          </button>
        </div>
      )}

      {status === 'active' && (
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
          WALK AROUND TO EXPLORE THE VEHICLE
        </span>
      )}

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
