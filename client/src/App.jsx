import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from './api/queryClient.js'
import Dashboard from './components/Dashboard/Dashboard.jsx'

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: 'rgba(13, 21, 37, 0.95)',
              color: '#e8f0fe',
              border: '1px solid rgba(0, 170, 255, 0.3)',
              fontFamily: 'Inter, sans-serif',
              fontSize: '13px',
            },
            duration: 4000,
          }}
        />
        <Routes>
          <Route path="/*" element={<Dashboard />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
