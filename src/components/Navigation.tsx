import type { ReactNode } from 'react'
import type { Screen } from '../types'
import styles from './Navigation.module.css'

interface NavigationProps {
  current: Screen
  onChange: (screen: Screen) => void
}

const HomeIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 12L12 4l9 8" />
    <path d="M5 10v9a1 1 0 001 1h4v-5h4v5h4a1 1 0 001-1v-9" />
  </svg>
)

const ScanIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14.5 4l1.5 2h3a1 1 0 011 1v11a1 1 0 01-1 1H5a1 1 0 01-1-1V7a1 1 0 011-1h3L9.5 4h5z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
)

const ModelIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2l9 4.9v10L12 22 3 16.9V7L12 2z" />
    <path d="M12 22V12" />
    <path d="M21 7l-9 5-9-5" />
  </svg>
)

const ReportsIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z" />
    <path d="M14 2v6h6" />
    <path d="M8 13h8M8 17h5" />
  </svg>
)

const navItems: { id: Screen; icon: ReactNode; label: string }[] = [
  { id: 'home',    icon: <HomeIcon />,    label: 'HOME'    },
  { id: 'scan',    icon: <ScanIcon />,    label: 'SCAN'    },
  { id: 'model',   icon: <ModelIcon />,   label: 'MODEL'   },
  { id: 'reports', icon: <ReportsIcon />, label: 'REPORTS' },
]

function Navigation({ current, onChange }: NavigationProps) {
  return (
    <nav className={styles.nav}>
      {navItems.map(item => (
        <button
          key={item.id}
          className={`${styles.item} ${current === item.id ? styles.active : ''}`}
          onClick={() => onChange(item.id)}
          aria-label={item.label}
        >
          <span className={styles.icon}>{item.icon}</span>
          <span className={styles.label}>{item.label}</span>
        </button>
      ))}
    </nav>
  )
}

export default Navigation
