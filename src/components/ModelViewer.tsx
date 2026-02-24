import { Suspense, useRef, useEffect } from 'react'
import { Canvas, useThree } from '@react-three/fiber'
import {
  OrbitControls,
  useGLTF,
  Environment,
  Center,
  ContactShadows,
  Html,
  useProgress,
} from '@react-three/drei'
import * as THREE from 'three'

interface ModelProps {
  url: string
}

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

function CameraFit({ url }: { url: string }) {
  const { scene } = useGLTF(url)
  const { camera } = useThree()

  useEffect(() => {
    const box = new THREE.Box3().setFromObject(scene)
    const size = box.getSize(new THREE.Vector3())
    const maxDim = Math.max(size.x, size.y, size.z)
    if (camera instanceof THREE.PerspectiveCamera) {
      camera.fov = 45
      const fovRad = (camera.fov * Math.PI) / 180
      let dist = (maxDim / 2) / Math.tan(fovRad / 2)
      dist *= 1.5
      const center = box.getCenter(new THREE.Vector3())
      camera.position.set(center.x + dist * 0.7, center.y + dist * 0.4, center.z + dist)
      camera.lookAt(center)
      camera.near = dist / 100
      camera.far = dist * 100
      camera.updateProjectionMatrix()
    }
  }, [scene, camera])

  return null
}

function Model({ url }: ModelProps) {
  const { scene } = useGLTF(url)
  const ref = useRef<THREE.Group>(null)

  return (
    <>
      <CameraFit url={url} />
      <Center>
        <primitive ref={ref} object={scene} />
      </Center>
    </>
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
        <Model url={glbUrl} />
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

      <OrbitControls
        enablePan
        enableZoom
        enableRotate
        minDistance={0.5}
        maxDistance={200}
        target={[0, 0, 0]}
        makeDefault
      />
    </Canvas>
  )
}

export default ModelViewer
