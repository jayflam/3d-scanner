import type { ComponentType, CSSProperties, ReactNode } from 'react'

// model-viewer is loaded as a web component via CDN script in index.html.
// This cast lets TypeScript accept it as a valid JSX element.
const ModelViewerEl = 'model-viewer' as unknown as ComponentType<{
  src?: string
  alt?: string
  ar?: string
  'ar-modes'?: string
  'ar-scale'?: string
  'camera-controls'?: string
  'shadow-intensity'?: string
  'environment-image'?: string
  exposure?: string
  style?: CSSProperties
  children?: ReactNode
}>

interface ARViewerProps {
  glbUrl: string | null
}

function ARViewer({ glbUrl }: ARViewerProps) {
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
        fontSize: '0.7rem',
        letterSpacing: '0.08em',
      }}>
        <span style={{ fontSize: '40px', opacity: 0.3 }}>◈</span>
        NO MODEL LOADED
      </div>
    )
  }

  return (
    <ModelViewerEl
      src={glbUrl}
      alt="Vehicle AR view"
      ar=""
      ar-modes="webxr scene-viewer quick-look"
      ar-scale="fixed"
      camera-controls=""
      shadow-intensity="1"
      environment-image="neutral"
      style={{
        width: '100%',
        height: '100%',
        backgroundColor: 'transparent',
      }}
    >
      {/* Custom AR button styled to match app theme */}
      <button
        slot="ar-button"
        style={{
          position: 'absolute',
          bottom: '14px',
          left: '50%',
          transform: 'translateX(-50%)',
          background: '#FFAA6E',
          color: '#1a0e00',
          border: 'none',
          borderRadius: '100px',
          padding: '10px 22px',
          fontSize: '0.68rem',
          fontWeight: 700,
          letterSpacing: '0.06em',
          cursor: 'pointer',
          whiteSpace: 'nowrap',
          WebkitTapHighlightColor: 'transparent',
        }}
      >
        VIEW IN AR
      </button>
    </ModelViewerEl>
  )
}

export default ARViewer
