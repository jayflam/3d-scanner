import { useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import ARViewer from './ARViewer'
import type { AssessmentResult, DamageSeverity } from '../types'
import styles from './ModelScreen.module.css'

// Mock data — replace with real API response
const MOCK_ASSESSMENT: AssessmentResult = {
  id: 'assess-001',
  vehicleName: 'Toyota Camry 2022',
  analyzedAt: '2 minutes ago',
  overallSeverity: 'high',
  summary:
    'Significant rear impact damage with structural deformation to the lower bumper fascia. The driver-side door exhibits surface-level scratches and minor creasing. The front wing shows multiple stone chips and paint abrasion. Overall repair scope is estimated as moderate to high.',
  zones: [
    { id: 'z1', name: 'Rear Bumper', severity: 'high',   description: 'Deep impact dent with visible paint transfer. Structural deformation detected. Full fascia replacement likely required.' },
    { id: 'z2', name: 'Driver Door', severity: 'medium', description: 'Surface scratches and minor creasing along lower third. Paint repair and possible dent pulling needed.' },
    { id: 'z3', name: 'Front Wing',  severity: 'medium', description: 'Multiple stone chips and paint abrasion across leading edge. Spot repair and refinish recommended.' },
    { id: 'z4', name: 'Roof Panel',  severity: 'clear',  description: 'No visible damage detected across the full roof surface.' },
    { id: 'z5', name: 'Hood',        severity: 'low',    description: 'Minor surface scuffs near the grille — cosmetic only.' },
    { id: 'z6', name: 'Trunk Lid',   severity: 'clear',  description: 'Clean — no damage observed.' },
  ],
}

const severityColors: Record<DamageSeverity, { bg: string; color: string; label: string }> = {
  high:   { bg: '#FEE2E2', color: '#D93025', label: 'HIGH' },
  medium: { bg: '#FEF3C7', color: '#D97706', label: 'MED' },
  low:    { bg: '#FEF9C3', color: '#A16207', label: 'LOW' },
  clear:  { bg: '#D1FAE5', color: '#1A7F52', label: 'CLEAR' },
}

const dotColors: Record<DamageSeverity, string> = {
  high: '#D93025', medium: '#D97706', low: '#A16207', clear: '#1A7F52',
}

function ModelScreen() {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [glbUrl, setGlbUrl] = useState<string | null>(null)
  const [glbName, setGlbName] = useState<string | null>(null)
  const [showAssessment, setShowAssessment] = useState(false)

  const handleGlbSelect = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (glbUrl) URL.revokeObjectURL(glbUrl)
    const url = URL.createObjectURL(file)
    setGlbUrl(url)
    setGlbName(file.name)
    setShowAssessment(true)
  }

  const assessment = showAssessment ? MOCK_ASSESSMENT : null

  return (
    <div className={styles.container}>
      {/* Live View section */}
      <p className={styles.sectionTitle} style={{ paddingTop: '14px' }}>Live View</p>
      <div className={styles.arViewport}>
        <ARViewer glbUrl={glbUrl} />
        {glbName && (
          <div className={styles.viewportOverlay}>
            <span className={styles.overlayBadge}>GLB · {glbName}</span>
            <span className={styles.overlayBadge}>INTERACTIVE</span>
          </div>
        )}
      </div>

      {/* File picker */}
      <button className={styles.filePicker} onClick={() => fileInputRef.current?.click()}>
        <div className={styles.fpIcon}>GLB</div>
        <div className={styles.fpText}>
          <span className={styles.fpMain}>{glbName ?? 'Open GLB File'}</span>
          <span className={styles.fpSub}>{glbName ? 'TAP TO CHANGE FILE' : 'TAP TO BROWSE FILES'}</span>
        </div>
        <span className={styles.fpChevron}>›</span>
      </button>

      <input
        ref={fileInputRef}
        type="file"
        accept=".glb,.gltf"
        className="visually-hidden"
        style={{ display: 'none' }} 
        onChange={handleGlbSelect}
      />

      {/* Assessment panel */}
      {assessment ? (
        <>
          <p className={styles.sectionTitle}>Damage Assessment</p>
          <div className={styles.panel}>
            {/* Panel header */}
            <div className={styles.panelHeader}>
              <div>
                <h3 className={styles.panelVehicle}>{assessment.vehicleName}</h3>
                <p className={styles.panelMeta}>Analyzed {assessment.analyzedAt}</p>
              </div>
              <span
                className={styles.severityBadge}
                style={severityColors[assessment.overallSeverity]}
              >
                {severityColors[assessment.overallSeverity].label}
              </span>
            </div>

            {/* Zones grid */}
            <div className={styles.zonesGrid}>
              {assessment.zones.map(zone => (
                <div key={zone.id} className={styles.zone}>
                  <div className={styles.zoneName}>
                    <span className={styles.zoneDot} style={{ background: dotColors[zone.severity] }} />
                    {zone.name}
                  </div>
                  <p className={styles.zoneDesc}>{zone.description}</p>
                  <span
                    className={styles.zoneBadge}
                    style={severityColors[zone.severity]}
                  >
                    {severityColors[zone.severity].label}
                  </span>
                </div>
              ))}
            </div>

            {/* Summary */}
            <div className={styles.summary}>
              <p className={styles.summaryLabel}>OVERALL ASSESSMENT</p>
              <p className={styles.summaryText}>{assessment.summary}</p>
            </div>
          </div>
        </>
      ) : (
        <div className={styles.noAssessment}>
          <p className={styles.naIcon}>◈</p>
          <p className={styles.naTitle}>No Assessment Yet</p>
          <p className={styles.naSub}>Open a GLB file to view your vehicle in 3D, then submit photos via the Scan tab to generate a damage report.</p>
        </div>
      )}

      <div className={styles.bottomSpacer} />
    </div>
  )
}

export default ModelScreen
