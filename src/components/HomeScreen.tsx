import { useState, useEffect } from 'react'
import bannerMobile from '../assets/banner_mobile.png'
import bannerWeb from '../assets/banner_web.png'
import type { Screen } from '../types'
import styles from './HomeScreen.module.css'

interface HomeScreenProps {
  onNavigate: (screen: Screen) => void
}

/** Returns true when the viewport is wider than 768 px (desktop). Updates live on resize. */
function useIsDesktop(): boolean {
  const [isDesktop, setIsDesktop] = useState(
    () => window.matchMedia('(min-width: 768px)').matches
  )
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 768px)')
    const handler = (e: MediaQueryListEvent) => setIsDesktop(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])
  return isDesktop
}

const steps: { title: string; desc: string }[] = [
  {
    title: 'Scan Your Car',
    desc: 'Use the Scan tab to capture photos or video of your vehicle from multiple angles. The more coverage, the more accurate the assessment.',
  },
  {
    title: 'Upload Files for Assessment',
    desc: 'Submit your captured media to our AI engine. It analyzes every panel, surface, and edge for signs of damage, dents, and paint defects.',
  },
  {
    title: 'Receive Your Damage Report',
    desc: 'Get a full damage breakdown with severity ratings and a navigable 3D model of your vehicle — available any time in the Reports tab.',
  },
]

function HomeScreen({ onNavigate }: HomeScreenProps) {
  const isDesktop = useIsDesktop()
  const [menuOpen, setMenuOpen] = useState(false)

  const closeMenu = () => setMenuOpen(false)

  return (
    <div className={`${styles.container} ${isDesktop ? styles.desktop : ''}`}>

      {/* Top banner */}
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

      {/* Scrollable content */}
      <div className={styles.content}>

        {/* — Section 1: Welcome ——————————————————————————————— */}
        <section className={styles.welcomeSection}>
          <h1 className={styles.welcomeTitle}>Welcome to Spaceframe</h1>
          <p className={styles.welcomeTag}>AI-POWERED VEHICLE ASSESSMENT</p>
          <p className={styles.welcomeDesc}>
            Spaceframe uses artificial intelligence to assess damage on your vehicle.
            Simply scan your car with your phone, upload the images, and our AI engine
            analyzes every panel for dents, scratches, and structural damage — then
            generates an interactive 3D model you can review any time.
          </p>
          <button
            className={styles.ctaButton}
            onClick={() => onNavigate('scan')}
          >
            Start Scanning
          </button>
        </section>

        {/* — Section 2: How it works ——————————————————————————— */}
        <section className={styles.stepsSection}>
          <p className={styles.stepsHeading}>How It Works</p>
          <ol className={styles.stepsList}>
            {steps.map((step, i) => (
              <li key={i} className={styles.step}>
                <span className={`${styles.stepNumber} ${styles[`stepNum${i + 1}` as keyof typeof styles]}`}>
                  {i + 1}
                </span>
                <div className={styles.stepBody}>
                  <p className={styles.stepTitle}>{step.title}</p>
                  <p className={styles.stepDesc}>{step.desc}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

      </div>

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
                onClick={() => { onNavigate(item.screen); closeMenu() }}
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

export default HomeScreen
