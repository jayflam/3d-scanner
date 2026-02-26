import { useState } from 'react'
import type { Screen } from './types'
import bannerMobile from './assets/banner_mobile.png'
import bannerWeb from './assets/banner_web.png'
import Navigation from './components/Navigation'
import HomeScreen from './components/HomeScreen'
import ScanScreen from './components/ScanScreen'
import ModelScreen from './components/ModelScreen'
import ReportsScreen from './components/ReportsScreen'
import styles from './App.module.css'

function App() {
  const [screen, setScreen] = useState<Screen>('home')
  const [menuOpen, setMenuOpen] = useState(false)

  const closeMenu = () => setMenuOpen(false)

  const renderScreen = () => {
    switch (screen) {
      case 'home':    return <HomeScreen onNavigate={setScreen} />
      case 'scan':    return <ScanScreen />
      case 'model':   return <ModelScreen />
      case 'reports': return <ReportsScreen />
    }
  }

  return (
    <div className={styles.app}>

      {/* Top banner — shared across all screens */}
      <div className={styles.banner}>
        <picture>
          <source media="(min-width: 600px)" srcSet={bannerWeb} />
          <img src={bannerMobile} alt="Spaceframe" className={styles.bannerImg} />
        </picture>
        <button
          className={`${styles.hamburger} ${menuOpen ? styles.hamburgerOpen : ''}`}
          onClick={() => setMenuOpen(o => !o)}
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
        >
          <span />
          <span />
          <span />
        </button>
      </div>

      <main className={styles.main}>
        {renderScreen()}
      </main>

      <Navigation current={screen} onChange={setScreen} />

      {/* Hamburger slide-in menu */}
      {menuOpen && (
        <div className={styles.menuOverlay} onClick={closeMenu}>
          <nav className={styles.menuPanel} onClick={e => e.stopPropagation()}>
            <button className={styles.menuClose} onClick={closeMenu} aria-label="Close menu">
              <span />
              <span />
            </button>
            {(
              [
                { label: 'Home',     screen: 'home'    },
                { label: 'Scan',     screen: 'scan'    },
                { label: '3D Model', screen: 'model'   },
                { label: 'Reports',  screen: 'reports' },
              ] as { label: string; screen: Screen }[]
            ).map(item => (
              <button
                key={item.screen}
                className={styles.menuItem}
                onClick={() => { setScreen(item.screen); closeMenu() }}
              >
                {item.label}
              </button>
            ))}
          </nav>
        </div>
      )}

    </div>
  )
}

export default App
