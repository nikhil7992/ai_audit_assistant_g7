import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard   from './pages/Dashboard'
import Upload      from './pages/Upload'
import Reports     from './pages/Reports'
import ReportDetail from './pages/ReportDetail'
import Validate    from './pages/Validate'
import Scenarios   from './pages/Scenarios'
import PolicySearch from './pages/PolicySearch'
import Admin       from './pages/Admin'
import styles      from './App.module.css'

function Nav() {
  const links = [
    { to: '/',          label: '📊 Dashboard'     },
    { to: '/upload',    label: '📤 Upload & Audit' },
    { to: '/reports',   label: '📋 Reports'        },
    { to: '/validate',  label: '✅ Validate'       },
    { to: '/scenarios', label: '🧪 Scenarios'      },
    { to: '/policies',  label: '🔍 Policy Search'  },
    { to: '/admin',     label: '⚙️ Admin'           },
  ]
  return (
    <nav className={styles.nav}>
      <div className={styles.brand}>
        <span className={styles.brandIcon}>🏢</span>
        <span>Expense Audit</span>
      </div>
      <ul className={styles.navList}>
        {links.map(l => (
          <li key={l.to}>
            <NavLink
              to={l.to}
              end={l.to === '/'}
              className={({ isActive }) =>
                `${styles.navLink} ${isActive ? styles.navActive : ''}`
              }
            >
              {l.label}
            </NavLink>
          </li>
        ))}
      </ul>
      <div className={styles.navFooter}>RetailCorp Inc.</div>
    </nav>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className={styles.shell}>
        <Nav />
        <main className={styles.main}>
          <Routes>
            <Route path="/"            element={<Dashboard />}    />
            <Route path="/upload"      element={<Upload />}       />
            <Route path="/reports"     element={<Reports />}      />
            <Route path="/reports/:id" element={<ReportDetail />} />
            <Route path="/validate"    element={<Validate />}     />
            <Route path="/scenarios"   element={<Scenarios />}    />
            <Route path="/policies"    element={<PolicySearch />} />
            <Route path="/admin"       element={<Admin />}        />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
