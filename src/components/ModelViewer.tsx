import { Suspense, useRef, useEffect } from 'react'
import { Canvas, useThree, useFrame } from '@react-three/fiber'
import { useGLTF, Environment, ContactShadows, Html, useProgress } from '@react-three/drei'
import * as THREE from 'three'

function Loader() {
  const { progress } = useProgress()
  return (
    <Html center>
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '12px',
        color: 'rgba(255,255,255,0.7)',
        fontFamily: 'DM Mono, monospace',
        fontSize: '0.7rem',
        letterSpacing: '0.08em',
        userSelect: 'none',
      }}>
        <div style={{
          width: '120px',
          height: '3px',
          background: 'rgba(255,255,255,0.1)',
          borderRadius: '2px',
          overflow: 'hidden',
        }}>
          <div style={{
            width: `${progress}%`,
            height: '100%',
            background: 'white',
            borderRadius: '2px',
            transition: 'width 0.3s',
          }} />
        </div>
        LOADING MODEL {Math.round(progress)}%
      </div>
    </Html>
  )
}

function ModelWithInteraction({ url }: { url: string }) {
  const { scene } = useGLTF(url)
  const groupRef = useRef<THREE.Group>(null)
  const { gl, camera } = useThree()

  const isDragging = useRef(false)
  const lastPointer = useRef({ x: 0, y: 0 })
  const lastPinchDist = useRef<number | null>(null)
  const rotX = useRef(0)
  const rotY = useRef(0)
  const modelScale = useRef(1)

  // Center model at world origin and lock camera — runs once per loaded scene
  useEffect(() => {
    const box = new THREE.Box3().setFromObject(scene)
    const center = box.getCenter(new THREE.Vector3())
    const size = box.getSize(new THREE.Vector3())

    // Shift the scene so its geometric center sits at (0,0,0)
    scene.position.sub(center)

    const maxDim = Math.max(size.x, size.y, size.z)
    if (camera instanceof THREE.PerspectiveCamera) {
      camera.fov = 45
      camera.updateProjectionMatrix()
      const fovRad = (camera.fov * Math.PI) / 180
      const dist = ((maxDim / 2) / Math.tan(fovRad / 2)) * 1.5
      camera.position.set(dist * 0.7, dist * 0.4, dist)
      camera.lookAt(0, 0, 0)
      camera.near = dist / 100
      camera.far = dist * 100
      camera.updateProjectionMatrix()
    }
  }, [scene, camera])

  // Pointer + touch interaction — mutates refs, no re-renders
  useEffect(() => {
    const canvas = gl.domElement

    const onMouseDown = (e: MouseEvent) => {
      isDragging.current = true
      lastPointer.current = { x: e.clientX, y: e.clientY }
    }
    const onMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) return
      rotY.current += (e.clientX - lastPointer.current.x) * 0.008
      rotX.current += (e.clientY - lastPointer.current.y) * 0.008
      lastPointer.current = { x: e.clientX, y: e.clientY }
    }
    const onMouseUp = () => { isDragging.current = false }

    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      modelScale.current = Math.max(0.05, Math.min(20, modelScale.current * (e.deltaY > 0 ? 0.93 : 1.07)))
    }

    const onTouchStart = (e: TouchEvent) => {
      if (e.touches.length === 1) {
        isDragging.current = true
        lastPointer.current = { x: e.touches[0].clientX, y: e.touches[0].clientY }
        lastPinchDist.current = null
      } else if (e.touches.length === 2) {
        isDragging.current = false
        lastPinchDist.current = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY,
        )
      }
    }
    const onTouchMove = (e: TouchEvent) => {
      e.preventDefault()
      if (e.touches.length === 1 && isDragging.current) {
        rotY.current += (e.touches[0].clientX - lastPointer.current.x) * 0.008
        rotX.current += (e.touches[0].clientY - lastPointer.current.y) * 0.008
        lastPointer.current = { x: e.touches[0].clientX, y: e.touches[0].clientY }
      } else if (e.touches.length === 2 && lastPinchDist.current !== null) {
        const dist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY,
        )
        modelScale.current = Math.max(0.05, Math.min(20, modelScale.current * (dist / lastPinchDist.current)))
        lastPinchDist.current = dist
      }
    }
    const onTouchEnd = (e: TouchEvent) => {
      if (e.touches.length === 0) {
        isDragging.current = false
        lastPinchDist.current = null
      } else if (e.touches.length === 1) {
        lastPinchDist.current = null
        isDragging.current = true
        lastPointer.current = { x: e.touches[0].clientX, y: e.touches[0].clientY }
      }
    }

    canvas.addEventListener('mousedown', onMouseDown)
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    canvas.addEventListener('wheel', onWheel, { passive: false })
    canvas.addEventListener('touchstart', onTouchStart, { passive: false })
    canvas.addEventListener('touchmove', onTouchMove, { passive: false })
    canvas.addEventListener('touchend', onTouchEnd)

    return () => {
      canvas.removeEventListener('mousedown', onMouseDown)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
      canvas.removeEventListener('wheel', onWheel)
      canvas.removeEventListener('touchstart', onTouchStart)
      canvas.removeEventListener('touchmove', onTouchMove)
      canvas.removeEventListener('touchend', onTouchEnd)
    }
  }, [gl])

  useFrame(() => {
    if (!groupRef.current) return
    groupRef.current.rotation.x = rotX.current
    groupRef.current.rotation.y = rotY.current
    groupRef.current.scale.setScalar(modelScale.current)
  })

  return (
    <group ref={groupRef}>
      <primitive object={scene} />
    </group>
  )
}

interface ModelViewerProps {
  glbUrl: string | null
}

function ModelViewer({ glbUrl }: ModelViewerProps) {
  if (!glbUrl) {
    return (
      <div style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        gap: '12px',
        color: 'rgba(255,255,255,0.4)',
        fontFamily: 'DM Mono, monospace',
        fontSize: '0.7rem',
        letterSpacing: '0.08em',
      }}>
        <span style={{ fontSize: '40px', opacity: 0.3 }}>◈</span>
        NO MODEL LOADED
      </div>
    )
  }

  return (
    <Canvas
      shadows
      dpr={[1, 2]}
      gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}
      style={{ width: '100%', height: '100%' }}
    >
      <ambientLight intensity={0.4} />
      <directionalLight position={[5, 8, 5]} intensity={1.2} castShadow />
      <directionalLight position={[-5, 3, -5]} intensity={0.4} />

      <Suspense fallback={<Loader />}>
        <ModelWithInteraction url={glbUrl} />
        <Environment preset="city" />
        <ContactShadows
          position={[0, -0.5, 0]}
          opacity={0.4}
          scale={12}
          blur={2.5}
          far={4}
          color="#000000"
        />
      </Suspense>
    </Canvas>
  )
}

export default ModelViewer
