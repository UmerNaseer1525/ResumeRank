import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Toaster } from 'react-hot-toast'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import BackgroundLayer from './components/BackgroundLayer'
import { AuthProvider } from './context/AuthProvider'
import { LoadingProvider } from './context/LoadingProvider'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <LoadingProvider>
          <div className="app-shell">
            <BackgroundLayer />
            <div className="app-content">
              <App />
              <Toaster
                position="top-right"
                toastOptions={{
                  style: {
                    border: '1px solid #bfdbfe',
                    padding: '10px 14px',
                    color: '#1e3a8a',
                  },
                }}
              />
            </div>
          </div>
        </LoadingProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
