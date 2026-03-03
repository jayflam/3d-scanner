import { Suspense, useRef } from "react";
import { Canvas } from "@react-three/fiber";
import { useGLTF, OrbitControls, Environment, Center, Html } from "@react-three/drei";
import { Group } from "three";

// ─── Model Component ────────────────────────────────────────────────────────

interface ModelProps {
  url: string;
}

function Model({ url }: ModelProps) {
  const groupRef = useRef<Group>(null);
  const { scene } = useGLTF(url);

  return (
    <Center>
      <primitive ref={groupRef} object={scene} />
    </Center>
  );
}

// ─── Loading Fallback ────────────────────────────────────────────────────────

function Loader() {
  return (
    <Html center>
      <div style={{ color: "white", fontSize: "1rem", fontFamily: "sans-serif" }}>
        Loading model...
      </div>
    </Html>
  );
}

// ─── Scene ───────────────────────────────────────────────────────────────────

interface SceneProps {
  modelUrl: string;
}

function Scene({ modelUrl }: SceneProps) {
  return (
    <>
      {/* Lighting */}
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 10, 7.5]} intensity={1.5} castShadow />
      <pointLight position={[-10, -10, -10]} intensity={0.5} />

      {/* Environment map for realistic reflections */}
      <Environment preset="city" />

      {/* The 3D model */}
      <Suspense fallback={<Loader />}>
        <Model url={modelUrl} />
      </Suspense>

      {/* Camera controls: orbit, zoom, pan */}
      <OrbitControls
        enablePan
        enableZoom
        enableRotate
        autoRotate
        autoRotateSpeed={1.5}
        minDistance={1}
        maxDistance={50}
      />
    </>
  );
}

// ─── ModelViewer ─────────────────────────────────────────────────────────────

interface ModelViewerProps {
  /** Path or URL to your .glb file, e.g. "/models/robot.glb" */
  modelUrl: string;
  /** Canvas width  (default: "100%") */
  width?: string | number;
  /** Canvas height (default: "100vh") */
  height?: string | number;
  /** Background colour (default: "#1a1a2e") */
  background?: string;
}

export default function ModelViewer({
  modelUrl,
  width = "100%",
  height = "100vh",
  background = "#1a1a2e",
}: ModelViewerProps) {
  return (
    <div style={{ width, height, background }}>
      <Canvas
        shadows
        camera={{ position: [0, 2, 5], fov: 45, near: 0.1, far: 1000 }}
        gl={{ antialias: true }}
      >
        <color attach="background" args={[background]} />
        <Scene modelUrl={modelUrl} />
      </Canvas>
    </div>
  );
}

// ─── Usage Example ────────────────────────────────────────────────────────────
//
// In your App.tsx (or any page):
//
//   import ModelViewer from "./ModelViewer";
//
//   export default function App() {
//     return (
//       <ModelViewer
//         modelUrl="/models/your-model.glb"   // place the .glb in /public/models/
//         height="100vh"
//         background="#0f0f1a"
//       />
//     );
//   }
//
// ─── Required packages ────────────────────────────────────────────────────────
//
//   npm install three @react-three/fiber @react-three/drei
//   npm install -D @types/three
