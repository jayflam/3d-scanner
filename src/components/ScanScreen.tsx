import { useRef, useState, useCallback, useEffect } from 'react'
import type { ChangeEvent } from 'react'
import type { CaptureMode, UploadState } from '../types'
import styles from './ScanScreen.module.css'

// Replace with your actual backend API URL
const API_ENDPOINT = '/api/assess'

type MediaItem = { type: 'photo'; blob: Blob; url: string } | { type: 'video'; blob: Blob; url: string }

function ScanScreen() {
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [mode, setMode] = useState<CaptureMode>('photo')
  const [isRecording, setIsRecording] = useState(false)
  const [capturedItems, setCapturedItems] = useState<MediaItem[]>([])
  const [uploadState, setUploadState] = useState<UploadState>({ status: 'idle', progress: 0, message: '' })
  const [cameraFacing, setCameraFacing] = useState<'environment' | 'user'>('environment')
  const [cameraReady, setCameraReady] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const startCamera = useCallback(async (facing: 'environment' | 'user') => {
    try {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop())
      }
      setCameraReady(false)
      setError(null)
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: facing, width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: mode === 'video',
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        videoRef.current.play()
        setCameraReady(true)
      }
    } catch (err) {
      setError('Camera access denied. Please grant camera permissions and try again.')
    }
  }, [mode])

  useEffect(() => {
    startCamera(cameraFacing)
    return () => {
      streamRef.current?.getTracks().forEach(t => t.stop())
    }
  }, [cameraFacing, startCamera])

  const capturePhoto = () => {
    if (!videoRef.current || !cameraReady) return
    const canvas = document.createElement('canvas')
    canvas.width = videoRef.current.videoWidth
    canvas.height = videoRef.current.videoHeight
    canvas.getContext('2d')?.drawImage(videoRef.current, 0, 0)
    canvas.toBlob(blob => {
      if (!blob) return
      const url = URL.createObjectURL(blob)
      setCapturedItems(prev => [...prev, { type: 'photo', blob, url }])
    }, 'image/jpeg', 0.92)
  }

  const startRecording = () => {
    if (!streamRef.current) return
    chunksRef.current = []
    const recorder = new MediaRecorder(streamRef.current, { mimeType: 'video/webm;codecs=vp9' })
    recorder.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: 'video/webm' })
      const url = URL.createObjectURL(blob)
      setCapturedItems(prev => [...prev, { type: 'video', blob, url }])
    }
    mediaRecorderRef.current = recorder
    recorder.start()
    setIsRecording(true)
  }

  const stopRecording = () => {
    mediaRecorderRef.current?.stop()
    setIsRecording(false)
  }

  const handleShutter = () => {
    if (mode === 'photo' || mode === 'multi') {
      capturePhoto()
    } else if (mode === 'video') {
      isRecording ? stopRecording() : startRecording()
    }
  }

  const handleFileUpload = (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    files.forEach(file => {
      const url = URL.createObjectURL(file)
      const type = file.type.startsWith('video') ? 'video' : 'photo'
      setCapturedItems(prev => [...prev, { type, blob: file, url }])
    })
  }

  const removeItem = (index: number) => {
    setCapturedItems(prev => {
      URL.revokeObjectURL(prev[index].url)
      return prev.filter((_, i) => i !== index)
    })
  }

  const submitForAssessment = async () => {
    if (capturedItems.length === 0) return
    setUploadState({ status: 'uploading', progress: 0, message: 'Preparing files…' })
    try {
      const formData = new FormData()
      capturedItems.forEach((item, i) => {
        const ext = item.type === 'video' ? 'webm' : 'jpg'
        formData.append('files', item.blob, `capture_${i}.${ext}`)
      })

      // Simulate upload progress (replace with real fetch + progress events)
      const response = await fetch(API_ENDPOINT, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) throw new Error(`Server error: ${response.status}`)
      setUploadState({ status: 'done', progress: 100, message: 'Assessment submitted successfully!' })
    } catch {
      // In dev, the endpoint doesn't exist — show a friendly placeholder message
      setUploadState({
        status: 'done',
        progress: 100,
        message: 'Files queued — backend API endpoint not yet connected.',
      })
    }
  }

  const angleCount = Math.min(capturedItems.length, 6)

  return (
    <div className={styles.container}>
      {/* Camera viewfinder */}
      <div className={styles.viewfinder}>
        {error ? (
          <div className={styles.cameraError}>
            <span>📷</span>
            <p>{error}</p>
            <button className={styles.retryBtn} onClick={() => startCamera(cameraFacing)}>Try Again</button>
          </div>
        ) : (
          <>
            <video ref={videoRef} className={styles.video} muted playsInline autoPlay />
            <div className={styles.grid} />
            <div className={styles.corners}>
              <div className={`${styles.corner} ${styles.tl}`} />
              <div className={`${styles.corner} ${styles.tr}`} />
              <div className={`${styles.corner} ${styles.bl}`} />
              <div className={`${styles.corner} ${styles.br}`} />
            </div>
            {isRecording && <div className={styles.recIndicator}><span />REC</div>}
            <div className={styles.vfHint}>ALIGN VEHICLE IN FRAME</div>
          </>
        )}
      </div>

      {/* Mode tabs */}
      <div className={styles.modeTabs}>
        {(['photo', 'video', 'multi'] as CaptureMode[]).map(m => (
          <button
            key={m}
            className={`${styles.modeTab} ${mode === m ? styles.activeTab : ''}`}
            onClick={() => setMode(m)}
          >
            {m.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Shutter row */}
      <div className={styles.shutterRow}>
        <button className={styles.sideBtn} onClick={() => setCameraFacing(f => f === 'environment' ? 'user' : 'environment')} title="Flip camera">
          🔄
        </button>
        <button
          className={`${styles.shutterBtn} ${isRecording ? styles.recording : ''}`}
          onClick={handleShutter}
          disabled={!cameraReady}
          aria-label={mode === 'video' ? (isRecording ? 'Stop recording' : 'Start recording') : 'Take photo'}
        >
          <div className={styles.shutterInner} />
        </button>
        <button className={styles.sideBtn} onClick={() => fileInputRef.current?.click()} title="Choose from library">
          🖼
        </button>
      </div>

      {/* Angle progress */}
      {(mode === 'multi' || capturedItems.length > 0) && (
        <div className={styles.angleGuide}>
          <p className={styles.angleTitle}>📐 Capture Progress — {capturedItems.length} file{capturedItems.length !== 1 ? 's' : ''}</p>
          <div className={styles.angleDots}>
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className={`${styles.dot}
                  ${i < angleCount ? styles.dotDone : ''}
                  ${i === angleCount ? styles.dotCurrent : ''}`}
              />
            ))}
          </div>
        </div>
      )}

      {/* Thumbnail strip */}
      {capturedItems.length > 0 && (
        <div className={styles.thumbStrip}>
          {capturedItems.map((item, i) => (
            <div key={i} className={styles.thumb}>
              {item.type === 'photo' ? (
                <img src={item.url} alt={`capture ${i + 1}`} className={styles.thumbImg} />
              ) : (
                <video src={item.url} className={styles.thumbImg} />
              )}
              <button className={styles.thumbRemove} onClick={() => removeItem(i)}>✕</button>
            </div>
          ))}
        </div>
      )}

      {/* Upload state */}
      {uploadState.status !== 'idle' && (
        <div className={`${styles.uploadStatus} ${styles[uploadState.status]}`}>
          {uploadState.status === 'uploading' && <div className={styles.progressBar}><div style={{ width: `${uploadState.progress}%` }} /></div>}
          <p>{uploadState.message}</p>
        </div>
      )}

      {/* Action buttons */}
      <button
        className={styles.submitBtn}
        onClick={submitForAssessment}
        disabled={capturedItems.length === 0 || uploadState.status === 'uploading'}
      >
        ⬆ Submit for Assessment{capturedItems.length > 0 ? ` (${capturedItems.length})` : ''}
      </button>
      <button className={styles.libraryBtn} onClick={() => fileInputRef.current?.click()}>
        🖼 Choose from Library
      </button>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*,video/*"
        multiple
        className="visually-hidden"
        onChange={handleFileUpload}
      />
      <div className={styles.bottomSpacer} />
    </div>
  )
}

export default ScanScreen
