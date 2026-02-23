import React from 'react'
import styles from './ReportsScreen.module.css'

const ReportsScreen: React.FC = () => {
  return (
    <div className={styles.container}>
      <div className={styles.empty}>
        <span className={styles.icon}>≡</span>
        <h2>Reports</h2>
        <p>Completed assessments will appear here once your backend service returns results.</p>
      </div>
    </div>
  )
}

export default ReportsScreen
