import type { Screen } from '../types'
import styles from './AppHeader.module.css'

const badgeLabels: Record<Screen, string> = {
  home: 'HOME',
  scan: 'SCAN',
  model: '3D',
  reports: 'REPORTS',
}

interface AppHeaderProps {
  screen: Screen
}

function AppHeader({ screen }: AppHeaderProps) {
  return (
    <header className={styles.header}>
      <div className={styles.logo}>
        Space<span>frame</span>
      </div>
      <div className={styles.badge}>
        {badgeLabels[screen]}
      </div>
    </header>
  )
}

export default AppHeader
