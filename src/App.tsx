import { useState } from 'react'
import type { Screen } from './types'
import AppHeader from './components/AppHeader'
import Navigation from './components/Navigation'
import HomeScreen from './components/HomeScreen'
import ScanScreen from './components/ScanScreen'
import ModelScreen from './components/ModelScreen'
import ReportsScreen from './components/ReportsScreen'
import styles from './App.module.css'

function App() {

  const [screen, setScreen] = useState<Screen>('home')

    const renderScreen = () => {
      switch (screen) {
        case 'home':    return <HomeScreen onNavigate={setScreen} />
        case 'scan':    return <ScanScreen />
        case 'model':   return <ModelScreen />
        case 'reports': return <ReportsScreen />
      }
    }

    return (
      <div className={`${styles.app} ${screen === 'home' ? styles.appHome : ''}`}>
        {screen !== 'home' && <AppHeader screen={screen} />}
        <main className={styles.main}>
          {renderScreen()}
        </main>
        <Navigation current={screen} onChange={setScreen} />
      </div>
    )
}

// const App: React.FC = () => {
//   const [screen, setScreen] = useState<Screen>('home')

//   const renderScreen = () => {
//     switch (screen) {
//       case 'home':    return <HomeScreen onNavigate={setScreen} />
//       case 'scan':    return <ScanScreen />
//       case 'model':   return <ModelScreen />
//       case 'reports': return <ReportsScreen />
//     }
//   }

//   return (
//     <div className={styles.app}>
//       <AppHeader screen={screen} />
//       <main className={styles.main}>
//         {renderScreen()}
//       </main>
//       <Navigation current={screen} onChange={setScreen} />
//     </div>
//   )
// }

export default App