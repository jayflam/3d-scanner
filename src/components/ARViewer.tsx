import { Suspense, useCallback, useEffect, useRef, useState } from 'react'
import type { CSSProperties, PointerEvent } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { useGLTF } from '@react-three/drei'
import { XR, createXRStore, useXR, useXRHitTest, XRDomOverlay } from '@react-three/xr'
import * as THREE from 'three'

// ─── Types ────────────────────────────────────────────────────────────────────

type ARStatus = 'idle' | 'requesting' | 'active' | 'denied' | 'unsupported'
type PlacementMode = 'placement' | 'placed'

// ─── XR Store ─────────────────────────────────────────────────────────────────
// hitTest: 'required' tells WebXR to enable ARCore plane/mesh detection.
// planeDetection + meshDetection give the hit-test engine more surface data to
// work with → more accurate ground snapping.

const xrStore = createXRStore({
  hand: false,
  controller: false,
  hitTest: 'required',
  planeDetection: true,
  meshDetection: true,
})

// ─── Car Model ────────────────────────────────────────────────────────────────
// Two-group hierarchy:
//   worldRef  — world position (from hit-test), Y-rotation, composite scale
//   offsetRef — baked local offset: bottom of car at offsetRef Y=0, centred XZ
//
// In 'placement' mode the worldRef tracks the hit-test position every frame.
// In 'placed'    mode position is frozen; only rotation & scale update.

const REAL_CAR_M = 4.5   // longest axis → real-world car length

function CarModel({
  url,
  modeRef,
  hitMatrixRef,
  hasHitRef,
  userScaleRef,
  userRotationYRef,
}: {
  url: string
  modeRef:        React.RefObject<PlacementMode>
  hitMatrixRef:   React.RefObject<THREE.Matrix4>
  hasHitRef:      React.RefObject<boolean>
  userScaleRef:   React.RefObject<number>
  userRotationYRef: React.RefObject<number>
}) {
  const { scene } = useGLTF(url)
  const worldRef  = useRef<THREE.Group | null>(null)
  const offsetRef = useRef<THREE.Group | null>(null)
  const initialized  = useRef(false)
  const normalScale  = useRef(1)

  useEffect(() => { initialized.current = false }, [url])

  useFrame(() => {
    if (!worldRef.current || !offsetRef.current) return

    // ── One-time sizing (runs on the first frame the scene has geometry) ──────
    if (!initialized.current) {
      const box = new THREE.Box3().setFromObject(offsetRef.current)
      if (box.isEmpty()) return
      initialized.current = true

      const size   = box.getSize(new THREE.Vector3())
      const maxDim = Math.max(size.x, size.y, size.z)
      normalScale.current = maxDim > 0 ? REAL_CAR_M / maxDim : 1

      // Shift the scene so its bottom sits at local Y=0 and it is centred on XZ.
      // Because worldRef.scale will be applied on top, native units are used here.
      const center = box.getCenter(new THREE.Vector3())
      offsetRef.current.position.set(-center.x, -box.min.y, -center.z)
    }

    // Apply composite scale (normalised car size × user pinch adjustment)
    worldRef.current.scale.setScalar(normalScale.current * (userScaleRef.current ?? 1))

    if (modeRef.current === 'placement') {
      if (!hasHitRef.current) { worldRef.current.visible = false; return }
      worldRef.current.visible = true
      // Snap to the ARCore-detected surface; keep car upright (ignore surface tilt)
      worldRef.current.position.setFromMatrixPosition(hitMatrixRef.current)
      worldRef.current.rotation.set(0, userRotationYRef.current ?? 0, 0)
    } else {
      // Placed: position is frozen; only rotation & scale update each frame
      worldRef.current.visible = true
      worldRef.current.rotation.y = userRotationYRef.current ?? 0
    }
  })

  return (
    <group ref={worldRef}>
      <group ref={offsetRef}>
        <primitive object={scene} />
      </group>
    </group>
  )
}

// ─── XR Session Bridge ────────────────────────────────────────────────────────

function XRSessionSync({ onActive }: { onActive: (v: boolean) => void }) {
  const session = useXR(s => s.session)
  useEffect(() => { onActive(!!session) }, [session, onActive])
  return null
}

// ─── AR Scene (inside Canvas > XR) ───────────────────────────────────────────
// Owns: hit-test loop, reticle mesh, car model, gesture handler, HTML overlay.

function ARScene({
  url,
  mode,
  onConfirmPlacement,
  onReposition,
}: {
  url: string
  mode: PlacementMode
  onConfirmPlacement: () => void
  onReposition: () => void
}) {
  const reticleRef    = useRef<THREE.Mesh | null>(null)
  const hitMatrixRef  = useRef(new THREE.Matrix4())
  const hasHitRef     = useRef(false)
  const userScaleRef  = useRef(1)
  const userRotYRef   = useRef(0)
  // Mirror mode into a ref so useFrame closures always read the latest value
  const modeRef = useRef<PlacementMode>(mode)
  modeRef.current = mode

  // ── ARCore hit-test (plane + mesh detection) ─────────────────────────────
  // useXRHitTest fires every frame while in XR. The 'viewer' reference space
  // shoots the ray from the centre of the camera. The 'plane'+'mesh' trackable
  // types tell ARCore to detect horizontal surfaces (floor, table, etc.).
  const _tmpMat = useRef(new THREE.Matrix4())
  useXRHitTest((results, getWorldMatrix) => {
    if (modeRef.current !== 'placement') return
    if (results.length === 0) {
      hasHitRef.current = false
      if (reticleRef.current) reticleRef.current.visible = false
      return
    }
    getWorldMatrix(_tmpMat.current, results[0])
    hasHitRef.current = true
    hitMatrixRef.current.copy(_tmpMat.current)
    if (reticleRef.current) {
      reticleRef.current.visible = true
      reticleRef.current.position.setFromMatrixPosition(_tmpMat.current)
    }
  }, 'viewer', ['plane', 'mesh'])

  // ── Pointer gesture handler (drag = Y-rotate, two-finger pinch = scale) ──
  const pointerMap = useRef(new Map<number, { x: number; y: number }>())

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId)
    pointerMap.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
  }

  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    const prev = pointerMap.current.get(e.pointerId)
    if (!prev) return
    const pts = [...pointerMap.current.entries()]

    if (pts.length === 1) {
      // Single pointer → rotate around Y
      userRotYRef.current += (e.clientX - prev.x) * 0.01
    } else if (pts.length >= 2) {
      // Two pointers → pinch-to-scale
      const other = pts.find(([id]) => id !== e.pointerId)
      if (other) {
        const [, o] = other
        const curDist  = Math.hypot(e.clientX - o.x, e.clientY - o.y)
        const prevDist = Math.hypot(prev.x   - o.x, prev.y   - o.y)
        if (prevDist > 0) {
          userScaleRef.current = Math.max(0.1, Math.min(5, userScaleRef.current * (curDist / prevDist)))
        }
      }
    }
    pointerMap.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
  }

  const onPointerUp = (e: PointerEvent<HTMLDivElement>) => {
    e.currentTarget.releasePointerCapture(e.pointerId)
    pointerMap.current.delete(e.pointerId)
  }

  const confirmPlacement = () => {
    if (!hasHitRef.current) return   // nothing detected yet — do nothing
    onConfirmPlacement()
  }

  return (
    <>
      {/* Lighting */}
      <ambientLight intensity={0.8} />
      <directionalLight position={[5, 10, 5]} intensity={1.5} castShadow />
      <directionalLight position={[-4, 4, -5]} intensity={0.4} />

      {/* Placement reticle — ring on the ARCore-detected surface */}
      <mesh ref={reticleRef} visible={false} rotation-x={-Math.PI / 2} renderOrder={1}>
        <ringGeometry args={[0.18, 0.24, 48]} />
        <meshBasicMaterial
          color="#FFAA6E"
          transparent
          opacity={0.9}
          side={THREE.DoubleSide}
        />
      </mesh>

      {/* GLB car model */}
      <Suspense fallback={null}>
        <CarModel
          key={url}
          url={url}
          modeRef={modeRef}
          hitMatrixRef={hitMatrixRef}
          hasHitRef={hasHitRef}
          userScaleRef={userScaleRef}
          userRotationYRef={userRotYRef}
        />
      </Suspense>

      {/* ─── HTML overlay (visible on top of AR via dom-overlay feature) ────── */}
      {/* The root div has pointer-events:none so it doesn't block AR input.   */}
      {/* Children opt back in with pointer-events:auto selectively.           */}
      <XRDomOverlay style={{ position: 'fixed', inset: 0, pointerEvents: 'none' }}>

        {/* Full-screen gesture capture.  Placed first (lowest z-index) so   */}
        {/* buttons rendered after it sit visually on top and receive clicks. */}
        <div
          style={{ position: 'absolute', inset: 0, zIndex: 1, pointerEvents: 'auto' }}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
        />

        {/* Context hint */}
        <span style={arHint}>
          {mode === 'placement'
            ? 'POINT AT THE GROUND  ·  DRAG TO ROTATE  ·  PINCH TO RESIZE'
            : 'DRAG TO ROTATE  ·  PINCH TO RESIZE'}
        </span>

        {/* Action button */}
        <div style={arBtnRow}>
          {mode === 'placement' && (
            <button style={{ ...primaryBtn, pointerEvents: 'auto' }} onClick={confirmPlacement}>
              PLACE HERE
            </button>
          )}
          {mode === 'placed' && (
            <button style={{ ...secondaryBtn, pointerEvents: 'auto' }} onClick={onReposition}>
              REPOSITION
            </button>
          )}
        </div>
      </XRDomOverlay>
    </>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

interface ARViewerProps { glbUrl: string | null }

export default function ARViewer({ glbUrl }: ARViewerProps) {
  const [arStatus, setArStatus] = useState<ARStatus>('idle')
  const [mode, setMode]         = useState<PlacementMode>('placement')

  // Probe WebXR AR support once on mount
  useEffect(() => {
    const xrNav = (navigator as { xr?: { isSessionSupported: (t: string) => Promise<boolean> } }).xr
    if (!xrNav?.isSessionSupported) { setArStatus('unsupported'); return }
    xrNav.isSessionSupported('immersive-ar')
      .then(ok => { if (!ok) setArStatus('unsupported') })
      .catch(() => setArStatus('unsupported'))
  }, [])

  const handleSessionActive = useCallback((active: boolean) => {
    setArStatus(prev => active ? 'active' : prev === 'active' ? 'idle' : prev)
    if (!active) setMode('placement')   // reset placement on session end
  }, [])

  const startAR = async () => {
    setArStatus('requesting')
    setMode('placement')
    try {
      await xrStore.enterAR()
    } catch {
      setArStatus('denied')
    }
  }

  // ── No GLB ────────────────────────────────────────────────────────────────
  if (!glbUrl) {
    return (
      <div style={centered}>
        <span style={{ fontSize: 36, opacity: 0.25 }}>◈</span>
        <span style={hint}>LOAD A GLB FILE TO ENABLE LIVE VIEW</span>
      </div>
    )
  }

  // ── WebXR not available ───────────────────────────────────────────────────
  if (arStatus === 'unsupported') {
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

      <Canvas
        camera={{ fov: 62, near: 0.01, far: 1000 }}
        gl={{ alpha: true, antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
      >
        <XR store={xrStore}>
          <XRSessionSync onActive={handleSessionActive} />
          {glbUrl && (
            <ARScene
              url={glbUrl}
              mode={mode}
              onConfirmPlacement={() => setMode('placed')}
              onReposition={() => setMode('placement')}
            />
          )}
        </XR>
      </Canvas>

      {/* Pre-AR overlays (idle / requesting / denied) */}
      {arStatus === 'idle' && (
        <div style={{ ...centered, position: 'absolute', inset: 0 }}>
          <button style={primaryBtn} onClick={startAR}>START AR</button>
          <span style={hint}>CAMERA ACCESS REQUIRED</span>
        </div>
      )}

      {arStatus === 'requesting' && (
        <div style={{ ...centered, position: 'absolute', inset: 0 }}>
          <span style={{ ...hint, color: 'rgba(255,255,255,0.6)' }}>STARTING AR…</span>
        </div>
      )}

      {arStatus === 'denied' && (
        <div style={{ ...centered, position: 'absolute', inset: 0, gap: 12 }}>
          <span style={{ fontSize: '0.78rem', color: '#D93025', letterSpacing: '0.04em' }}>
            AR UNAVAILABLE
          </span>
          <span style={{ ...hint, textAlign: 'center', maxWidth: 220 }}>
            Allow camera access in your browser settings, then reload the page.
          </span>
          <button style={primaryBtn} onClick={startAR}>TRY AGAIN</button>
        </div>
      )}

    </div>
  )
}

// ─── Shared styles ────────────────────────────────────────────────────────────

const centered: CSSProperties = {
  width: '100%', height: '100%',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  flexDirection: 'column', gap: 14,
}

const hint: CSSProperties = {
  fontSize: '0.62rem',
  color: 'rgba(255,255,255,0.38)',
  letterSpacing: '0.08em',
}

const primaryBtn: CSSProperties = {
  background: '#FFAA6E', color: '#1a0e00',
  border: 'none', borderRadius: 100,
  padding: '12px 28px',
  fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.06em',
  cursor: 'pointer', WebkitTapHighlightColor: 'transparent',
}

const secondaryBtn: CSSProperties = {
  background: 'rgba(255,255,255,0.15)',
  color: 'rgba(255,255,255,0.9)',
  border: '1px solid rgba(255,255,255,0.3)',
  borderRadius: 100,
  padding: '12px 28px',
  fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.06em',
  cursor: 'pointer', WebkitTapHighlightColor: 'transparent',
}

// Styles used inside XRDomOverlay (plain objects, not CSSProperties — applied via style prop)
const arHint: CSSProperties = {
  position: 'absolute',
  top: 24, left: 0, right: 0,
  textAlign: 'center',
  fontSize: '0.55rem',
  color: 'rgba(255,255,255,0.75)',
  letterSpacing: '0.08em',
  pointerEvents: 'none',
  zIndex: 10,
}

const arBtnRow: CSSProperties = {
  position: 'absolute',
  bottom: 40, left: 0, right: 0,
  display: 'flex', justifyContent: 'center', gap: 12,
  pointerEvents: 'none',
  zIndex: 10,
}
