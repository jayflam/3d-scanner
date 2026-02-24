import type { Screen } from '../types'
import styles from './Navigation.module.css'

interface NavigationProps {
  current: Screen
  onChange: (screen: Screen) => void
}

const navItems: { id: Screen; icon: string; label: string }[] = [
  { id: 'home',    icon: '⌂',  label: 'HOME' },
  { id: 'scan',    icon: '◉',  label: 'SCAN' },
  { id: 'model',   icon: '◈',  label: 'MODEL' },
  { id: 'reports', icon: '≡',  label: 'REPORTS' },
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
