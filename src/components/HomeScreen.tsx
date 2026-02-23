import React from 'react'
import type { Screen, RecentAssessment } from '../types'
import styles from './HomeScreen.module.css'

interface HomeScreenProps {
  onNavigate: (screen: Screen) => void
}

const MOCK_RECENT: RecentAssessment[] = [
  {
    id: '1',
    vehicleName: 'Toyota Camry 2022',
    subtitle: 'REAR BUMPER · 4 PHOTOS',
    status: 'done',
    timestamp: '2 hours ago',
  },
  {
    id: '2',
    vehicleName: 'Honda CR-V 2021',
    subtitle: 'DOOR PANEL · 2 VIDEOS',
    status: 'processing',
    timestamp: '15 min ago',
  },
]

const quickActions: { icon: string; title: string; desc: string; screen: Screen; primary?: boolean }[] = [
  { icon: '📷', title: 'Take Photo',    desc: 'Capture with your camera',   screen: 'scan',   primary: true },
  { icon: '🎥', title: 'Record Video',  desc: 'Walk-around inspection mode', screen: 'scan' },
  { icon: '📤', title: 'Upload File',   desc: 'From your photo library',     screen: 'scan' },
  { icon: '◈',  title: 'View 3D Model', desc: 'Open a GLB model file',       screen: 'model' },
]

const HomeScreen: React.FC<HomeScreenProps> = ({ onNavigate }) => {
  return (
    <div className={styles.container}>
      {/* Hero */}
      <div className={styles.hero}>
        <div className={styles.heroIcon}>🚗</div>
        <h2 className={styles.heroTitle}>Scan Your Vehicle</h2>
        <p className={styles.heroSub}>TAP BELOW TO BEGIN</p>
      </div>

      {/* Quick actions */}
      <div className={styles.actionGrid}>
        {quickActions.map(action => (
          <button
            key={action.title}
            className={`${styles.actionCard} ${action.primary ? styles.primary : ''}`}
            onClick={() => onNavigate(action.screen)}
          >
            <span className={styles.cardIcon}>{action.icon}</span>
            <span className={styles.cardTitle}>{action.title}</span>
            <span className={styles.cardDesc}>{action.desc}</span>
          </button>
        ))}
      </div>

      {/* Recent */}
      <p className={styles.sectionTitle}>Recent Assessments</p>
      {MOCK_RECENT.map(item => (
        <div key={item.id} className={styles.recentItem}>
          <div className={styles.recentThumb}>🚗</div>
          <div className={styles.recentInfo}>
            <p className={styles.recentTitle}>{item.vehicleName}</p>
            <p className={styles.recentSub}>{item.subtitle}</p>
          </div>
          <span className={`${styles.pill} ${styles[item.status]}`}>
            {item.status === 'done' ? 'Done' : item.status === 'processing' ? 'Processing' : 'Failed'}
          </span>
        </div>
      ))}
      <div className={styles.bottomSpacer} />
    </div>
  )
}

export default HomeScreen
